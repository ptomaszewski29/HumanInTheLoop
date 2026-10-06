from enum import Enum


class TaskStatus(str, Enum):
    NEW = "NEW"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
