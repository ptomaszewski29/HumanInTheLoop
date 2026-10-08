import json
import sqlite3

from config.settings import Settings
from models.github_issue import IssueLink
from models.requirement import Requirement, RequirementSource

COLUMNS = (
    "id",
    "repository_id",
    "title",
    "content",
    "source",
    "issue",
    "created_at",
    "updated_at",
)

COLUMN_LIST = ",\n                ".join(COLUMNS)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)


class RequirementRepository:
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
            CREATE TABLE IF NOT EXISTS requirements (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'MANUAL',
                issue TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

    def _issue_json(self, requirement: Requirement) -> str:

        return json.dumps(
            {
                "id": requirement.issue.id,
                "number": requirement.issue.number,
                "title": requirement.issue.title,
                "state": requirement.issue.state,
                "url": requirement.issue.url,
            }
        )

    def save(self, requirement: Requirement) -> None:
        """Writes a requirement, replacing an earlier one."""

        cursor = self.connection.cursor()

        cursor.execute(
            f"""
            INSERT OR REPLACE INTO requirements (
                {COLUMN_LIST}
            )
            VALUES (
                {PLACEHOLDERS}
            )
            """,
            (
                requirement.id,
                requirement.repository_id,
                requirement.title,
                requirement.content,
                requirement.source.value,
                self._issue_json(requirement),
                requirement.created_at,
                requirement.updated_at,
            ),
        )

        self.connection.commit()

    def delete(self, requirement_id: str) -> None:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            DELETE FROM requirements
            WHERE id = ?
            """,
            (requirement_id,),
        )

        self.connection.commit()

    def _to_requirement(self, row: tuple) -> Requirement:

        issue = json.loads(row[5] or "{}")

        return Requirement(
            id=row[0],
            repository_id=row[1],
            title=row[2],
            content=row[3],
            source=RequirementSource.parse(row[4]),
            issue=IssueLink(
                id=int(issue.get("id") or 0),
                number=int(issue.get("number") or 0),
                title=issue.get("title", ""),
                state=issue.get("state", ""),
                url=issue.get("url", ""),
            ),
            created_at=row[6],
            updated_at=row[7],
        )

    def get_all(self) -> list[Requirement]:

        cursor = self.connection.cursor()

        rows = cursor.execute(f"""
            SELECT
                {COLUMN_LIST}
            FROM requirements
            ORDER BY updated_at DESC
            """).fetchall()

        return [self._to_requirement(row) for row in rows]

    def get_by_id(
        self,
        requirement_id: str,
    ) -> Requirement | None:

        cursor = self.connection.cursor()

        row = cursor.execute(
            f"""
            SELECT
                {COLUMN_LIST}
            FROM requirements
            WHERE id = ?
            """,
            (requirement_id,),
        ).fetchone()

        if row is None:
            return None

        return self._to_requirement(row)

    def get_by_issue(
        self,
        number: int,
    ) -> Requirement | None:
        """The requirement imported from an issue, if any.

        Importing the same issue twice should update one
        requirement rather than pile up duplicates.
        """

        for requirement in self.get_all():

            if requirement.issue.number == number:
                return requirement

        return None
