from dataclasses import dataclass

from models.file_type import FileType


@dataclass
class GeneratedFile:
    """A file the workflow actually wrote to a repository."""

    file_path: str

    file_type: FileType = FileType.CODE

    content: str = ""
