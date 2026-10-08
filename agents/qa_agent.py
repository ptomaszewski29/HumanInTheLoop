from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.code_cleaner import strip_code_fences
from services.file_bundle import FileBundle
from services.file_parser import FileParseError, FileParser
from services.llm_factory import LLMFactory


class QAAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create()

    def execute(
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
- import from the matching source file

Return only JSON in exactly this shape:

{{
  "files": [
    {{
      "path": "tests/notification.service.test.ts",
      "content": "...typescript..."
    }}
  ]
}}

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

        print("=" * 80)
        print(f"QA RESULT ({len(tests)} file(s))")
        print("=" * 80)
        print(FileBundle.structure(tests))
        print("=" * 80)

        return tests

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
