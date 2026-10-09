from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from models.github_issue import IssueLink
from models.task_breakdown import TaskBreakdown
from models.task_execution import (
    ExecutionStatus,
    LogEntry,
    TaskExecution,
)


@dataclass
class Plan:
    """An epic, and the tasks the planner broke it into."""

    id: str = field(default_factory=lambda: str(uuid4()))

    repository_id: str = ""

    requirement_id: str = ""

    issue: IssueLink = field(default_factory=IssueLink)

    epic: str = ""

    tasks: list[TaskBreakdown] = field(
        default_factory=list
    )

    # What happened to each task that has been attempted.
    # The single record of progress: 'completed' below is
    # derived from it rather than stored beside it.
    executions: list[TaskExecution] = field(
        default_factory=list
    )

    # Problems found in the breakdown the model proposed:
    # self-dependencies, unknown ids, cycles. Reported
    # rather than silently repaired.
    issues: list[str] = field(default_factory=list)

    created_at: str = field(
        default_factory=lambda: datetime.now(
            UTC
        ).isoformat()
    )

    def task(self, task_id: int) -> TaskBreakdown | None:

        for item in self.tasks:

            if item.id == task_id:
                return item

        return None

    def execution(
        self,
        task_id: int,
    ) -> TaskExecution | None:

        for item in self.executions:

            if item.task_id == task_id:
                return item

        return None

    def record(self, execution: TaskExecution) -> None:
        """Keeps one record per task, the latest winning."""

        self.executions = [
            item
            for item in self.executions
            if item.task_id != execution.task_id
        ]

        self.executions.append(execution)

    @property
    def completed(self) -> list[int]:
        """The tasks that finished, in id order."""

        return sorted(
            item.task_id
            for item in self.executions
            if item.done
        )

    def is_done(self, task_id: int) -> bool:

        execution = self.execution(task_id)

        return execution is not None and execution.done

    def status_of(
        self,
        item: TaskBreakdown,
    ) -> ExecutionStatus:
        """What the dashboard and the buttons go by."""

        execution = self.execution(item.id)

        if execution is not None and execution.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.RUNNING,
        ):
            return execution.status

        if self.blocked_by(item):
            return ExecutionStatus.PENDING

        return ExecutionStatus.READY

    def dashboard(self) -> dict[str, int]:
        """Totals for every status, including zeros."""

        counts = {
            status.value: 0 for status in ExecutionStatus
        }

        for item in self.tasks:
            counts[self.status_of(item).value] += 1

        counts["TOTAL"] = len(self.tasks)

        return counts

    @property
    def running(self) -> TaskBreakdown | None:
        """The task being worked on, if any.

        Read from the stored record, so it is right after a
        rerun and after a restart alike.
        """

        for item in self.tasks:

            execution = self.execution(item.id)

            if (
                execution is not None
                and execution.status
                == ExecutionStatus.RUNNING
            ):
                return item

        return None

    def next_ready(self) -> TaskBreakdown | None:
        """The next task a run-all should pick up.

        Tasks are already in dependency order, so the first
        unfinished one whose dependencies are done is it.
        """

        for item in self.remaining:

            if self.is_ready(item):
                return item

        return None

    def log(self) -> list[LogEntry]:
        """Every start and finish, oldest first."""

        entries: list[LogEntry] = []

        for execution in self.executions:

            item = self.task(execution.task_id)

            title = item.title if item else ""

            if execution.started_at:

                entries.append(
                    LogEntry(
                        at=execution.started_at,
                        event="STARTED",
                        task_id=execution.task_id,
                        title=title,
                    )
                )

            if execution.completed_at:

                entries.append(
                    LogEntry(
                        at=execution.completed_at,
                        event=execution.status.value,
                        task_id=execution.task_id,
                        title=title,
                        detail=execution.error,
                    )
                )

        return sorted(
            entries,
            key=lambda entry: (entry.at, entry.event),
        )

    @property
    def percent_complete(self) -> float:

        if not self.tasks:
            return 0.0

        return len(self.completed) / len(self.tasks)

    @property
    def started(self) -> bool:

        return bool(self.executions)

    @property
    def remaining(self) -> list[TaskBreakdown]:
        """Everything not yet finished, failures included."""

        return [
            item
            for item in self.tasks
            if not self.is_done(item.id)
        ]

    def blocked_by(
        self,
        item: TaskBreakdown,
    ) -> list[int]:
        """Dependencies of this task that are not done yet."""

        return [
            dependency
            for dependency in item.dependencies
            if not self.is_done(dependency)
        ]

    def is_ready(self, item: TaskBreakdown) -> bool:

        return not self.blocked_by(item)

    def levels(self) -> list[list[TaskBreakdown]]:
        """The tasks arranged in dependency layers.

        Everything in one layer can run once the layers
        above it are done. A task caught in a cycle has no
        layer, so it lands in the last one.
        """

        known = {item.id for item in self.tasks}

        placed: dict[int, int] = {}

        remaining = list(self.tasks)

        depth = 0

        while remaining and depth < len(self.tasks) + 1:

            ready = [
                item
                for item in remaining
                if all(
                    dependency in placed
                    or dependency not in known
                    for dependency in item.dependencies
                )
            ]

            if not ready:
                break

            for item in ready:
                placed[item.id] = depth

                remaining.remove(item)

            depth += 1

        layers: list[list[TaskBreakdown]] = [
            [] for _ in range(depth + (1 if remaining else 0))
        ]

        for item in self.tasks:

            if item.id in placed:
                layers[placed[item.id]].append(item)

        if remaining:
            layers[-1].extend(remaining)

        return [layer for layer in layers if layer]
