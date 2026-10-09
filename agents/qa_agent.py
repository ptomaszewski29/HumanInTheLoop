import posixpath

from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.code_cleaner import strip_code_fences
from services.file_bundle import FileBundle
from services.file_parser import FileParseError, FileParser
from services.llm_factory import LLMFactory

# The same trap as in the developer: a small model answers
# with the path it was shown, so the path it is shown is
# one no real project would have, and it is dropped if it
# comes back anyway.
EXAMPLE_TEST_PATH = "tests/example-one.test.ts"

# Files there is nothing to assert about: a config file, a
# barrel, a file of nothing but types. Writing a suite for
# one costs a call and produces a test that asserts the
# language works.
NOT_WORTH_TESTING = (
    ".d.ts",
    ".json",
    "index.ts",
)


class QAAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create()

    def execute(
        self,
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:

        if Settings.GENERATE_FILE_BY_FILE:

            written = self._suite_per_file(files)

            if written:
                return written

        return self._all_at_once(files)

    # ------------------------------------------------
    # a suite per source file
    # ------------------------------------------------

    @staticmethod
    def worth_testing(
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:

        return [
            item
            for item in files
            if not item.path.endswith(NOT_WORTH_TESTING)
            and item.content.strip()
        ]

    @staticmethod
    def import_specifier(
        test_path: str,
        source_path: str,
    ) -> str:
        """What the suite must import, spelled out.

        The relative path between two known paths is
        arithmetic, and the prompt used to ask for it.
        A 3B model answered './clock' for a suite in
        tests/ importing src/clock.ts, and every generated
        suite failed to resolve -- eight of them in one
        run, found the first time the test gate could
        actually run.
        """

        target = posixpath.splitext(source_path)[0]

        specifier = posixpath.relpath(
            target,
            posixpath.dirname(test_path) or ".",
        ).replace("\\", "/")

        return (
            specifier
            if specifier.startswith(".")
            else f"./{specifier}"
        )

    @staticmethod
    def test_path(source_path: str) -> str:
        """tests/<name>.test.ts for src/<anything>/<name>.ts."""

        name = source_path.rsplit("/", 1)[-1]

        for suffix in (".tsx", ".ts", ".mts", ".js"):
            name = name.removesuffix(suffix)

        return f"tests/{name}.test.ts"

    def _suite_per_file(
        self,
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:
        """One call per source file.

        The same reason the developer writes a file at a
        time: one answer covering eight files is one
        answer's worth of attention split eight ways, and
        what came back was a single suite for the whole
        project.
        """

        targets = self.worth_testing(files)

        if not targets:
            return []

        listing = FileBundle.structure(files)

        tests: list[GeneratedFile] = []

        for position, source in enumerate(
            targets,
            start=1,
        ):

            path = self.test_path(source.path)

            print(
                f"QA: writing {path} "
                f"({position}/{len(targets)})"
            )

            content = self._suite_for(
                source,
                listing,
                path,
            )

            if content:
                tests.append(
                    GeneratedFile(
                        path=path,
                        file_type=FileType.TEST,
                        content=content,
                    )
                )

        self._announce(tests)

        return tests

    def _suite_for(
        self,
        source: GeneratedFile,
        listing: str,
        path: str,
    ) -> str:
        """One source file's suite, or '' if the call failed."""

        specifier = self.import_specifier(
            path,
            source.path,
        )

        prompt = f"""
You are a QA Engineer.

The project has these files:
{listing}

Write a Vitest suite for exactly one of them:
{source.path}

That file:

{source.content}

Rules:

- the suite goes in {path}
- import exactly like this, and do not change
  the path:

    import {{ ... }} from '{specifier}';

- at most 3 tests
- use describe, it and expect
- this is Vitest, not Jest. For a mock write
  vi.fn(), and for a mocked type use
  ReturnType<typeof vi.fn>. The name `jest` does
  not exist here and a suite using it fails to
  run at all
- test what this file does, not what it imports
- do not invent exports it does not have

Return the TypeScript only: no JSON, no markdown
fence, no explanation.
"""

        try:
            answer = self.llm.generate_text(prompt)

        except Exception as error:  # noqa: BLE001

            # One missing suite is recoverable; the test
            # gate runs whatever was written.
            print(f"QA: {path} failed ({error})")

            return ""

        return strip_code_fences(answer).strip()

    # ------------------------------------------------
    # one call for everything
    # ------------------------------------------------

    def _all_at_once(
        self,
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:

        prompt = f"""
You are a QA Engineer.

Write a Vitest suite for this project.

Source files:

{FileBundle.structure(files)}

Code:

{FileBundle.render(files)}

Rules:

- one test file per source file worth testing
- a test file for src/x/y.ts goes in tests/y.test.ts
- at most 3 tests per file
- use describe, it and expect
- this is Vitest, not Jest: mocks are vi.fn()
- import from the matching source file

Return only JSON in exactly this shape:

{{
  "files": [
    {{
      "path": "tests/example-one.test.ts",
      "content": "...typescript..."
    }}
  ]
}}

That path shows the format only; never use it.
Escape newlines in "content" as \n.
No explanations outside the JSON.
"""

        raw = self.llm.generate_text(prompt)

        try:
            tests = FileParser.parse(
                raw,
                FileType.TEST,
            )

        except (FileParseError, ValueError) as error:
            tests = self._single_file(raw, files, error)

        tests = [
            item
            for item in tests
            if item.path != EXAMPLE_TEST_PATH
        ]

        self._announce(tests)

        return tests

    @staticmethod
    def _announce(tests: list[GeneratedFile]) -> None:

        print("=" * 80)
        print(f"QA RESULT ({len(tests)} file(s))")
        print("=" * 80)
        print(FileBundle.structure(tests))
        print("=" * 80)

    @staticmethod
    def _single_file(
        raw: str,
        files: list[GeneratedFile],
        error: Exception,
    ) -> list[GeneratedFile]:
        """Falls back to one suite when the JSON is unusable."""

        content = strip_code_fences(raw)

        if not content.strip():
            print(f"QA: no usable tests ({error})")

            return []

        stem = "generated"

        if files:
            stem = files[0].path.rsplit("/", 1)[-1]
            stem = stem.removesuffix(".ts")

        print(
            f"QA: JSON unusable ({error}); "
            "falling back to a single suite"
        )

        return [
            GeneratedFile(
                path=f"tests/{stem}.test.ts",
                file_type=FileType.TEST,
                content=content,
            )
        ]
