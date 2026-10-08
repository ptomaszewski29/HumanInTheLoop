from dataclasses import dataclass, field
from enum import Enum


class Priority(str, Enum):
    HIGH = "HIGH"

    MEDIUM = "MEDIUM"

    LOW = "LOW"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "Priority":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.MEDIUM

    @property
    def rank(self) -> int:
        """Lower sorts first."""

        return {
            Priority.HIGH: 0,
            Priority.MEDIUM: 1,
            Priority.LOW: 2,
        }[self]


@dataclass
class TaskBreakdown:
    """One task the planner carved out of an epic."""

    id: int = 0

    title: str = ""

    description: str = ""

    priority: Priority = Priority.MEDIUM

    # The ids of the tasks this one needs first.
    dependencies: list[int] = field(default_factory=list)

    @property
    def prompt(self) -> str:
        """What the developer is asked to build."""

        if not self.description.strip():
            return self.title.strip()

        return f"{self.title.strip()}\n\n{self.description.strip()}"
