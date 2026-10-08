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
