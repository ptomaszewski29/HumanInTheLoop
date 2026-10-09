from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.code_cleaner import strip_code_fences
from services.file_bundle import FileBundle
from services.file_naming import FileNaming
from services.file_parser import FileParseError, FileParser
from services.import_repair import drop_self_imports
from services.llm_factory import LLMFactory

# The paths in these examples are deliberately not names
# any real task would produce. A small model copies a
# plausible example instead of answering: shown
# "src/notification.service.ts", a 3B model planned exactly
# that for the task "Create package.json". EXAMPLE_PATHS is
# the mechanical guard that goes with it.
EXAMPLE_PATHS = frozenset(
    {"src/example-one.ts", "src/example-two.ts"}
)

FORMAT = """
Return only JSON in exactly this shape:

{
  "files": [
    {
      "path": "src/example-one.ts",
      "content": "...typescript..."
    },
    {
      "path": "src/example-two.ts",
      "content": "...typescript..."
    }
  ]
}

Rules:

- those two paths show the format only; never use them
- one file per logical component
- paths are relative to the repository root
- source files go under src/; a configuration file such
  as package.json or tsconfig.json sits at the root
- never use .. in a path
- put the whole file in "content"
- escape newlines in "content" as \n
- no explanations outside the JSON
"""

PLAN_FORMAT = """
Return only JSON in exactly this shape:

{
  "files": [
    {
      "path": "src/example-one.ts",
      "content": "One sentence about what this file is for."
    },
    {
      "path": "src/example-two.ts",
      "content": "One sentence about what this file is for."
    }
  ]
}

Rules:

- those two paths show the format only; never use them
- name the files this task needs, not the ones above
- "content" is one sentence saying what the file is for
- no code at this stage
- one file per logical component
- paths are relative to the repository root
- source files go under src/; a configuration file such
  as package.json or tsconfig.json sits at the root
- never use .. in a path
- no explanations outside the JSON
"""

# What the model is told about writing a single file. The
# instruction against stubs is here rather than in the
# shared format because it is only affordable once the
# whole answer is about one file.
WRITE_RULES = """
Write the complete file. Every method has a real body.
No TODO, no placeholder, no "in a real implementation
this would ...". Import from the other files by their
paths above where you need them.

Return the TypeScript only: no JSON, no markdown fence,
no explanation.
"""


class DeveloperAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create()

    def execute(
        self,
        task: str,
    ) -> list[GeneratedFile]:

        if Settings.GENERATE_FILE_BY_FILE:

            planned = self._plan(task)

            if planned:
                return self._write_each(task, planned)

        return self._generate(self._one_call_prompt(task), task)

    def improve(
        self,
        task: str,
        files: list[GeneratedFile],
        review: str,
    ) -> list[GeneratedFile]:

        if Settings.GENERATE_FILE_BY_FILE:

            targets = self._targets(files, review)

            if targets:
                return self._rewrite(
                    task,
                    files,
                    review,
                    targets,
                )

        prompt = f"""
You are a Senior TypeScript Developer.

Original task:
{task}

Architect review:

{review}

Current files:

{FileBundle.render(files)}

First, fix every repository problem. If a
file is reported missing, create that exact
file with real content. If a symbol is
reported missing, define and export it.

Then fix every BLOCKER. Address the warnings
only if that does not risk a blocker. Ignore
the suggestions.

Return the complete file set, including the
files you did not change. You may add or
remove files when the review asks for it.
{FORMAT}
"""

        return self._generate(prompt, task)

    # ------------------------------------------------
    # file by file
    # ------------------------------------------------

    def _plan(self, task: str) -> list[tuple[str, str]]:
        """The files to write, as (path, purpose).

        An empty list means the planning call was unusable
        and the caller should fall back to one call for
        everything -- a thin answer beats no answer.
        """

        prompt = f"""
You are a Senior TypeScript Developer.

Task:
{task}

List only the files this task actually needs.

Match the list to the task. "Initialise a node
project" is one file; a notification platform
with three providers is a dozen. Do not pad the
list to look thorough: every file you name costs
a call, and a file nobody asked for is worse
than no file.

One file is a perfectly good answer. At most
{Settings.MAX_FILES_PER_TASK}.
{PLAN_FORMAT}
"""

        try:
            entries = FileParser.parse(
                self.llm.generate_text(prompt),
                FileType.SOURCE,
            )

        except (FileParseError, ValueError, RuntimeError) as error:

            print(
                f"DEVELOPER: no usable file plan ({error}); "
                "falling back to one call"
            )

            return []

        planned = [
            (item.path, item.content.strip())
            for item in entries
            if item.path not in EXAMPLE_PATHS
        ][: Settings.MAX_FILES_PER_TASK]

        if not planned:

            print(
                "DEVELOPER: the plan was the example copied "
                "back; falling back to one call"
            )

            return []

        print("=" * 80)
        print(f"DEVELOPER PLAN ({len(planned)} file(s))")
        print("=" * 80)

        for path, purpose in planned:
            print(f"- {path}: {purpose}")

        print("=" * 80)

        return planned

    @staticmethod
    def _batches(
        planned: list[tuple[str, str]],
    ) -> list[list[tuple[str, str]]]:
        """The planned files, grouped per call."""

        size = max(1, Settings.FILES_PER_CALL)

        return [
            planned[start : start + size]
            for start in range(0, len(planned), size)
        ]

    def _write_each(
        self,
        task: str,
        planned: list[tuple[str, str]],
    ) -> list[GeneratedFile]:
        """Writes the planned files, a batch per call."""

        listing = "\n".join(
            f"- {path}: {purpose}"
            for path, purpose in planned
        )

        batches = self._batches(planned)

        files: list[GeneratedFile] = []

        for position, batch in enumerate(batches, start=1):

            print(
                "DEVELOPER: writing "
                + ", ".join(path for path, _ in batch)
                + f" ({position}/{len(batches)})"
            )

            files.extend(
                self._write_batch(task, listing, batch)
            )

        if not files:
            raise RuntimeError(
                "DeveloperAgent wrote none of the "
                f"{len(planned)} planned file(s)."
            )

        missing = [
            path
            for path, _ in planned
            if path not in {item.path for item in files}
        ]

        if missing:
            print(
                f"DEVELOPER: {len(missing)} planned file(s) "
                "did not come back: " + ", ".join(missing)
            )

        files = self._settle(files)

        self._announce(files)

        return files

    def _write_batch(
        self,
        task: str,
        listing: str,
        batch: list[tuple[str, str]],
    ) -> list[GeneratedFile]:
        """One call's worth of files.

        A batch of one asks for plain TypeScript, which
        takes JSON out of the picture altogether. Anything
        larger has to answer in JSON, because one answer
        carries several files.
        """

        if len(batch) == 1:

            path, purpose = batch[0]

            content = self._write_one(
                task,
                listing,
                path,
                purpose,
            )

            return (
                [
                    GeneratedFile(
                        path=path,
                        file_type=FileType.SOURCE,
                        content=content,
                    )
                ]
                if content
                else []
            )

        wanted = "\n".join(
            f"- {path}: {purpose}" for path, purpose in batch
        )

        prompt = f"""
You are a Senior TypeScript Developer.

Overall task:
{task}

The solution is split across these files:
{listing}

Write exactly these {len(batch)}, and no others:
{wanted}

Write each one in full. Every method has a real
body. No TODO, no placeholder, no "in a real
implementation this would ...". Import from the
other files by their paths above where you need
them.
{FORMAT}
"""

        try:
            raw = self.llm.generate_text(prompt)

        except Exception as error:  # noqa: BLE001

            print(
                "DEVELOPER: batch failed "
                f"({error}): "
                + ", ".join(path for path, _ in batch)
            )

            return []

        try:
            written = FileParser.parse(raw, FileType.SOURCE)

        except (FileParseError, ValueError) as error:

            print(f"DEVELOPER: batch unusable ({error})")

            return []

        # The model is asked for specific paths and does
        # not always honour them. Keeping anything it
        # invents would quietly grow the file set past the
        # plan the rest of the run is working from.
        asked = {path for path, _ in batch}

        return [
            item for item in written if item.path in asked
        ]

    def _write_one(
        self,
        task: str,
        listing: str,
        path: str,
        purpose: str,
        existing: str = "",
        review: str = "",
    ) -> str:
        """One file's content, or '' if the call failed.

        A file that cannot be written is reported and
        skipped: losing one file is recoverable, and the
        Architect will say so on the next round. Failing
        the whole task because the ninth file timed out is
        not.
        """

        current = (
            f"""
The file as it stands:

{existing}
"""
            if existing
            else ""
        )

        correction = (
            f"""
Architect review of the current code:

{review}

Fix what the review raises about this file.
Keep everything it does not object to.
"""
            if review
            else ""
        )

        prompt = f"""
You are a Senior TypeScript Developer.

Overall task:
{task}

The solution is split across these files:
{listing}

Write exactly one of them: {path}
Its job: {purpose}
{current}{correction}{WRITE_RULES}
"""

        try:
            answer = self.llm.generate_text(prompt)

        except Exception as error:  # noqa: BLE001

            # Any provider failure: a timeout, a refusal, a
            # dropped connection. One file is not worth the
            # task.
            print(f"DEVELOPER: {path} failed ({error})")

            return ""

        content = strip_code_fences(answer).strip()

        if not content:
            print(f"DEVELOPER: {path} came back empty")

        return content

    def _targets(
        self,
        files: list[GeneratedFile],
        review: str,
    ) -> list[str]:
        """The files a review round should rewrite.

        Decided here rather than by the model: a path that
        appears in the review is a path the Architect has
        something to say about. Sending the whole set back
        and asking for the whole set returned is what made
        a review round a no-op -- measured three times, the
        model returned the same files with twenty
        characters changed.
        """

        named = [
            item.path
            for item in files
            if item.path in review
        ]

        missing = [
            path
            for path in FileParser.paths_in(review)
            if path not in {item.path for item in files}
        ]

        # Nothing named: rewrite the largest file, which is
        # where the substance is, rather than nothing.
        if not named and not missing:

            if not files:
                return []

            named = [
                max(files, key=lambda item: len(item.content)).path
            ]

        return (named + missing)[: Settings.MAX_FILES_PER_TASK]

    def _rewrite(
        self,
        task: str,
        files: list[GeneratedFile],
        review: str,
        targets: list[str],
    ) -> list[GeneratedFile]:
        """Rewrites the named files, keeps the rest as they are."""

        by_path = {item.path: item for item in files}

        listing = "\n".join(
            f"- {item.path}" for item in files
        )

        for position, path in enumerate(targets, start=1):

            print(
                f"DEVELOPER: revising {path} "
                f"({position}/{len(targets)})"
            )

            existing = by_path.get(path)

            content = self._write_one(
                task,
                listing,
                path,
                "as described by the review",
                existing.content if existing else "",
                review,
            )

            if not content:
                continue

            by_path[path] = GeneratedFile(
                path=path,
                file_type=FileType.SOURCE,
                content=content,
            )

        # Order: the files that existed, then anything the
        # review asked for that did not.
        kept = [by_path[item.path] for item in files]

        added = [
            by_path[path]
            for path in targets
            if path not in {item.path for item in files}
            and path in by_path
        ]

        settled = self._settle(kept + added)

        self._announce(settled)

        return settled

    # ------------------------------------------------
    # one call for everything
    # ------------------------------------------------

    @staticmethod
    def _one_call_prompt(task: str) -> str:

        return f"""
You are a Senior TypeScript Developer.

Task:
{task}

Split the solution into the files a real
project would have: one interface, service,
provider or component per file.
{FORMAT}
"""

    def _generate(
        self,
        prompt: str,
        task: str,
    ) -> list[GeneratedFile]:

        raw = self.llm.generate_text(prompt)

        try:
            files = FileParser.parse(
                raw,
                FileType.SOURCE,
            )

        except (FileParseError, ValueError) as error:
            files = self._single_file(raw, task, error)

        files = self._settle(files)

        self._announce(files)

        return files

    @staticmethod
    def _settle(
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:
        """The last mechanical pass before the files leave.

        A file importing itself is the one cycle with no
        design question in it, so it is cut here rather
        than described to the model -- which was asked to
        fix exactly that for two rounds running and did
        not.
        """

        repaired, notes = drop_self_imports(files)

        for note in notes:
            print(f"DEVELOPER: {note}")

        return repaired

    @staticmethod
    def _announce(files: list[GeneratedFile]) -> None:

        print("=" * 80)
        print(
            f"DEVELOPER RESULT ({len(files)} file(s), "
            f"{sum(len(item.content) for item in files)} chars)"
        )
        print("=" * 80)
        print(FileBundle.structure(files))
        print("=" * 80)

    @staticmethod
    def _single_file(
        raw: str,
        task: str,
        error: Exception,
    ) -> list[GeneratedFile]:
        """Falls back to one file when the JSON is unusable.

        A model that ignores the format still produces
        usable code, so the run continues with a single
        file rather than failing outright.
        """

        content = strip_code_fences(raw)

        if not content.strip():
            raise RuntimeError(
                f"DeveloperAgent returned nothing usable: {error}"
            )

        print(
            "DEVELOPER: JSON unusable "
            f"({error}); falling back to a single file"
        )

        return [
            GeneratedFile(
                path=FileNaming.code_path(content, task),
                file_type=FileType.SOURCE,
                content=content,
            )
        ]
