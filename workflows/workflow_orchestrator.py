from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from config.settings import Settings
from models.file_generation_result import (
    FileGenerationResult,
)
from models.generated_file import GeneratedFile
from models.review_history import (
    ReviewHistory,
)
from models.task import Task
from models.task_status import TaskStatus
from services.file_writer import FileWriter
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

        source_files = self.developer.execute(task_description)

        if not source_files:

            raise RuntimeError("DeveloperAgent returned no files.")

        architecture_review = None

        while review_iterations < Settings.MAX_REVIEW_LOOPS:

            architecture_review = self.architect.execute(
                task_description,
                source_files,
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
                    structural=architecture_review.structural,
                )
            )

            # Only blockers send the files back to the
            # developer. Warnings and suggestions are
            # recorded and shipped with the task.
            if not architecture_review.blockers:
                break

            if architecture_review.recommendation == ReviewDecision.REJECT:
                break

            source_files = self.developer.improve(
                task_description,
                source_files,
                architecture_review.review,
            )

        test_files = self.qa.execute(source_files)

        generated_files = self.write_files(
            repository_path,
            source_files + test_files,
        )

        return Task(
            repository_id=repository_id,
            repository_path=repository_path,
            description=task_description,
            architecture_review=architecture_review.review,
            architecture_score=architecture_review.score,
            recommendation=architecture_review.recommendation,
            blockers=architecture_review.blockers,
            warnings=architecture_review.warnings,
            suggestions=architecture_review.suggestions,
            structural=architecture_review.structural,
            review_iterations=review_iterations,
            review_history=review_history,
            generated_files=generated_files,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

    def write_files(
        self,
        repository_path: str,
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:
        """Writes the run's files into the repository.

        Nothing is written when no repository folder was
        given, so the workflow still runs standalone. A
        file whose path is unsafe is skipped rather than
        failing the whole run.
        """

        if not repository_path:
            return files

        written: list[GeneratedFile] = []

        for item in files:

            try:
                written.append(
                    FileWriter.write(
                        repository_path,
                        FileGenerationResult(
                            relative_path=item.path,
                            content=item.content,
                            file_type=item.file_type,
                        ),
                    )
                )

            except ValueError as error:
                print(f"SKIPPED {item.path}: {error}")

        if not written:
            raise RuntimeError(
                "No generated file could be written to "
                f"{repository_path}."
            )

        return written
