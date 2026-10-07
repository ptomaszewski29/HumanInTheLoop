import sqlite3

from config.settings import Settings
from models.task import Task
from models.task_status import TaskStatus


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
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

    def save(
        self,
        task: Task,
    ) -> None:
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
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.description,
                task.generated_code,
                task.architecture_review,
                task.architecture_score,
                task.generated_tests,
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
                    status=TaskStatus(row[6]),
                    created_at=row[7],
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
            status=TaskStatus(row[6]),
            created_at=row[7],
        )
