from enum import Enum


class ReviewDecision(str, Enum):
    APPROVE = "APPROVE"

    REQUEST_CHANGES = "REQUEST_CHANGES"

    REJECT = "REJECT"

    UNKNOWN = "UNKNOWN"
