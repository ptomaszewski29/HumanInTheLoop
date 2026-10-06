import sqlite3

from models.task import Task
from models.task_status import TaskStatus


class TaskRepository:
    def __init__(
        self,
        db_name: str = "human_in_the_loop.db",
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
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.description,
                task.generated_code,
                task.status.value,
                task.created_at,
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
                    status=TaskStatus(row[3]),
                    created_at=row[4],
                )
            )

        return tasks
