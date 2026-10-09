from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from agents.test_execution_agent import TestExecutionAgent
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
from services.bootstrap import bootstrap
from services.file_writer import FileWriter
from services.git_diff_service import GitDiffService
from services.repository_context import describe
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

        created = self.prepare(repository_path)

        source_files = self.developer.execute(
            task_description,
            repository_path,
        )

        if not source_files:

            raise RuntimeError("DeveloperAgent returned no files.")

        architecture_review = None

        while review_iterations < Settings.MAX_REVIEW_LOOPS:

            architecture_review = self.architect.execute(
                task_description,
                source_files,
                review_history,
                repository_path,
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

            # Structural problems and architecture
            # blockers both send the files back. Warnings
            # and suggestions are recorded and shipped.
            open_findings = (
                architecture_review.structural
                + architecture_review.blockers
            )

            if not open_findings:
                break

            if architecture_review.recommendation == ReviewDecision.REJECT:
                break

            source_files = self.developer.improve(
                task_description,
                source_files,
                self.fix_brief(architecture_review),
                repository_path,
            )

        test_files = self.qa.execute(source_files)

        generated_files = self.write_files(
            repository_path,
            source_files + test_files,
        )

        # Run what was just generated. A failure sends the
        # files back; a missing toolchain does not, because
        # the developer cannot install one.
        test_result = TestExecutionAgent.execute(
            repository_path
        )

        attempts = 0

        while (
            test_result.blocks_delivery
            and attempts < Settings.MAX_TEST_LOOPS
        ):

            attempts += 1

            source_files = self.developer.improve(
                task_description,
                source_files,
                TestExecutionAgent.fix_brief(
                    test_result,
                    source_files,
                    test_files,
                ),
                repository_path,
            )

            architecture_review = self.architect.execute(
                task_description,
                source_files,
                review_history,
                repository_path,
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

            test_files = self.qa.execute(source_files)

            generated_files = self.write_files(
                repository_path,
                source_files + test_files,
            )

            test_result = TestExecutionAgent.execute(
                repository_path
            )

        # What a reviewer will be asked to approve. Read
        # only: the files are already on disk, so this
        # compares them with what git has recorded.
        diffs = GitDiffService.compare(
            repository_path,
            [item.path for item in generated_files],
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
            test_result=test_result,
            diffs=diffs,
            environment=created,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

    @staticmethod
    def prepare(repository_path: str) -> list[str]:
        """Scaffolding, before a single task is written.

        Deterministic on purpose. The alternative was a
        planned task per config file, and one of those
        took twenty-three minutes of model time to produce
        a package.json.
        """

        if not Settings.AUTO_BOOTSTRAP:
            return []

        created = bootstrap(
            repository_path,
            describe(repository_path),
        )

        if created:
            print(
                "BOOTSTRAP: created "
                + ", ".join(created)
            )

        return created

    @staticmethod
    def fix_brief(review) -> str:
        """What the developer has to act on.

        Structural problems come first: they are facts
        about the files, while the rest is judgement.
        """

        parts: list[str] = []

        if review.structural:

            lines = "\n".join(
                f"- {finding}"
                for finding in review.structural
            )

            parts.append(
                "Repository problems found by a "
                "compiler-style pass:\n" + lines
            )

        # A cycle told as prose went unfixed for three
        # rounds running: the developer rewrites one file
        # at a time and cannot see which import closes the
        # loop. The validator can, so it says which one to
        # remove instead of describing the route.
        cuts = review.structure_report.cuts()

        if cuts:

            parts.append(
                "Do exactly this to break the cycles:\n"
                + "\n".join(f"- {cut}" for cut in cuts)
            )

        if review.review:
            parts.append(review.review)

        return "\n\n".join(parts)

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
