import operator
from typing import Annotated, TypedDict

from models.generated_file import GeneratedFile
from models.review_history import (
    ReviewHistory,
)


class GraphState(TypedDict):
    task_description: str

    source_files: list[GeneratedFile]

    architecture_review: str

    architecture_score: int

    recommendation: str

    blockers: list[str]

    warnings: list[str]

    suggestions: list[str]

    test_files: list[GeneratedFile]

    review_iterations: int

    review_history: Annotated[
        list[ReviewHistory],
        operator.add,
    ]
