from dataclasses import dataclass
from enum import Enum


class ChangeType(str, Enum):
    ADDED = "added"

    MODIFIED = "modified"

    DELETED = "deleted"

    UNCHANGED = "unchanged"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "ChangeType":

        try:
            return cls(str(value).lower())

        except ValueError:
            return cls.UNCHANGED


@dataclass
class GitDiff:
    """What one generated file would change in the repository."""

    file_path: str

    change_type: ChangeType = ChangeType.ADDED

    diff_content: str = ""

    @property
    def is_change(self) -> bool:

        return self.change_type != ChangeType.UNCHANGED
