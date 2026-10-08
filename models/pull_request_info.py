from dataclasses import dataclass
from enum import Enum


class PullRequestState(str, Enum):
    NONE = "NONE"

    OPEN = "OPEN"

    CLOSED = "CLOSED"

    MERGED = "MERGED"

    FAILED = "FAILED"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "PullRequestState":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.NONE


@dataclass
class PullRequestInfo:
    """The pull request a task produced, if any."""

    id: int = 0

    url: str = ""

    branch: str = ""

    base: str = ""

    state: PullRequestState = PullRequestState.NONE

    created_at: str = ""

    error: str = ""

    @property
    def exists(self) -> bool:

        return bool(self.url) and self.state in (
            PullRequestState.OPEN,
            PullRequestState.CLOSED,
            PullRequestState.MERGED,
        )

    @property
    def label(self) -> str:

        return f"PR #{self.id}" if self.id else "PR"
