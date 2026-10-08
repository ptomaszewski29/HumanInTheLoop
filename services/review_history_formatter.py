from models.review_history import (
    ReviewHistory,
)


class ReviewHistoryFormatter:

    @staticmethod
    def format(
        review_history: list[ReviewHistory],
    ) -> str:

        if not review_history:
            return "No previous reviews."

        blocks: list[str] = []

        for review in review_history:

            blocks.append(f"""
Iteration {review.iteration}

Score:
{review.score}

Recommendation:
{review.recommendation.value}

{ReviewHistoryFormatter._section("BLOCKERS", review.blockers)}
{ReviewHistoryFormatter._section("WARNINGS", review.warnings)}
{ReviewHistoryFormatter._section("SUGGESTIONS", review.suggestions)}
--------------------------
""")

        return "\n".join(blocks)

    @staticmethod
    def _section(
        title: str,
        findings: list[str],
    ) -> str:

        if not findings:
            return f"{title}:\n- None\n"

        lines = "\n".join(
            f"- {finding}" for finding in findings
        )

        return f"{title}:\n{lines}\n"

    @staticmethod
    def open_findings(
        review_history: list[ReviewHistory],
    ) -> str:
        """The findings the last review left open."""

        if not review_history:
            return "No previous findings."

        last = review_history[-1]

        return (
            ReviewHistoryFormatter._section(
                "BLOCKERS", last.blockers
            )
            + ReviewHistoryFormatter._section(
                "WARNINGS", last.warnings
            )
            + ReviewHistoryFormatter._section(
                "SUGGESTIONS", last.suggestions
            )
        )
