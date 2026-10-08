from dataclasses import dataclass
from enum import Enum


class PushStatus(str, Enum):
    NOT_PUSHED = "NOT_PUSHED"

    SUCCESS = "SUCCESS"

    FAILED = "FAILED"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "PushStatus":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.NOT_PUSHED


@dataclass
class GitPushOperation:
    """What happened when a branch was sent to a remote."""

    branch_name: str = ""

    remote_name: str = ""

    remote_url: str = ""

    pushed_at: str = ""

    status: PushStatus = PushStatus.NOT_PUSHED

    error: str = ""

    @property
    def pushed(self) -> bool:

        return self.status == PushStatus.SUCCESS

    @property
    def remote_branch(self) -> str:

        if not self.remote_name or not self.branch_name:
            return ""

        return f"{self.remote_name}/{self.branch_name}"
