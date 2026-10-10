import json
import sqlite3

from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.git_diff import ChangeType, GitDiff
from models.git_operation import GitOperation
from models.git_push_operation import (
    GitPushOperation,
    PushStatus,
)
from models.github_issue import IssueLink
from models.pipeline_step import PipelineStep
from models.pull_request_info import (
    PullRequestInfo,
    PullRequestState,
)
from models.review_history import ReviewHistory
from models.task import Task
from models.task_status import TaskStatus
from models.test_result import TestResult, TestStatus
from workflows.review_decision import (
    ReviewDecision,
)

COLUMNS = (
    "id",
    "repository_id",
    "repository_path",
    "issue",
    "description",
    "generated_code",
    "architecture_review",
    "architecture_score",
    "generated_tests",
    "recommendation",
    "blockers",
    "warnings",
    "suggestions",
    "structural",
    "review_history",
    "review_iterations",
    "generated_files",
    "git_operation",
    "git_push",
    "pull_request",
    "test_result",
    "diffs",
    "status",
    "created_at",
    # Read positionally in _to_task, so a new column is
    # appended here and nowhere else: inserting one in the
    # middle silently shifts every field after it.
    "environment",
    "steps",
)

COLUMN_LIST = ",\n                ".join(COLUMNS)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)

# Columns added after the first release, with the
# definition used to retrofit older databases.
ADDED_COLUMNS = {
    "repository_id": "TEXT NOT NULL DEFAULT ''",
    "repository_path": "TEXT NOT NULL DEFAULT ''",
    "issue": "TEXT NOT NULL DEFAULT '{}'",
    "recommendation": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
    "blockers": "TEXT NOT NULL DEFAULT '[]'",
    "warnings": "TEXT NOT NULL DEFAULT '[]'",
    "suggestions": "TEXT NOT NULL DEFAULT '[]'",
    "structural": "TEXT NOT NULL DEFAULT '[]'",
    "environment": "TEXT NOT NULL DEFAULT '[]'",
    "steps": "TEXT NOT NULL DEFAULT '[]'",
    "review_history": "TEXT NOT NULL DEFAULT '[]'",
    "review_iterations": "INTEGER NOT NULL DEFAULT 0",
    "generated_files": "TEXT NOT NULL DEFAULT '[]'",
    "git_operation": "TEXT NOT NULL DEFAULT '{}'",
    "git_push": "TEXT NOT NULL DEFAULT '{}'",
    "pull_request": "TEXT NOT NULL DEFAULT '{}'",
    "test_result": "TEXT NOT NULL DEFAULT '{}'",
    "diffs": "TEXT NOT NULL DEFAULT '[]'",
}


class TaskRepository:
    def __init__(
        self,
        db_name: str = Settings.DATABASE_NAME,
    ) -> None:
        self.connection = sqlite3.connect(
            db_name,
            check_same_thread=False,
        )

        self.create_table()

    def create_table(self) -> None:
        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL DEFAULT '',
                repository_path TEXT NOT NULL DEFAULT '',
                issue TEXT NOT NULL DEFAULT '{}',
                description TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                architecture_review TEXT NOT NULL,
                architecture_score INTEGER NOT NULL,
                generated_tests TEXT NOT NULL,
                recommendation TEXT NOT NULL DEFAULT 'UNKNOWN',
                blockers TEXT NOT NULL DEFAULT '[]',
                warnings TEXT NOT NULL DEFAULT '[]',
                suggestions TEXT NOT NULL DEFAULT '[]',
                structural TEXT NOT NULL DEFAULT '[]',
                review_history TEXT NOT NULL DEFAULT '[]',
                review_iterations INTEGER NOT NULL DEFAULT 0,
                generated_files TEXT NOT NULL DEFAULT '[]',
                git_operation TEXT NOT NULL DEFAULT '{}',
                git_push TEXT NOT NULL DEFAULT '{}',
                pull_request TEXT NOT NULL DEFAULT '{}',
                test_result TEXT NOT NULL DEFAULT '{}',
                diffs TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

        self.migrate()

    def migrate(self) -> None:
        cursor = self.connection.cursor()

        columns = {row[1] for row in cursor.execute("PRAGMA table_info(tasks)")}

        for name, definition in ADDED_COLUMNS.items():

            if name in columns:
                continue

            cursor.execute(
                f"ALTER TABLE tasks ADD COLUMN {name} {definition}"
            )

        self.connection.commit()

    def save(
        self,
        task: Task,
    ) -> None:

        review_history_json = json.dumps(
            [
                {
                    "iteration": item.iteration,
                    "score": item.score,
                    "recommendation": item.recommendation.value,
                    "review": item.review,
                    "resolved": item.resolved,
                    "blockers": item.blockers,
                    "warnings": item.warnings,
                    "suggestions": item.suggestions,
                    "structural": item.structural,
                }
                for item in task.review_history
            ]
        )

        generated_files_json = json.dumps(
            [
                {
                    "path": item.path,
                    "file_type": item.file_type.value,
                }
                for item in task.generated_files
            ]
        )

        git_operation_json = json.dumps(
            {
                "branch_name": task.git_operation.branch_name,
                "commit_hash": task.git_operation.commit_hash,
                "commit_message": task.git_operation.commit_message,
                "created_at": task.git_operation.created_at,
            }
        )

        git_push_json = json.dumps(
            {
                "branch_name": task.git_push.branch_name,
                "remote_name": task.git_push.remote_name,
                "remote_url": task.git_push.remote_url,
                "pushed_at": task.git_push.pushed_at,
                "status": task.git_push.status.value,
                "error": task.git_push.error,
            }
        )

        pull_request_json = json.dumps(
            {
                "id": task.pull_request.id,
                "url": task.pull_request.url,
                "branch": task.pull_request.branch,
                "base": task.pull_request.base,
                "state": task.pull_request.state.value,
                "created_at": task.pull_request.created_at,
                "error": task.pull_request.error,
            }
        )

        test_result_json = json.dumps(
            {
                "status": task.test_result.status.value,
                "total_tests": task.test_result.total_tests,
                "failed_tests": task.test_result.failed_tests,
                "duration_seconds": task.test_result.duration_seconds,
                "output": task.test_result.output,
                "executed_at": task.test_result.executed_at,
            }
        )

        diffs_json = json.dumps(
            [
                {
                    "file_path": item.file_path,
                    "change_type": item.change_type.value,
                }
                for item in task.diffs
            ]
        )

        cursor = self.connection.cursor()

        cursor.execute(
            f"""
            INSERT INTO tasks (
                {COLUMN_LIST}
            )
            VALUES (
                {PLACEHOLDERS}
            )
            """,
            (
                task.id,
                task.repository_id,
                task.repository_path,
                json.dumps(
                    {
                        "id": task.issue.id,
                        "number": task.issue.number,
                        "title": task.issue.title,
                        "state": task.issue.state,
                        "url": task.issue.url,
                    }
                ),
                task.description,
                task.generated_code,
                task.architecture_review,
                task.architecture_score,
                task.generated_tests,
                task.recommendation.value,
                json.dumps(task.blockers),
                json.dumps(task.warnings),
                json.dumps(task.suggestions),
                json.dumps(task.structural),
                review_history_json,
                task.review_iterations,
                generated_files_json,
                git_operation_json,
                git_push_json,
                pull_request_json,
                test_result_json,
                diffs_json,
                task.status.value,
                task.created_at,
                json.dumps(task.environment),
                json.dumps(
                    [
                        {
                            "name": step.name,
                            "detail": step.detail,
                            "at": step.at,
                            "seconds": step.seconds,
                            "ok": step.ok,
                        }
                        for step in task.steps
                    ]
                ),
            ),
        )

        self.connection.commit()

    def update_status(
        self,
        task_id: str,
        status: TaskStatus,
    ) -> None:
        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE tasks
            SET status = ?
            WHERE id = ?
            """,
            (
                status.value,
                task_id,
            ),
        )

        self.connection.commit()

    def update_git_operation(
        self,
        task_id: str,
        operation: GitOperation,
    ) -> None:
        """Records the branch and commit a task produced."""

        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE tasks
            SET git_operation = ?
            WHERE id = ?
            """,
            (
                json.dumps(
                    {
                        "branch_name": operation.branch_name,
                        "commit_hash": operation.commit_hash,
                        "commit_message": operation.commit_message,
                        "created_at": operation.created_at,
                    }
                ),
                task_id,
            ),
        )

        self.connection.commit()

    def update_git_push(
        self,
        task_id: str,
        operation: GitPushOperation,
    ) -> None:
        """Records the outcome of a push."""

        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE tasks
            SET git_push = ?
            WHERE id = ?
            """,
            (
                json.dumps(
                    {
                        "branch_name": operation.branch_name,
                        "remote_name": operation.remote_name,
                        "remote_url": operation.remote_url,
                        "pushed_at": operation.pushed_at,
                        "status": operation.status.value,
                        "error": operation.error,
                    }
                ),
                task_id,
            ),
        )

        self.connection.commit()

    def update_pull_request(
        self,
        task_id: str,
        info: PullRequestInfo,
    ) -> None:
        """Records the pull request a task produced."""

        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE tasks
            SET pull_request = ?
            WHERE id = ?
            """,
            (
                json.dumps(
                    {
                        "id": info.id,
                        "url": info.url,
                        "branch": info.branch,
                        "base": info.base,
                        "state": info.state.value,
                        "created_at": info.created_at,
                        "error": info.error,
                    }
                ),
                task_id,
            ),
        )

        self.connection.commit()

    def _parse_steps(
        self,
        steps_json: str,
    ) -> list[PipelineStep]:

        try:
            loaded = json.loads(steps_json or "[]")

        except (TypeError, ValueError):
            return []

        if not isinstance(loaded, list):
            return []

        return [
            PipelineStep(
                name=str(item.get("name", "")),
                detail=str(item.get("detail", "")),
                at=str(item.get("at", "")),
                seconds=float(item.get("seconds", 0) or 0),
                ok=bool(item.get("ok", True)),
            )
            for item in loaded
            if isinstance(item, dict)
        ]

    def _parse_findings(
        self,
        findings_json: str,
    ) -> list[str]:

        return json.loads(findings_json or "[]")

    def _parse_review_history(
        self,
        review_history_json: str,
    ) -> list[ReviewHistory]:
        items = json.loads(review_history_json or "[]")

        return [
            ReviewHistory(
                iteration=item["iteration"],
                score=item["score"],
                recommendation=ReviewDecision(item["recommendation"]),
                review=item["review"],
                resolved=item.get("resolved", []),
                blockers=item.get("blockers", []),
                warnings=item.get("warnings", []),
                suggestions=item.get("suggestions", []),
                structural=item.get("structural", []),
            )
            for item in items
        ]

    def _parse_generated_files(
        self,
        generated_files_json: str,
    ) -> list[GeneratedFile]:
        items = json.loads(generated_files_json or "[]")

        return [
            GeneratedFile(
                path=item["path"],
                file_type=FileType.parse(
                    item.get("file_type", "")
                ),
            )
            for item in items
        ]

    def _parse_git_operation(
        self,
        git_operation_json: str,
    ) -> GitOperation:
        data = json.loads(git_operation_json or "{}")

        if not data:
            return GitOperation()

        return GitOperation(
            branch_name=data.get("branch_name", ""),
            commit_hash=data.get("commit_hash", ""),
            commit_message=data.get("commit_message", ""),
            created_at=data.get("created_at", ""),
        )

    def _parse_git_push(
        self,
        git_push_json: str,
    ) -> GitPushOperation:
        data = json.loads(git_push_json or "{}")

        if not data:
            return GitPushOperation()

        return GitPushOperation(
            branch_name=data.get("branch_name", ""),
            remote_name=data.get("remote_name", ""),
            remote_url=data.get("remote_url", ""),
            pushed_at=data.get("pushed_at", ""),
            status=PushStatus.parse(
                data.get("status", "")
            ),
            error=data.get("error", ""),
        )

    def _parse_pull_request(
        self,
        pull_request_json: str,
    ) -> PullRequestInfo:
        data = json.loads(pull_request_json or "{}")

        if not data:
            return PullRequestInfo()

        return PullRequestInfo(
            id=int(data.get("id") or 0),
            url=data.get("url", ""),
            branch=data.get("branch", ""),
            base=data.get("base", ""),
            state=PullRequestState.parse(
                data.get("state", "")
            ),
            created_at=data.get("created_at", ""),
            error=data.get("error", ""),
        )

    def _parse_issue(self, issue_json: str) -> IssueLink:
        data = json.loads(issue_json or "{}")

        return IssueLink(
            id=int(data.get("id") or 0),
            number=int(data.get("number") or 0),
            title=data.get("title", ""),
            state=data.get("state", ""),
            url=data.get("url", ""),
        )

    def _parse_test_result(
        self,
        test_result_json: str,
    ) -> TestResult:
        data = json.loads(test_result_json or "{}")

        if not data:
            return TestResult()

        return TestResult(
            status=TestStatus.parse(
                data.get("status", "")
            ),
            total_tests=int(data.get("total_tests") or 0),
            failed_tests=int(
                data.get("failed_tests") or 0
            ),
            duration_seconds=float(
                data.get("duration_seconds") or 0.0
            ),
            output=data.get("output", ""),
            executed_at=data.get("executed_at", ""),
        )

    def _parse_diffs(
        self,
        diffs_json: str,
    ) -> list[GitDiff]:
        """The review evidence, without the diff bodies.

        Only the verdict per file is stored; the text is
        regenerated from the repository when shown.
        """

        return [
            GitDiff(
                file_path=item["file_path"],
                change_type=ChangeType.parse(
                    item.get("change_type", "")
                ),
            )
            for item in json.loads(diffs_json or "[]")
        ]

    def _to_task(
        self,
        row: tuple,
    ) -> Task:

        return Task(
            id=row[0],
            repository_id=row[1],
            repository_path=row[2],
            issue=self._parse_issue(row[3]),
            description=row[4],
            generated_code=row[5],
            architecture_review=row[6],
            architecture_score=row[7],
            generated_tests=row[8],
            recommendation=ReviewDecision(row[9]),
            blockers=self._parse_findings(row[10]),
            warnings=self._parse_findings(row[11]),
            suggestions=self._parse_findings(row[12]),
            structural=self._parse_findings(row[13]),
            review_history=self._parse_review_history(row[14]),
            review_iterations=row[15],
            generated_files=self._parse_generated_files(row[16]),
            git_operation=self._parse_git_operation(row[17]),
            git_push=self._parse_git_push(row[18]),
            pull_request=self._parse_pull_request(row[19]),
            test_result=self._parse_test_result(row[20]),
            diffs=self._parse_diffs(row[21]),
            status=TaskStatus(row[22]),
            created_at=row[23],
            environment=self._parse_findings(row[24]),
            steps=self._parse_steps(row[25]),
        )

    def get_all(
        self,
    ) -> list[Task]:

        cursor = self.connection.cursor()

        rows = cursor.execute(f"""
            SELECT
                {COLUMN_LIST}
            FROM tasks
            ORDER BY created_at DESC
            """).fetchall()

        return [self._to_task(row) for row in rows]

    def get_by_id(
        self,
        task_id: str,
    ) -> Task | None:

        cursor = self.connection.cursor()

        row = cursor.execute(
            f"""
            SELECT
                {COLUMN_LIST}
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if row is None:
            return None

        return self._to_task(row)
