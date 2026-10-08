import os
import sqlite3

from config.settings import Settings
from models.repository import Repository


def same_path(left: str, right: str) -> bool:
    """True when two spellings point at one folder."""

    if not left or not right:
        return False

    return os.path.normcase(
        os.path.abspath(left)
    ) == os.path.normcase(os.path.abspath(right))

COLUMNS = (
    "id",
    "name",
    "path",
    "created_at",
)

COLUMN_LIST = ",\n                ".join(COLUMNS)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)


class RepositoryRepository:
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
            CREATE TABLE IF NOT EXISTS repositories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

    def save(
        self,
        repository: Repository,
    ) -> None:

        cursor = self.connection.cursor()

        cursor.execute(
            f"""
            INSERT INTO repositories (
                {COLUMN_LIST}
            )
            VALUES (
                {PLACEHOLDERS}
            )
            """,
            (
                repository.id,
                repository.name,
                repository.path,
                repository.created_at,
            ),
        )

        self.connection.commit()

    def _to_repository(
        self,
        row: tuple,
    ) -> Repository:

        return Repository(
            id=row[0],
            name=row[1],
            path=row[2],
            created_at=row[3],
        )

    def get_all(
        self,
    ) -> list[Repository]:

        cursor = self.connection.cursor()

        rows = cursor.execute(f"""
            SELECT
                {COLUMN_LIST}
            FROM repositories
            ORDER BY name COLLATE NOCASE
            """).fetchall()

        return [self._to_repository(row) for row in rows]

    def get_by_id(
        self,
        repository_id: str,
    ) -> Repository | None:

        cursor = self.connection.cursor()

        row = cursor.execute(
            f"""
            SELECT
                {COLUMN_LIST}
            FROM repositories
            WHERE id = ?
            """,
            (repository_id,),
        ).fetchone()

        if row is None:
            return None

        return self._to_repository(row)

    def get_by_path(
        self,
        path: str,
    ) -> Repository | None:
        """The repository for a folder, however it is typed."""

        for repository in self.get_all():

            if same_path(repository.path, path):
                return repository

        return None

    def delete(
        self,
        repository_id: str,
    ) -> None:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            DELETE FROM repositories
            WHERE id = ?
            """,
            (repository_id,),
        )

        self.connection.commit()
