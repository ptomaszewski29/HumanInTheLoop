from dataclasses import dataclass

from workflows.review_decision import (
    ReviewDecision,
)


@dataclass
class ArchitectureReview:
    score: int

    recommendation: ReviewDecision

    review: str
