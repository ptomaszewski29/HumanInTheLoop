import json
import re

from models.file_type import FileType
from models.generated_file import GeneratedFile

FENCE = re.compile(
    r"^```[a-zA-Z0-9+#-]*\s*\n?|\n?```\s*$",
    re.MULTILINE,
)

MAX_FILES = 25


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

        payload = FileParser.load(
            FileParser.extract_json(raw)
        )

        entries = payload.get("files")

        if not isinstance(entries, list):
            raise FileParseError(
                "The JSON has no 'files' list."
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
