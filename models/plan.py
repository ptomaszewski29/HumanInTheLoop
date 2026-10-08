from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from models.task_breakdown import TaskBreakdown


@dataclass
class Plan:
    """An epic, and the tasks the planner broke it into."""

    id: str = field(default_factory=lambda: str(uuid4()))

    repository_id: str = ""

    epic: str = ""

    tasks: list[TaskBreakdown] = field(
        default_factory=list
    )

    # Task ids already run through the pipeline.
    completed: list[int] = field(default_factory=list)

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

    def is_done(self, task_id: int) -> bool:

        return task_id in self.completed

    @property
    def remaining(self) -> list[TaskBreakdown]:

        return [
            item
            for item in self.tasks
            if item.id not in self.completed
        ]

    def blocked_by(
        self,
        item: TaskBreakdown,
    ) -> list[int]:
        """Dependencies of this task that are not done yet."""

        return [
            dependency
            for dependency in item.dependencies
            if dependency not in self.completed
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
