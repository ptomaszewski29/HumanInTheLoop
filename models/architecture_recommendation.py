from enum import Enum


class ArchitectureRecommendation(str, Enum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    REJECT = "REJECT"
    UNKNOWN = "UNKNOWN"
