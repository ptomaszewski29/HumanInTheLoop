import json
import re

from models.file_type import FileType
from models.generated_file import GeneratedFile

FENCE = re.compile(
    r"^```[a-zA-Z0-9+#-]*\s*\n?|\n?```\s*$",
    re.MULTILINE,
)

MAX_FILES = 25

PATH_KEY = re.compile(r'"path"\s*:\s*"([^"\n]*)"')

CONTENT_KEY = re.compile(r'"content"\s*:\s*"')

ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    '"': '"',
    "\\": "\\",
    "/": "/",
}

WHITESPACE = " \t\r\n"

# The entry ends here: a closing brace, then the next entry
# or the end of the list.
CLOSES_ENTRY = re.compile(r'\s*\}\s*(?:,\s*\{|\]|$)')

# Another key follows in the same entry: a comma, then a
# quoted name, then a colon.
NEXT_KEY = re.compile(r'\s*,\s*"[A-Za-z_][\w-]*"\s*:')

# A path as it appears in a review: at least one folder, a
# file name, a known source extension.
#
# The lookbehind is the point. Without it the scan happily
# starts in the middle of ../../etc/evil.ts and reports
# etc/evil.ts -- a path that looks safe because the part
# that made it dangerous was left behind. Review text comes
# from the model, so it is not a place to be relaxed about
# this.
PATH_IN_TEXT = re.compile(
    r"(?<![\w./\\-])"
    r"(?:[\w.-]+/)+[\w.-]+\.(?:ts|tsx|js|jsx|mts|cts)\b"
)


class FileParseError(ValueError):
    pass


class FileParser:
    """Turns a model's JSON answer into GeneratedFile objects.

    Local models wrap JSON in prose or fences and sometimes
    emit none at all, so the outermost JSON object is
    located rather than assuming the whole answer is JSON.
    """

    @staticmethod
    def extract_json(raw: str) -> str:

        text = FENCE.sub("", raw.strip()).strip()

        start = text.find("{")

        if start == -1:
            raise FileParseError(
                "No JSON object in the answer."
            )

        depth = 0

        in_string = False

        escaped = False

        for index in range(start, len(text)):

            character = text[index]

            if in_string:

                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False

                continue

            if character == '"':
                in_string = True

            elif character == "{":
                depth += 1

            elif character == "}":
                depth -= 1

                if depth == 0:
                    return text[start : index + 1]

        raise FileParseError(
            "The JSON object is not closed."
        )

    @staticmethod
    def escape_control_characters(text: str) -> str:
        """Escapes raw newlines and tabs inside strings.

        Models routinely paste code straight into a JSON
        string without escaping it, which strict JSON
        rejects. The structure is still recoverable.
        """

        replacements = {
            "\n": "\\n",
            "\r": "\\r",
            "\t": "\\t",
        }

        out: list[str] = []

        in_string = False

        escaped = False

        for character in text:

            if in_string:

                if escaped:
                    escaped = False

                elif character == "\\":
                    escaped = True

                elif character == '"':
                    in_string = False

                elif character in replacements:
                    out.append(replacements[character])
                    continue

            elif character == '"':
                in_string = True

            out.append(character)

        return "".join(out)

    @staticmethod
    def load(raw_json: str) -> dict:
        """Strict JSON first, then the forgiving pass."""

        try:
            return json.loads(raw_json)

        except json.JSONDecodeError:
            return json.loads(
                FileParser.escape_control_characters(
                    raw_json
                )
            )

    @staticmethod
    def balanced_objects(text: str) -> list[dict]:
        """Every complete JSON object inside the text.

        A model that runs out of tokens leaves the outer
        object unclosed, but the file entries it already
        emitted are intact and worth keeping.
        """

        found: list[dict] = []

        index = 0

        while index < len(text):

            if text[index] != "{":
                index += 1
                continue

            depth = 0

            in_string = False

            escaped = False

            end = None

            for position in range(index, len(text)):

                character = text[position]

                if in_string:

                    if escaped:
                        escaped = False
                    elif character == "\\":
                        escaped = True
                    elif character == '"':
                        in_string = False

                    continue

                if character == '"':
                    in_string = True

                elif character == "{":
                    depth += 1

                elif character == "}":
                    depth -= 1

                    if depth == 0:
                        end = position
                        break

            if end is None:
                index += 1
                continue

            try:
                value = FileParser.load(
                    text[index : end + 1]
                )

            except (ValueError, TypeError):
                index += 1
                continue

            if isinstance(value, dict):
                found.append(value)

            index = end + 1

        return found

    @staticmethod
    def salvage(raw: str) -> list[dict]:
        """File entries recoverable from a truncated answer."""

        text = FENCE.sub("", raw.strip()).strip()

        return [
            value
            for value in FileParser.balanced_objects(text)
            if "path" in value and "content" in value
        ]

    @staticmethod
    def recover_entries(raw: str) -> list[dict]:
        """File entries read without trusting the quoting.

        A single unescaped quote inside generated code —
        `const s = "hi";` is enough — ends the string as
        far as a strict scanner is concerned, and every
        brace after it is miscounted. The answer is then
        declared truncated when it is in fact complete,
        and the file carrying the quote is lost.

        So this does not scan for structure. It anchors on
        the two keys that matter and decides where content
        ends by what follows the quote: a terminator is a
        quote followed by a comma or a closing brace. A
        quote inside code is followed by a semicolon, an
        operator or more code, so it is passed over.
        """

        text = FENCE.sub("", raw.strip()).strip()

        entries: list[dict] = []

        for match in PATH_KEY.finditer(text):

            path = match.group(1)

            content_key = CONTENT_KEY.search(text, match.end())

            if content_key is None:
                continue

            # Another path before the content means this
            # entry has no content of its own.
            following = PATH_KEY.search(text, match.end())

            if (
                following is not None
                and following.start() < content_key.start()
            ):
                continue

            content = FileParser._read_until_terminator(
                text,
                content_key.end(),
            )

            if content is None:
                continue

            entries.append({"path": path, "content": content})

        return entries

    @staticmethod
    def _read_until_terminator(
        text: str,
        start: int,
    ) -> str | None:
        """The string beginning at 'start', leniently read."""

        out: list[str] = []

        index = start

        while index < len(text):

            character = text[index]

            if character == "\\" and index + 1 < len(text):

                nxt = text[index + 1]

                out.append(ESCAPES.get(nxt, nxt))

                index += 2

                continue

            if character == '"':

                if FileParser._ends_the_value(text, index):
                    return "".join(out)

                # A quote in the middle of code: keep it.
                out.append('"')

                index += 1

                continue

            out.append(character)

            index += 1

        return None

    @staticmethod
    def _ends_the_value(text: str, quote: int) -> bool:
        """Whether the quote at 'quote' closes the value.

        Looking only for a comma or a brace after it is not
        enough: `const a = "x", b = 2;` and `join(", ")`
        both have one, and accepting either truncates the
        file in the middle. So what follows must be real
        JSON structure -- the next entry, the next key, or
        the end of the list -- which code does not imitate
        by accident.
        """

        return bool(
            CLOSES_ENTRY.match(text, quote + 1)
            or NEXT_KEY.match(text, quote + 1)
        )

    @staticmethod
    def paths_in(text: str) -> list[str]:
        """Repository paths mentioned in prose, in order.

        Used to work out which files a review is about
        without asking the model which files its own review
        was about. Only paths that would be safe to write
        are returned, and each appears once.
        """

        found: list[str] = []

        for match in PATH_IN_TEXT.finditer(text):

            path = FileParser.safe_path(match.group(0))

            if path and path not in found:
                found.append(path)

        return found

    @staticmethod
    def safe_path(path: str) -> str | None:
        """A repository-relative path, or None if unsafe.

        Dangerous paths are rejected outright. Stripping
        the dangerous part instead would turn ../x.ts into
        a legitimate-looking x.ts and quietly write it.
        """

        cleaned = path.replace("\\", "/").strip()

        while cleaned.startswith("./"):
            cleaned = cleaned[2:]

        if not cleaned:
            return None

        if any(character < " " for character in cleaned):
            return None

        if cleaned.startswith("/") or ":" in cleaned:
            return None

        segments = cleaned.split("/")

        if any(
            segment in ("", "..", ".")
            for segment in segments
        ):
            return None

        return cleaned

    @staticmethod
    def parse(
        raw: str,
        file_type: FileType = FileType.SOURCE,
    ) -> list[GeneratedFile]:

        try:
            payload = FileParser.load(
                FileParser.extract_json(raw)
            )

            entries = payload.get("files")

        except (FileParseError, ValueError):
            entries = None

        if not isinstance(entries, list):

            # A truncated answer still carries the entries
            # the model finished before it ran out.
            entries = FileParser.salvage(raw)

            # Salvage only keeps entries whose braces
            # balance, so a stray quote still costs its
            # file. Read the keys directly when that has
            # left anything behind.
            lenient = FileParser.recover_entries(raw)

            if len(lenient) > len(entries):
                entries = lenient

            if entries:
                print(
                    f"recovered {len(entries)} file(s) "
                    "from an answer strict JSON rejected"
                )

        if not entries:
            raise FileParseError(
                "No usable 'files' list in the answer."
            )

        files: list[GeneratedFile] = []

        seen: set[str] = set()

        for entry in entries[:MAX_FILES]:

            if not isinstance(entry, dict):
                continue

            path = str(entry.get("path", "")).strip()

            content = entry.get("content", "")

            if not isinstance(content, str):
                content = str(content)

            if not path or not content.strip():
                continue

            path = FileParser.safe_path(path)

            if not path:
                continue

            if path in seen:
                continue

            seen.add(path)

            files.append(
                GeneratedFile(
                    path=path,
                    file_type=file_type,
                    content=content,
                )
            )

        if not files:
            raise FileParseError(
                "The 'files' list held no usable entry."
            )

        return files
