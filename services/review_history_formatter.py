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

        lines: list[str] = []

        for review in review_history:

            lines.append(f"""
Iteration {review.iteration}

Score:
{review.score}

Recommendation:
{review.recommendation.value}

Review:
{review.review}

--------------------------
""")

        return "\n".join(lines)
