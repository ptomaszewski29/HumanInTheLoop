from workflows.review_decision import (
    ReviewDecision,
)


class RecommendationPolicy:
    """Severity decides the recommendation, not the model.

    Three sources feed in: the architect's own blockers,
    the structural validator's findings, and the severity
    rules below.

    Rule 1: at least one blocker -> REQUEST_CHANGES.
    Rule 2: warnings without blockers -> APPROVE.
    Rule 3: suggestions only -> APPROVE.

    A structural finding outranks the model entirely: the
    validator checked the files, the model only read them.

    An explicit REJECT from the architect is kept, because
    the severity rules do not cover it.
    """

    @staticmethod
    def decide(
        blockers: list[str],
        structural: list[str] | None = None,
        stated: ReviewDecision | None = None,
    ) -> ReviewDecision:

        if structural is not None and not isinstance(
            structural, list
        ):
            raise TypeError(
                "decide() takes the structural findings "
                "second and the stated recommendation "
                f"third; got {structural!r} as structural."
            )

        if structural:
            return ReviewDecision.REQUEST_CHANGES

        if stated == ReviewDecision.REJECT:
            return ReviewDecision.REJECT

        if blockers:
            return ReviewDecision.REQUEST_CHANGES

        return ReviewDecision.APPROVE
