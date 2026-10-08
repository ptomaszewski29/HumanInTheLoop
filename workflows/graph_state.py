import operator
from typing import Annotated, TypedDict

from models.review_history import (
    ReviewHistory,
)


class GraphState(TypedDict):
    task_description: str

    generated_code: str

    architecture_review: str

    architecture_score: int

    recommendation: str

    generated_tests: str

    review_iterations: int

    review_history: Annotated[
        list[ReviewHistory],
        operator.add,
    ]
