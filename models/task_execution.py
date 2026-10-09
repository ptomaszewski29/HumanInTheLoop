from dataclasses import dataclass
from enum import Enum


class ExecutionStatus(str, Enum):
    """Where one planned task stands."""

    # Waiting on a dependency that has not completed.
    PENDING = "PENDING"

    READY = "READY"

    RUNNING = "RUNNING"

    COMPLETED = "COMPLETED"

    FAILED = "FAILED"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "ExecutionStatus":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.PENDING


@dataclass
class LogEntry:
    """One line of what happened, and when.

    Built from the stored executions rather than appended
    to as the run goes, so the log a restart shows is the
    same log that was on screen before it.
    """

    at: str = ""

    event: str = ""

    task_id: int = 0

    title: str = ""

    detail: str = ""


@dataclass
class TaskExecution:
    """What happened when a planned task was run.

    Only recorded once a run starts. A task with no record
    has not been attempted, and its status is worked out
    from the dependency graph instead.
    """

    task_id: int = 0

    status: ExecutionStatus = ExecutionStatus.RUNNING

    started_at: str = ""

    completed_at: str = ""

    error: str = ""

    # The Task row this run produced, if it got that far.
    task_record_id: str = ""

    @property
    def done(self) -> bool:

        return self.status == ExecutionStatus.COMPLETED

    @property
    def failed(self) -> bool:

        return self.status == ExecutionStatus.FAILED

    @property
    def duration(self) -> str:
        """How long it took, when both ends are known."""

        if not self.started_at or not self.completed_at:
            return ""

        from datetime import datetime

        try:
            started = datetime.fromisoformat(
                self.started_at
            )

            finished = datetime.fromisoformat(
                self.completed_at
            )

        except ValueError:
            return ""

        seconds = (finished - started).total_seconds()

        if seconds < 60:
            return f"{seconds:.0f}s"

        return f"{seconds / 60:.1f}m"
