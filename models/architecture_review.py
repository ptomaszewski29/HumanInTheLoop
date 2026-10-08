from dataclasses import dataclass, field

from models.structure_report import StructureReport
from workflows.review_decision import (
    ReviewDecision,
)


@dataclass
class ArchitectureReview:
    score: int

    recommendation: ReviewDecision

    review: str

    resolved: list[str] = field(default_factory=list)

    blockers: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    suggestions: list[str] = field(default_factory=list)

    structural: list[str] = field(default_factory=list)

    structure_report: StructureReport = field(
        default_factory=StructureReport
    )
