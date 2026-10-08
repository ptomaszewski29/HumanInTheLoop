import os

from models.file_generation_result import (
    FileGenerationResult,
)
from models.generated_file import GeneratedFile


class FileWriter:
    """Writes generated files inside a repository folder.

    Every path is checked to stay within the repository
    root, so a generated path can never reach the rest of
    the machine.
    """

    @staticmethod
    def resolve(
        repository_path: str,
        relative_path: str,
    ) -> str:
        """Absolute target path, or an error if unsafe."""

        if not relative_path or not relative_path.strip():
            raise ValueError("Empty file path.")

        candidate = relative_path.strip().replace("\\", "/")

        if os.path.isabs(candidate) or ":" in candidate:
            raise ValueError(
                f"Absolute paths are not allowed: {relative_path}"
            )

        root = os.path.abspath(repository_path)

        target = os.path.abspath(
            os.path.join(root, candidate)
        )

        if target != root and not target.startswith(
            root + os.sep
        ):
            raise ValueError(
                "Path escapes the repository: "
                f"{relative_path}"
            )

        return target

    @staticmethod
    def write(
        repository_path: str,
        result: FileGenerationResult,
    ) -> GeneratedFile:

        if not os.path.isdir(repository_path):
            raise ValueError(
                "Repository folder does not exist: "
                f"{repository_path}"
            )

        target = FileWriter.resolve(
            repository_path,
            result.relative_path,
        )

        os.makedirs(
            os.path.dirname(target),
            exist_ok=True,
        )

        existed = os.path.exists(target)

        with open(
            target,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(result.content)

        print(
            f"{'overwrote' if existed else 'created'} "
            f"{target}"
        )

        return GeneratedFile(
            file_path=result.relative_path.strip().replace(
                "\\", "/"
            ),
            file_type=result.file_type,
            content=result.content,
        )

    @staticmethod
    def write_all(
        repository_path: str,
        results: list[FileGenerationResult],
    ) -> list[GeneratedFile]:

        return [
            FileWriter.write(repository_path, result)
            for result in results
        ]

    @staticmethod
    def read(
        repository_path: str,
        file_path: str,
    ) -> str | None:
        """Current content on disk, or None if unreadable."""

        try:
            target = FileWriter.resolve(
                repository_path,
                file_path,
            )
        except ValueError:
            return None

        if not os.path.isfile(target):
            return None

        with open(
            target,
            encoding="utf-8",
        ) as handle:
            return handle.read()
