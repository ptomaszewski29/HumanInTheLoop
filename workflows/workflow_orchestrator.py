from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from config.settings import Settings
from models.file_generation_result import (
    FileGenerationResult,
)
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.review_history import (
    ReviewHistory,
)
from models.task import Task
from models.task_status import TaskStatus
from services.file_naming import FileNaming
from services.file_writer import FileWriter
from services.review_history_formatter import (
    ReviewHistoryFormatter,
)
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
        repository_id: str = "",
        repository_path: str = "",
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
                    resolved=architecture_review.resolved,
                    blockers=architecture_review.blockers,
                    warnings=architecture_review.warnings,
                    suggestions=architecture_review.suggestions,
                )
            )

            # Only blockers send the code back to the
            # developer. Warnings and suggestions are
            # recorded and shipped with the task.
            if not architecture_review.blockers:
                break

            if architecture_review.recommendation == ReviewDecision.REJECT:
                break

            generated_code = self.developer.execute(f"""
Improve the code according
to architect feedback.

Original task:

{task_description}

Fix every BLOCKER. Address the warnings
only if that does not risk a blocker.
Ignore the suggestions.

{ReviewHistoryFormatter.open_findings(review_history)}

Current implementation:

{generated_code}

Return only TypeScript code.
""")

        generated_tests = self.qa.execute(generated_code)

        generated_files = self.write_files(
            repository_path,
            task_description,
            generated_code,
            generated_tests,
        )

        return Task(
            repository_id=repository_id,
            repository_path=repository_path,
            description=task_description,
            generated_code=generated_code,
            architecture_review=architecture_review.review,
            architecture_score=architecture_review.score,
            recommendation=architecture_review.recommendation,
            blockers=architecture_review.blockers,
            warnings=architecture_review.warnings,
            suggestions=architecture_review.suggestions,
            generated_tests=generated_tests,
            review_iterations=review_iterations,
            review_history=review_history,
            generated_files=generated_files,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

    def write_files(
        self,
        repository_path: str,
        task_description: str,
        generated_code: str,
        generated_tests: str,
    ) -> list[GeneratedFile]:
        """Writes the run's artifacts into the repository.

        Nothing is written when no repository folder was
        given, so the workflow still runs standalone.
        """

        if not repository_path:
            return []

        results = [
            FileGenerationResult(
                relative_path=FileNaming.code_path(
                    generated_code,
                    task_description,
                ),
                content=generated_code,
                file_type=FileType.CODE,
            ),
        ]

        if generated_tests.strip():

            results.append(
                FileGenerationResult(
                    relative_path=FileNaming.test_path(
                        generated_code,
                        task_description,
                    ),
                    content=generated_tests,
                    file_type=FileType.TEST,
                )
            )

        return FileWriter.write_all(
            repository_path,
            results,
        )
