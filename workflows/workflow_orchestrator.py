from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent

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

        print("=" * 80)
        print("DEVELOPER")
        print("=" * 80)

        generated_code = self.developer.execute(task_description)

        if not generated_code.strip():

            raise RuntimeError("DeveloperAgent returned empty code.")

        print("=" * 80)
        print("ARCHITECT")
        print("=" * 80)

        architecture_review = self.architect.execute(
            task_description,
            generated_code,
        )

        review_iterations += 1

        print(f"RECOMMENDATION: " f"{architecture_review.recommendation.value}")

        # ==================================================
        # FEEDBACK LOOP
        # ==================================================

        if architecture_review.recommendation == ReviewDecision.REQUEST_CHANGES:

            print("=" * 80)
            print("DEVELOPER FIX")
            print("=" * 80)

            generated_code = self.developer.execute(f"""
You previously implemented the following task:

{task_description}

The software architect reviewed your work
and requested changes.

ARCHITECT FEEDBACK:

{architecture_review.review}

CURRENT IMPLEMENTATION:

{generated_code}

Your responsibility:

1. Fix all findings.
2. Improve code quality.
3. Keep existing functionality.
4. Return only the improved TypeScript code.
""")

            if not generated_code.strip():

                raise RuntimeError("DeveloperAgent fix returned empty code.")

            print("=" * 80)
            print("ARCHITECT RE-REVIEW")
            print("=" * 80)

            architecture_review = self.architect.execute(
                task_description,
                generated_code,
            )

            review_iterations += 1

            print(f"RECOMMENDATION: " f"{architecture_review.recommendation.value}")

        # ==================================================
        # QA
        # ==================================================

        print("=" * 80)
        print("QA")
        print("=" * 80)

        generated_tests = self.qa.execute(generated_code)

        task = Task(
            description=task_description,
            generated_code=generated_code,
            architecture_review=architecture_review.review,
            architecture_score=architecture_review.score,
            recommendation=architecture_review.recommendation,
            generated_tests=generated_tests,
            review_iterations=review_iterations,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

        print("=" * 80)
        print("TASK OBJECT")
        print("=" * 80)

        print(f"review length: " f"{len(task.architecture_review)}")

        print(f"tests length: " f"{len(task.generated_tests)}")

        print(f"score: " f"{task.architecture_score}")

        print(f"recommendation: " f"{task.recommendation.value}")

        print(f"iterations: " f"{task.review_iterations}")

        return task
