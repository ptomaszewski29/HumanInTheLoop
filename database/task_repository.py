import json
import sqlite3

from config.settings import Settings
from models.review_history import ReviewHistory
from models.task import Task
from models.task_status import TaskStatus
from workflows.review_decision import (
    ReviewDecision,
)


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
                description TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                architecture_review TEXT NOT NULL,
                architecture_score INTEGER NOT NULL,
                generated_tests TEXT NOT NULL,
                recommendation TEXT NOT NULL DEFAULT 'UNKNOWN',
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

        if "recommendation" not in columns:
            cursor.execute("""
                ALTER TABLE tasks
                ADD COLUMN recommendation
                TEXT NOT NULL
                DEFAULT 'UNKNOWN'
                """)

        if "review_history" not in columns:
            cursor.execute("""
                ALTER TABLE tasks
                ADD COLUMN review_history
                TEXT NOT NULL
                DEFAULT '[]'
                """)

        if "review_iterations" not in columns:
            cursor.execute("""
                ALTER TABLE tasks
                ADD COLUMN review_iterations
                INTEGER NOT NULL
                DEFAULT 0
                """)

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
                }
                for item in task.review_history
            ]
        )

        cursor = self.connection.cursor()

        cursor.execute(
            """
            INSERT INTO tasks (
                id,
                description,
                generated_code,
                architecture_review,
                architecture_score,
                generated_tests,
                recommendation,
                review_history,
                review_iterations,
                status,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                task.id,
                task.description,
                task.generated_code,
                task.architecture_review,
                task.architecture_score,
                task.generated_tests,
                task.recommendation.value,
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
            )
            for item in items
        ]

    def get_all(
        self,
    ) -> list[Task]:

        cursor = self.connection.cursor()

        rows = cursor.execute("""
            SELECT
                id,
                description,
                generated_code,
                architecture_review,
                architecture_score,
                generated_tests,
                recommendation,
                review_history,
                review_iterations,
                status,
                created_at
            FROM tasks
            ORDER BY created_at DESC
            """).fetchall()

        tasks: list[Task] = []

        for row in rows:

            tasks.append(
                Task(
                    id=row[0],
                    description=row[1],
                    generated_code=row[2],
                    architecture_review=row[3],
                    architecture_score=row[4],
                    generated_tests=row[5],
                    recommendation=ReviewDecision(row[6]),
                    review_history=self._parse_review_history(row[7]),
                    review_iterations=row[8],
                    status=TaskStatus(row[9]),
                    created_at=row[10],
                )
            )

        return tasks

    def get_by_id(
        self,
        task_id: str,
    ) -> Task | None:

        cursor = self.connection.cursor()

        row = cursor.execute(
            """
            SELECT
                id,
                description,
                generated_code,
                architecture_review,
                architecture_score,
                generated_tests,
                recommendation,
                review_history,
                review_iterations,
                status,
                created_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if row is None:
            return None

        return Task(
            id=row[0],
            description=row[1],
            generated_code=row[2],
            architecture_review=row[3],
            architecture_score=row[4],
            generated_tests=row[5],
            recommendation=ReviewDecision(row[6]),
            review_history=self._parse_review_history(row[7]),
            review_iterations=row[8],
            status=TaskStatus(row[9]),
            created_at=row[10],
        )
