from dataclasses import dataclass

from models.file_type import FileType


@dataclass
class GeneratedFile:
    """One file produced by the workflow."""

    path: str

    file_type: FileType = FileType.SOURCE

    content: str = ""
