from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from models.task import Task
from models.task_status import TaskStatus


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

        print("=" * 80)
        print("DEVELOPER")
        print("=" * 80)

        generated_code = self.developer.execute(task_description)

        if not generated_code.strip():
            raise RuntimeError(
                "DeveloperAgent returned no code - "
                "aborting before architect and QA."
            )

        print(generated_code)

        print("=" * 80)
        print("ARCHITECT")
        print("=" * 80)

        architecture_review = self.architect.execute(
            task_description,
            generated_code,
        )

        print(architecture_review.to_markdown())

        print("=" * 80)
        print("QA")
        print("=" * 80)

        generated_tests = self.qa.execute(generated_code)

        print(generated_tests)

        task = Task(
            description=task_description,
            generated_code=generated_code,
            architecture_review=architecture_review.to_markdown(),
            generated_tests=generated_tests,
            architecture_score=architecture_review.score,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

        print("=" * 80)
        print("TASK OBJECT")
        print("=" * 80)

        print(f"code length: " f"{len(task.generated_code)}")

        print(f"review length: " f"{len(task.architecture_review)}")

        print(f"score: " f"{task.architecture_score}/100")

        print(
            f"recommendation: "
            f"{architecture_review.recommendation.value}"
        )

        print(f"tests length: " f"{len(task.generated_tests)}")

        return task
