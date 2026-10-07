from dataclasses import dataclass

from models.architecture_recommendation import (
    ArchitectureRecommendation,
)


@dataclass
class ArchitectureReview:
    review: str = ""

    score: int = 0

    recommendation: ArchitectureRecommendation = (
        ArchitectureRecommendation.UNKNOWN
    )

    def to_markdown(
        self,
    ) -> str:
        """Render the review for storage and for the UI."""

        return (
            f"**Score:** {self.score}/100\n\n"
            f"**Recommendation:** "
            f"{self.recommendation.value}\n\n"
            f"{self.review}"
        )
