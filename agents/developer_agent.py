from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.code_cleaner import strip_code_fences
from services.file_bundle import FileBundle
from services.file_naming import FileNaming
from services.file_parser import FileParseError, FileParser
from services.llm_factory import LLMFactory

FORMAT = """
Return only JSON in exactly this shape:

{
  "files": [
    {
      "path": "src/notification.service.ts",
      "content": "...typescript..."
    },
    {
      "path": "src/email.provider.ts",
      "content": "...typescript..."
    }
  ]
}

Rules:

- one file per logical component
- paths are relative, always starting with src/
- never use .. in a path
- put the whole file in "content"
- escape newlines in "content" as \n
- no explanations outside the JSON
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

        prompt = f"""
You are a Senior TypeScript Developer.

Task:
{task}

Split the solution into the files a real
project would have: one interface, service,
provider or component per file.
{FORMAT}
"""

        return self._generate(prompt, task)

    def improve(
        self,
        task: str,
        files: list[GeneratedFile],
        review: str,
    ) -> list[GeneratedFile]:

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

        print("=" * 80)
        print(
            f"DEVELOPER RESULT ({len(files)} file(s))"
        )
        print("=" * 80)
        print(FileBundle.structure(files))
        print("=" * 80)

        return files

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
