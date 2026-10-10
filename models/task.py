from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from models.compile_result import CompileResult
from models.generated_file import GeneratedFile
from models.git_diff import GitDiff
from models.git_operation import GitOperation
from models.git_push_operation import GitPushOperation
from models.github_issue import IssueLink
from models.pipeline_step import PipelineStep
from models.pull_request_info import PullRequestInfo
from models.review_history import (
    ReviewHistory,
)
from models.task_status import TaskStatus
from models.test_result import TestResult
from workflows.review_decision import (
    ReviewDecision,
)


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid4()))

    repository_id: str = ""

    # The backlog item this task serves, if any.
    issue: IssueLink = field(default_factory=IssueLink)

    # Kept alongside the id so a task can still find its
    # files after the repository row is deleted.
    repository_path: str = ""

    description: str = ""

    generated_code: str = ""

    architecture_review: str = ""

    architecture_score: int = 0

    generated_tests: str = ""

    recommendation: ReviewDecision = ReviewDecision.UNKNOWN

    blockers: list[str] = field(default_factory=list)

    warnings: list[str] = field(default_factory=list)

    suggestions: list[str] = field(default_factory=list)

    structural: list[str] = field(default_factory=list)

    review_iterations: int = 0

    review_history: list[ReviewHistory] = field(default_factory=list)

    generated_files: list[GeneratedFile] = field(default_factory=list)

    git_operation: GitOperation = field(
        default_factory=GitOperation
    )

    git_push: GitPushOperation = field(
        default_factory=GitPushOperation
    )

    pull_request: PullRequestInfo = field(
        default_factory=PullRequestInfo
    )

    test_result: TestResult = field(
        default_factory=TestResult
    )

    # What the reviewer was shown before approving.
    diffs: list[GitDiff] = field(default_factory=list)

    # Scaffolding this run wrote into the repository before
    # any code was generated. Recorded because it is a
    # change to someone's folder that nothing else would
    # mention: a repair nobody is told about is worse than
    # no repair.
    environment: list[str] = field(default_factory=list)

    # What the pipeline did, in order. Kept because a run
    # is a dozen decisions and the only other record of
    # them was a console window.
    steps: list[PipelineStep] = field(
        default_factory=list
    )

    compile_result: CompileResult = field(
        default_factory=CompileResult
    )

    status: TaskStatus = TaskStatus.NEW

    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
