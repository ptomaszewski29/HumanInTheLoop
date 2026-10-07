import re

from models.architecture_recommendation import (
    ArchitectureRecommendation,
)
from models.architecture_review import (
    ArchitectureReview,
)
from services.llm_factory import LLMFactory

SCORE_PATTERN = re.compile(
    r"SCORE\s*:\s*(\d{1,3})",
    re.IGNORECASE,
)

RECOMMENDATION_PATTERN = re.compile(
    r"RECOMMENDATION\s*:\s*"
    r"(APPROVE|REQUEST_CHANGES|REJECT)",
    re.IGNORECASE,
)

REVIEW_PATTERN = re.compile(
    r"REVIEW\s*:\s*(.+)",
    re.IGNORECASE | re.DOTALL,
)


class ArchitectAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create()

    def execute(
        self,
        task_description: str,
        generated_code: str,
    ) -> ArchitectureReview:

        prompt = f"""
You are a senior software architect
reviewing TypeScript code.

Judge correctness, edge cases, typing,
naming and maintainability.

Task:
{task_description}

Code:
{generated_code}

Answer in exactly this format:

SCORE: <integer between 0 and 100>
RECOMMENDATION: <APPROVE or REQUEST_CHANGES or REJECT>
REVIEW:
- <finding>
- <finding>
- <finding>

Rules:
- maximum 6 bullet points
- each bullet is one sentence
- name a concrete strength or a concrete risk
- no code in the answer
"""

        result = self.llm.generate_text(prompt)

        review = self.parse(result)

        print("=" * 80)
        print("ARCHITECT RAW RESULT")
        print("=" * 80)
        print(repr(result))
        print("=" * 80)

        return review

    def parse(
        self,
        result: str,
    ) -> ArchitectureReview:
        """Turn the raw answer into a structured review.

        Falls back to the raw text so a model that ignores
        the format still produces a usable review.
        """

        return ArchitectureReview(
            review=self.parse_review(result),
            score=self.parse_score(result),
            recommendation=self.parse_recommendation(result),
        )

    def parse_score(
        self,
        result: str,
    ) -> int:

        match = SCORE_PATTERN.search(result)

        if match is None:
            return 0

        return min(
            int(match.group(1)),
            100,
        )

    def parse_recommendation(
        self,
        result: str,
    ) -> ArchitectureRecommendation:

        match = RECOMMENDATION_PATTERN.search(result)

        if match is None:
            return ArchitectureRecommendation.UNKNOWN

        return ArchitectureRecommendation(
            match.group(1).upper()
        )

    def parse_review(
        self,
        result: str,
    ) -> str:

        match = REVIEW_PATTERN.search(result)

        if match is None:
            return result.strip()

        return match.group(1).strip()
