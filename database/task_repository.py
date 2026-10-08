import json
import sqlite3

from config.settings import Settings
from models.review_history import ReviewHistory
from models.task import Task
from models.task_status import TaskStatus
from workflows.review_decision import (
    ReviewDecision,
)

COLUMNS = (
    "id",
    "repository_id",
    "description",
    "generated_code",
    "architecture_review",
    "architecture_score",
    "generated_tests",
    "recommendation",
    "blockers",
    "warnings",
    "suggestions",
    "review_history",
    "review_iterations",
    "status",
    "created_at",
)

COLUMN_LIST = ",\n                ".join(COLUMNS)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)

# Columns added after the first release, with the
# definition used to retrofit older databases.
ADDED_COLUMNS = {
    "repository_id": "TEXT NOT NULL DEFAULT ''",
    "recommendation": "TEXT NOT NULL DEFAULT 'UNKNOWN'",
    "blockers": "TEXT NOT NULL DEFAULT '[]'",
    "warnings": "TEXT NOT NULL DEFAULT '[]'",
    "suggestions": "TEXT NOT NULL DEFAULT '[]'",
    "review_history": "TEXT NOT NULL DEFAULT '[]'",
    "review_iterations": "INTEGER NOT NULL DEFAULT 0",
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
                description TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                architecture_review TEXT NOT NULL,
                architecture_score INTEGER NOT NULL,
                generated_tests TEXT NOT NULL,
                recommendation TEXT NOT NULL DEFAULT 'UNKNOWN',
                blockers TEXT NOT NULL DEFAULT '[]',
                warnings TEXT NOT NULL DEFAULT '[]',
                suggestions TEXT NOT NULL DEFAULT '[]',
                review_history TEXT NOT NULL DEFAULT '[]',
                review_iterations INTEGER NOT NULL DEFAULT 0,
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
                }
                for item in task.review_history
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
                task.description,
                task.generated_code,
                task.architecture_review,
                task.architecture_score,
                task.generated_tests,
                task.recommendation.value,
                json.dumps(task.blockers),
                json.dumps(task.warnings),
                json.dumps(task.suggestions),
                review_history_json,
                task.review_iterations,
                task.status.value,
                task.created_at,
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
            )
            for item in items
        ]

    def _to_task(
        self,
        row: tuple,
    ) -> Task:

        return Task(
            id=row[0],
            repository_id=row[1],
            description=row[2],
            generated_code=row[3],
            architecture_review=row[4],
            architecture_score=row[5],
            generated_tests=row[6],
            recommendation=ReviewDecision(row[7]),
            blockers=self._parse_findings(row[8]),
            warnings=self._parse_findings(row[9]),
            suggestions=self._parse_findings(row[10]),
            review_history=self._parse_review_history(row[11]),
            review_iterations=row[12],
            status=TaskStatus(row[13]),
            created_at=row[14],
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
