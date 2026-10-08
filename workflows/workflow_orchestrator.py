from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from config.settings import Settings
from models.review_history import (
    ReviewHistory,
)
from models.task import Task
from models.task_status import TaskStatus
from workflows.review_decision import (
    ReviewDecision,
)


class WorkflowOrchestrator:
    def __init__(
        self,
    ) -> None:

        self.developer = DeveloperAgent()

        self.architect = ArchitectAgent()

        self.qa = QAAgent()

    def execute(
        self,
        task_description: str,
    ) -> Task:

        review_iterations = 0

        review_history: list[ReviewHistory] = []

        generated_code = self.developer.execute(task_description)

        if not generated_code.strip():

            raise RuntimeError("DeveloperAgent returned empty code.")

        architecture_review = None

        while review_iterations < Settings.MAX_REVIEW_LOOPS:

            architecture_review = self.architect.execute(
                task_description,
                generated_code,
                review_history,
            )

            review_iterations += 1

            review_history.append(
                ReviewHistory(
                    iteration=review_iterations,
                    score=architecture_review.score,
                    recommendation=architecture_review.recommendation,
                    review=architecture_review.review,
                )
            )

            if architecture_review.recommendation == ReviewDecision.APPROVE:
                break

            if architecture_review.recommendation == ReviewDecision.REJECT:
                break

            generated_code = self.developer.execute(f"""
Improve the code according
to architect feedback.

Original task:

{task_description}

Architect review:

{architecture_review.review}

Current implementation:

{generated_code}

Fix every architect finding.

Return only TypeScript code.
""")

        generated_tests = self.qa.execute(generated_code)

        return Task(
            description=task_description,
            generated_code=generated_code,
            architecture_review=architecture_review.review,
            architecture_score=architecture_review.score,
            recommendation=architecture_review.recommendation,
            generated_tests=generated_tests,
            review_iterations=review_iterations,
            review_history=review_history,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )
