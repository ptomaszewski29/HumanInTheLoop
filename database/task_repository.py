import sqlite3

from config.settings import Settings
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
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

        self.migrate()

    def migrate(self) -> None:
        """Add columns missing from tables created by older versions."""

        cursor = self.connection.cursor()

        columns = {
            row[1]
            for row in cursor.execute(
                "PRAGMA table_info(tasks)"
            )
        }

        if "recommendation" not in columns:
            cursor.execute("""
                ALTER TABLE tasks
                ADD COLUMN recommendation TEXT NOT NULL
                DEFAULT 'UNKNOWN'
                """)

        self.connection.commit()

    def save(
        self,
        task: Task,
    ) -> None:

        print("=" * 80)
        print("SAVING TASK")
        print("=" * 80)

        print(f"CODE LENGTH: {len(task.generated_code)}")

        print(f"REVIEW LENGTH: {len(task.architecture_review)}")

        print(f"TESTS LENGTH: {len(task.generated_tests)}")

        print("=" * 80)

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
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.description,
                task.generated_code,
                task.architecture_review,
                task.architecture_score,
                task.generated_tests,
                task.recommendation.value,
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
                    status=TaskStatus(row[7]),
                    created_at=row[8],
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
                status,
                created_at
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if row is None:
            return None

        task = Task(
            id=row[0],
            description=row[1],
            generated_code=row[2],
            architecture_review=row[3],
            architecture_score=row[4],
            generated_tests=row[5],
            recommendation=ReviewDecision(row[6]),
            status=TaskStatus(row[7]),
            created_at=row[8],
        )

        print("=" * 80)
        print("LOADING TASK")
        print("=" * 80)

        print(f"CODE LENGTH: {len(task.generated_code)}")

        print(f"REVIEW LENGTH: {len(task.architecture_review)}")

        print(f"TESTS LENGTH: {len(task.generated_tests)}")

        print("=" * 80)

        return task
