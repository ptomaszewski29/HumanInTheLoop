from models.architecture_review import (
    ArchitectureReview,
)
from models.generated_file import GeneratedFile
from models.review_history import (
    ReviewHistory,
)
from services.file_bundle import FileBundle
from services.llm_factory import (
    LLMFactory,
)
from services.review_history_formatter import (
    ReviewHistoryFormatter,
)
from services.review_parser import (
    ReviewParser,
    drop_contradictions,
)
from workflows.recommendation_policy import (
    RecommendationPolicy,
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
        source_files: list[GeneratedFile],
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

Project Structure:

{FileBundle.structure(source_files)}

Current Code:

{FileBundle.render(source_files)}

Review the project structure as well as the
code. A file set should separate interfaces,
services and providers, and each file should
hold one logical component.

Classify every finding by severity.

BLOCKER
Prevents the solution from meeting
architectural, functional, security,
reliability or maintainability
requirements.

Always a BLOCKER, with no exception:

- the code would not compile or run
- the code is incomplete, truncated, or has
  unbalanced braces or brackets
- the code calls or references something
  that is not defined
- a requirement stated in the task is not
  implemented
- a security vulnerability
- a file imports something no file in the
  set defines

Also a BLOCKER: dependency inversion
violations, broken abstraction boundaries,
hard-coded infrastructure dependencies,
invalid business logic, missing required
interfaces, unbounded resource consumption.

WARNING
Should be fixed, but does not make the
implementation unacceptable. For example:
missing logging, weak naming, missing
documentation, limited extensibility,
non-optimal design choices, a file holding
several unrelated components.

SUGGESTION
Optional improvement. For example: pattern
recommendations, performance ideas, code
style, future-proofing.

Rules:

- Anything that stops the code from
  compiling, running, or meeting a stated
  requirement is a BLOCKER, however small
  the fix looks.
- For questions of design taste and
  polish only, when in doubt choose
  WARNING over BLOCKER.
- Missing logging, error handling, retries,
  metrics and tests are WARNINGS or
  SUGGESTIONS, never BLOCKERS, unless the
  task explicitly asked for them.
- "Could be more extensible" and "could be
  more generic" are SUGGESTIONS.
- If there are no previous reviews, review
  the code from scratch and leave RESOLVED
  FINDINGS as "None".
- Otherwise take every finding from the
  most recent previous review one by one.
  If the current code addresses it, list it
  under RESOLVED FINDINGS and do not repeat
  it. If it is not addressed, list it again
  under its severity. Never silently drop a
  previous finding.
- A finding counts as resolved as soon as
  the current code addresses it, even if
  the solution is not perfect.
- RESOLVED FINDINGS is only for findings
  that are genuinely fixed. Never list the
  same finding under RESOLVED FINDINGS and
  under a severity heading. Never write
  "(not resolved)" or a similar note there.
  Each finding appears under exactly one
  heading.
- Do not re-raise a finding you already
  listed as resolved in an earlier review.
- Raise the score when findings are
  resolved.
- Write "None" under a heading that has no
  entries.

Return exactly in this format, with no
extra commentary:

SCORE: <0-100>

RECOMMENDATION: <APPROVE|REQUEST_CHANGES|REJECT>

RESOLVED FINDINGS:
- previously raised finding that is now fixed

BLOCKERS:
- finding

WARNINGS:
- finding

SUGGESTIONS:
- finding
"""

        raw_review = (
            self.llm.generate_text(
                prompt
            )
        )

        score = ReviewParser.score(raw_review)

        resolved = ReviewParser.section(
            raw_review, "resolved"
        )

        blockers = ReviewParser.section(
            raw_review, "blockers"
        )

        warnings = ReviewParser.section(
            raw_review, "warnings"
        )

        suggestions = ReviewParser.section(
            raw_review, "suggestions"
        )

        # A finding cannot be resolved and open at
        # the same time; still being open wins.
        resolved = drop_contradictions(
            resolved,
            blockers + warnings + suggestions,
        )

        stated = ReviewParser.stated_recommendation(
            raw_review
        )

        recommendation = RecommendationPolicy.decide(
            blockers,
            ReviewDecision(stated) if stated else None,
        )

        review_text = self._render(
            resolved,
            blockers,
            warnings,
            suggestions,
        )

        print("=" * 80)
        print(
            "ARCHITECT RESULT "
            f"(iteration {len(history) + 1}, "
            f"{len(history)} previous reviews)"
        )
        print("=" * 80)
        print(
            f"score={score} "
            f"blockers={len(blockers)} "
            f"warnings={len(warnings)} "
            f"suggestions={len(suggestions)} "
            f"resolved={len(resolved)} "
            f"stated={stated} "
            f"-> {recommendation.value}"
        )
        print("=" * 80)
        print(raw_review)
        print("=" * 80)

        return ArchitectureReview(
            score=score,
            recommendation=recommendation,
            review=review_text,
            resolved=resolved,
            blockers=blockers,
            warnings=warnings,
            suggestions=suggestions,
        )

    @staticmethod
    def _render(
        resolved: list[str],
        blockers: list[str],
        warnings: list[str],
        suggestions: list[str],
    ) -> str:

        sections = (
            ("Resolved Findings", resolved),
            ("Blockers", blockers),
            ("Warnings", warnings),
            ("Suggestions", suggestions),
        )

        parts: list[str] = []

        for title, findings in sections:

            if findings:
                body = "\n".join(
                    f"- {finding}"
                    for finding in findings
                )
            else:
                body = "- None"

            parts.append(f"**{title}:**\n{body}")

        return "\n\n".join(parts)
