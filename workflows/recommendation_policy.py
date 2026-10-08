from workflows.review_decision import (
    ReviewDecision,
)


class RecommendationPolicy:
    """Severity decides the recommendation, not the model.

    Rule 1: at least one blocker -> REQUEST_CHANGES.
    Rule 2: warnings without blockers -> APPROVE.
    Rule 3: suggestions only -> APPROVE.

    An explicit REJECT from the architect is kept,
    because it is an escape hatch the severity
    rules do not cover.
    """

    @staticmethod
    def decide(
        blockers: list[str],
        stated: ReviewDecision | None = None,
    ) -> ReviewDecision:

        if stated == ReviewDecision.REJECT:
            return ReviewDecision.REJECT

        if blockers:
            return ReviewDecision.REQUEST_CHANGES

        return ReviewDecision.APPROVE
