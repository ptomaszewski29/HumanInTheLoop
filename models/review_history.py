from dataclasses import dataclass

from workflows.review_decision import (
    ReviewDecision,
)


@dataclass
class ReviewHistory:
    iteration: int

    score: int

    recommendation: ReviewDecision

    review: str
