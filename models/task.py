from dataclasses import dataclass

from models.task_status import TaskStatus


@dataclass
class Task:
    description: str
    generated_code: str = ""
    status: TaskStatus = TaskStatus.NEW