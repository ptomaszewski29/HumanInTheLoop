import json
import sqlite3

from config.settings import Settings
from models.github_issue import IssueLink
from models.plan import Plan
from models.task_breakdown import Priority, TaskBreakdown
from models.task_execution import (
    ExecutionStatus,
    TaskExecution,
)

COLUMNS = (
    "id",
    "repository_id",
    "requirement_id",
    "issue",
    "epic",
    "tasks",
    "completed",
    "executions",
    "issues",
    "created_at",
)

COLUMN_LIST = ",\n                ".join(COLUMNS)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)

# Columns added after the table first shipped, with the
# definition used to retrofit an existing database.
ADDED_COLUMNS = {
    "executions": "TEXT NOT NULL DEFAULT '[]'",
    "issues": "TEXT NOT NULL DEFAULT '[]'",
    "requirement_id": "TEXT NOT NULL DEFAULT ''",
    "issue": "TEXT NOT NULL DEFAULT '{}'",
}


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
                requirement_id TEXT NOT NULL DEFAULT '',
                issue TEXT NOT NULL DEFAULT '{}',
                epic TEXT NOT NULL,
                tasks TEXT NOT NULL DEFAULT '[]',
                completed TEXT NOT NULL DEFAULT '[]',
                executions TEXT NOT NULL DEFAULT '[]',
                issues TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

        self.migrate()

    def migrate(self) -> None:

        cursor = self.connection.cursor()

        columns = {
            row[1]
            for row in cursor.execute(
                "PRAGMA table_info(plans)"
            )
        }

        for name, definition in ADDED_COLUMNS.items():

            if name in columns:
                continue

            cursor.execute(
                f"ALTER TABLE plans ADD COLUMN "
                f"{name} {definition}"
            )

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

    def _executions_json(self, plan: Plan) -> str:

        return json.dumps(
            [
                {
                    "task_id": item.task_id,
                    "status": item.status.value,
                    "started_at": item.started_at,
                    "completed_at": item.completed_at,
                    "error": item.error,
                    "task_record_id": item.task_record_id,
                }
                for item in plan.executions
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
                plan.requirement_id,
                json.dumps(
                    {
                        "id": plan.issue.id,
                        "number": plan.issue.number,
                        "title": plan.issue.title,
                        "state": plan.issue.state,
                        "url": plan.issue.url,
                    }
                ),
                plan.epic,
                self._tasks_json(plan),
                json.dumps(plan.completed),
                self._executions_json(plan),
                json.dumps(plan.issues),
                plan.created_at,
            ),
        )

        self.connection.commit()

    def update_progress(self, plan: Plan) -> None:
        """Records what has been attempted and how it went."""

        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE plans
            SET executions = ?, completed = ?
            WHERE id = ?
            """,
            (
                self._executions_json(plan),
                json.dumps(plan.completed),
                plan.id,
            ),
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

    def _parse_executions(
        self,
        executions_json: str,
        completed_json: str,
    ) -> list[TaskExecution]:
        """Execution records, or a stand-in for old rows.

        Plans saved before executions existed only knew
        which tasks had finished, so those are turned into
        completed records rather than losing the progress.
        """

        records = json.loads(executions_json or "[]")

        if records:

            return [
                TaskExecution(
                    task_id=int(item.get("task_id") or 0),
                    status=ExecutionStatus.parse(
                        item.get("status", "")
                    ),
                    started_at=item.get("started_at", ""),
                    completed_at=item.get(
                        "completed_at", ""
                    ),
                    error=item.get("error", ""),
                    task_record_id=item.get(
                        "task_record_id", ""
                    ),
                )
                for item in records
            ]

        return [
            TaskExecution(
                task_id=int(task_id),
                status=ExecutionStatus.COMPLETED,
            )
            for task_id in json.loads(
                completed_json or "[]"
            )
        ]

    def _parse_issue(self, issue_json: str) -> IssueLink:
        data = json.loads(issue_json or "{}")

        return IssueLink(
            id=int(data.get("id") or 0),
            number=int(data.get("number") or 0),
            title=data.get("title", ""),
            state=data.get("state", ""),
            url=data.get("url", ""),
        )

    def _to_plan(self, row: tuple) -> Plan:

        return Plan(
            id=row[0],
            repository_id=row[1],
            requirement_id=row[2],
            issue=self._parse_issue(row[3]),
            epic=row[4],
            tasks=self._parse_tasks(row[5]),
            executions=self._parse_executions(
                row[7],
                row[6],
            ),
            issues=json.loads(row[8] or "[]"),
            created_at=row[9],
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
