"""Offline checks for repository awareness.

Runs without an LLM:

    python -m tests.repository_test
"""

import os
import tempfile

from database.repository_repository import (
    RepositoryRepository,
)
from database.task_repository import TaskRepository
from models.repository import Repository
from models.task import Task

failures: list[str] = []


def check(
    label: str,
    actual: object,
    expected: object,
) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


database = os.path.join(
    tempfile.mkdtemp(),
    "repository_test.db",
)

repositories = RepositoryRepository(database)

print("=" * 80)
print("REPOSITORY CRUD")
print("=" * 80)

check("starts empty", repositories.get_all(), [])

frontend = Repository(
    name="Frontend",
    path="C:/Projects/Frontend",
)

backend = Repository(
    name="Backend",
    path="C:/Projects/Backend",
)

repositories.save(frontend)
repositories.save(backend)

check("both saved", len(repositories.get_all()), 2)

check(
    "sorted by name",
    [item.name for item in repositories.get_all()],
    ["Backend", "Frontend"],
)

loaded = repositories.get_by_id(frontend.id)

check("loaded by id", loaded.name, "Frontend")

check("path round trip", loaded.path, "C:/Projects/Frontend")

check("id round trip", loaded.id, frontend.id)

check(
    "created_at round trip",
    loaded.created_at,
    frontend.created_at,
)

check(
    "missing id returns None",
    repositories.get_by_id("does-not-exist"),
    None,
)

repositories.delete(backend.id)

check("deleted", len(repositories.get_all()), 1)

check(
    "deleted one is gone",
    repositories.get_by_id(backend.id),
    None,
)

check(
    "the other survives",
    repositories.get_by_id(frontend.id).name,
    "Frontend",
)

print()
print("=" * 80)
print("TASK IS LINKED TO A REPOSITORY")
print("=" * 80)

tasks = TaskRepository(database)

task = Task(
    repository_id=frontend.id,
    description="Create a notification system.",
)

tasks.save(task)

reloaded = tasks.get_by_id(task.id)

check(
    "repository_id persisted",
    reloaded.repository_id,
    frontend.id,
)

check(
    "repository resolves to a name",
    repositories.get_by_id(reloaded.repository_id).name,
    "Frontend",
)

check(
    "repository_id survives get_all",
    tasks.get_all()[0].repository_id,
    frontend.id,
)

legacy = Task(description="Task without a repository.")

tasks.save(legacy)

check(
    "a task may have no repository",
    tasks.get_by_id(legacy.id).repository_id,
    "",
)

print()
print("=" * 80)
print("DATA SURVIVES A RESTART")
print("=" * 80)

reopened_repositories = RepositoryRepository(database)

reopened_tasks = TaskRepository(database)

check(
    "repositories reloaded",
    [item.name for item in reopened_repositories.get_all()],
    ["Frontend"],
)

check(
    "task still points at its repository",
    reopened_tasks.get_by_id(task.id).repository_id,
    frontend.id,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REPOSITORY CHECKS PASSED")
print("=" * 80)
