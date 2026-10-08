import re

from models.architecture_review import (
    ArchitectureReview,
)
from models.review_history import (
    ReviewHistory,
)
from services.llm_factory import (
    LLMFactory,
)
from services.review_history_formatter import (
    ReviewHistoryFormatter,
)
from workflows.review_decision import (
    ReviewDecision,
)


class ArchitectAgent:
    def __init__(
        self,
    ) -> None:

        self.llm = (
            LLMFactory.create()
        )

    def execute(
        self,
        task_description: str,
        generated_code: str,
        review_history: list[
            ReviewHistory
        ] | None = None,
    ) -> ArchitectureReview:

        history = review_history or []

        history_text = (
            ReviewHistoryFormatter.format(
                history
            )
        )

        prompt = f"""
You are a Senior Software Architect.

Task:
{task_description}

Previous Reviews:

{history_text}

Current Code:

{generated_code}

Your responsibility:

1. Decide which previous findings are now resolved.
2. Decide which previous findings are still unresolved.
3. Identify new findings only if they really exist.
4. Decide whether the implementation can be approved.

Review the code critically. Check that
every requirement in the task is actually
implemented, that the code would compile
and run, and that the stated design
principles are really applied.

Rules:

- If there are no previous reviews, this is
  a first review: review the code from
  scratch, leave Resolved Findings as
  "None", and list every real problem you
  find under New Findings.
- Otherwise, take every finding listed in
  the most recent previous review one by
  one and decide its fate: each one goes
  either under Resolved Findings or under
  Remaining Findings. Never silently drop
  a previous finding.
- A finding is resolved as soon as the
  current code addresses it, even if the
  solution is not perfect. Do not repeat a
  finding as unresolved if the current code
  already fixes it.
- New Findings is only for problems that no
  previous review mentioned.
- Raise the score when findings are resolved.
- Recommend APPROVE only when no finding
  blocks the task requirements. Never
  approve code that is broken or ignores a
  stated requirement.
- Use REQUEST_CHANGES whenever at least one
  blocking finding remains.
- Reserve a score above 90 for code you
  would merge unchanged.
- Report "None" under a heading only when
  that heading genuinely has no entries.

Return exactly in this format:

SCORE: <0-100>

RECOMMENDATION:
<APPROVE|REQUEST_CHANGES|REJECT>

REVIEW:

Resolved Findings:
- finding

Remaining Findings:
- finding

New Findings:
- finding
"""

        raw_review = (
            self.llm.generate_text(
                prompt
            )
        )

        score_match = re.search(
            r"SCORE:\s*(\d+)",
            raw_review,
        )

        recommendation_match = (
            re.search(
                (
                    r"RECOMMENDATION:\s*"
                    r"(APPROVE|REQUEST_CHANGES|REJECT)"
                ),
                raw_review,
            )
        )

        score = (
            int(score_match.group(1))
            if score_match
            else 0
        )

        recommendation = (
            ReviewDecision(
                recommendation_match.group(
                    1
                )
            )
            if recommendation_match
            else ReviewDecision.UNKNOWN
        )

        review_text = (
            raw_review.split(
                "REVIEW:"
            )[-1].strip()
        )

        print("=" * 80)
        print(
            "ARCHITECT RAW RESULT "
            f"(iteration {len(history) + 1}, "
            f"{len(history)} previous reviews)"
        )
        print("=" * 80)
        print(raw_review)
        print("=" * 80)

        return ArchitectureReview(
            score=score,
            recommendation=recommendation,
            review=review_text,
        )
