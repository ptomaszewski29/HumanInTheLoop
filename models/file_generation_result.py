from dataclasses import dataclass

from models.file_type import FileType


@dataclass
class FileGenerationResult:
    """A file the workflow wants written, before it exists."""

    relative_path: str

    content: str

    file_type: FileType = FileType.SOURCE
