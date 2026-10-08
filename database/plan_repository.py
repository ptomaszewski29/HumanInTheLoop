import json
import sqlite3

from config.settings import Settings
from models.plan import Plan
from models.task_breakdown import Priority, TaskBreakdown

COLUMNS = (
    "id",
    "repository_id",
    "epic",
    "tasks",
    "completed",
    "created_at",
)

COLUMN_LIST = ",\n                ".join(COLUMNS)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)


class PlanRepository:
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
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL DEFAULT '',
                epic TEXT NOT NULL,
                tasks TEXT NOT NULL DEFAULT '[]',
                completed TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

    def _tasks_json(self, plan: Plan) -> str:

        return json.dumps(
            [
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "priority": item.priority.value,
                    "dependencies": item.dependencies,
                }
                for item in plan.tasks
            ]
        )

    def save(self, plan: Plan) -> None:

        cursor = self.connection.cursor()

        cursor.execute(
            f"""
            INSERT INTO plans (
                {COLUMN_LIST}
            )
            VALUES (
                {PLACEHOLDERS}
            )
            """,
            (
                plan.id,
                plan.repository_id,
                plan.epic,
                self._tasks_json(plan),
                json.dumps(plan.completed),
                plan.created_at,
            ),
        )

        self.connection.commit()

    def update_completed(
        self,
        plan_id: str,
        completed: list[int],
    ) -> None:
        """Records which tasks of a plan have been run."""

        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE plans
            SET completed = ?
            WHERE id = ?
            """,
            (json.dumps(sorted(set(completed))), plan_id),
        )

        self.connection.commit()

    def delete(self, plan_id: str) -> None:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            DELETE FROM plans
            WHERE id = ?
            """,
            (plan_id,),
        )

        self.connection.commit()

    def _parse_tasks(
        self,
        tasks_json: str,
    ) -> list[TaskBreakdown]:

        return [
            TaskBreakdown(
                id=int(item.get("id") or 0),
                title=item.get("title", ""),
                description=item.get("description", ""),
                priority=Priority.parse(
                    item.get("priority", "")
                ),
                dependencies=[
                    int(value)
                    for value in item.get(
                        "dependencies", []
                    )
                ],
            )
            for item in json.loads(tasks_json or "[]")
        ]

    def _to_plan(self, row: tuple) -> Plan:

        return Plan(
            id=row[0],
            repository_id=row[1],
            epic=row[2],
            tasks=self._parse_tasks(row[3]),
            completed=json.loads(row[4] or "[]"),
            created_at=row[5],
        )

    def get_all(self) -> list[Plan]:

        cursor = self.connection.cursor()

        rows = cursor.execute(f"""
            SELECT
                {COLUMN_LIST}
            FROM plans
            ORDER BY created_at DESC
            """).fetchall()

        return [self._to_plan(row) for row in rows]

    def get_by_id(self, plan_id: str) -> Plan | None:

        cursor = self.connection.cursor()

        row = cursor.execute(
            f"""
            SELECT
                {COLUMN_LIST}
            FROM plans
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()

        if row is None:
            return None

        return self._to_plan(row)
