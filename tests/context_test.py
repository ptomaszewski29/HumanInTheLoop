"""Offline checks for repository context and bootstrap.

Real folders, no model, no network:

    python -m tests.context_test
"""

import json
import os
import tempfile

from models.repository_context import (
    ProjectState,
    RepositoryContext,
    TestFramework,
)
from services.bootstrap import TEMPLATES, bootstrap
from services.repository_context import describe
from services.translations import MESSAGES

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


def write(root: str, path: str, content: str) -> None:

    absolute = os.path.join(root, *path.split("/"))

    os.makedirs(
        os.path.dirname(absolute) or root,
        exist_ok=True,
    )

    with open(absolute, "w", encoding="utf-8") as handle:
        handle.write(content)


def folder() -> str:

    return tempfile.mkdtemp()


def read_text(root: str, name: str) -> str:

    with open(
        os.path.join(root, name),
        encoding="utf-8",
    ) as handle:
        return handle.read()


def read(root: str, name: str) -> dict:

    with open(
        os.path.join(root, name),
        encoding="utf-8",
    ) as handle:
        return json.load(handle)


print("=" * 80)
print("THE REPOSITORY IS DESCRIBED FROM DISK, NOT GUESSED")
print("=" * 80)

empty = folder()

blank = describe(empty)

check("an empty folder is EMPTY", blank.state, ProjectState.EMPTY)

check("nothing is set up", blank.missing, [
    "package.json",
    "tsconfig.json",
    "vitest.config.ts",
    ".gitignore",
])

check("so it needs bootstrapping", blank.bootstrap_needed, True)

check("and its tests cannot run", blank.tests_runnable, False)

check(
    "a folder that is not there describes as empty",
    describe(os.path.join(empty, "nowhere")).state,
    ProjectState.EMPTY,
)

check(
    "and so does no folder at all",
    describe("").state,
    ProjectState.EMPTY,
)

half = folder()

write(half, "src/a.ts", "export class A {}")

write(half, "package.json", json.dumps({"name": "x"}))

partial = describe(half)

check(
    "code without tooling is BOOTSTRAP_REQUIRED",
    partial.state,
    ProjectState.BOOTSTRAP_REQUIRED,
)

check("package.json is seen", partial.package_json, True)

check("the missing tsconfig is named", "tsconfig.json" in partial.missing, True)

check(
    "package.json is not counted as a source folder",
    partial.source_folders,
    ["src"],
)

check("and the file is counted", partial.file_count, 2)

broken = folder()

write(broken, "package.json", "{ not json at all")

check(
    "a malformed manifest is a state, not a crash",
    describe(broken).package_json,
    True,
)

print()
print("=" * 80)
print("A TEST FRAMEWORK IS REPORTED, NOT ASSUMED")
print("=" * 80)

for name, expected in (
    ("vitest.config.ts", TestFramework.VITEST),
    ("jest.config.js", TestFramework.JEST),
    (".mocharc.json", TestFramework.MOCHA),
):
    root = folder()

    write(root, "src/a.ts", "export class A {}")

    write(root, name, "{}")

    check(
        f"{name} means {expected.value}",
        describe(root).test_framework,
        expected,
    )

from_manifest = folder()

write(
    from_manifest,
    "package.json",
    json.dumps({"devDependencies": {"jest": "^29.0.0"}}),
)

check(
    "a dependency counts when there is no config",
    describe(from_manifest).test_framework,
    TestFramework.JEST,
)

# The runner drives Vitest and nothing else. Saying "tests
# are enabled" because Jest is configured would be a claim
# the test gate immediately contradicts.
check(
    "Jest configured is still not runnable here",
    RepositoryContext(
        test_framework=TestFramework.JEST,
        dependencies_installed=True,
    ).tests_runnable,
    False,
)

check(
    "nor is Vitest without its dependencies",
    RepositoryContext(
        test_framework=TestFramework.VITEST,
        dependencies_installed=False,
    ).tests_runnable,
    False,
)

check(
    "both together are",
    RepositoryContext(
        test_framework=TestFramework.VITEST,
        dependencies_installed=True,
    ).tests_runnable,
    True,
)

installed = folder()

os.makedirs(os.path.join(installed, "node_modules"))

check(
    "installed dependencies are noticed",
    describe(installed).dependencies_installed,
    True,
)

os.makedirs(os.path.join(installed, ".git"))

check(
    "and so is git",
    describe(installed).git,
    True,
)

print()
print("=" * 80)
print("SCAFFOLDING IS WRITTEN FROM TEMPLATES, NOT GENERATED")
print("=" * 80)

fresh = folder()

created = bootstrap(fresh, describe(fresh))

check(
    "an empty repository gets the lot",
    sorted(created),
    [
        ".gitignore",
        "package.json",
        "tsconfig.json",
        "vitest.config.ts",
    ],
)

settled = describe(fresh)

check(
    "and is then READY",
    settled.state,
    ProjectState.PROJECT_READY,
)

check(
    "with Vitest configured",
    settled.test_framework,
    TestFramework.VITEST,
)

check(
    "nothing left missing",
    settled.missing,
    [],
)

check(
    "and node_modules will not be committed by accident",
    "node_modules/"
    in read_text(fresh, ".gitignore"),
    True,
)

check(
    "the manifest is valid JSON",
    read(fresh, "package.json")["scripts"]["test"],
    "vitest run",
)

check(
    "running it again creates nothing",
    bootstrap(fresh, describe(fresh)),
    [],
)

mine = folder()

write(mine, "package.json", '{"name": "mine"}')

created = bootstrap(mine, describe(mine))

check(
    "an existing manifest is left alone",
    "package.json" in created,
    False,
)

check(
    "and keeps its content",
    read(mine, "package.json")["name"],
    "mine",
)

check(
    "while what was missing is written",
    sorted(created),
    [".gitignore", "tsconfig.json", "vitest.config.ts"],
)

check(
    "a folder that is not there writes nothing",
    bootstrap("", describe("")),
    [],
)

check(
    "every missing name has a template",
    sorted(TEMPLATES),
    sorted(RepositoryContext().missing),
)

# A .gitignore is worth writing and is not worth calling a
# project unbuildable over: a repository with the tooling
# and no .gitignore is ready to work in.
tidy = folder()

for name in (
    "package.json",
    "tsconfig.json",
    "vitest.config.ts",
):
    write(tidy, name, "{}")

no_ignore = describe(tidy)

check(
    "a missing .gitignore is listed",
    no_ignore.missing,
    [".gitignore"],
)

check(
    "but does not block the build",
    no_ignore.build_missing,
    [],
)

check(
    "so the project is ready",
    no_ignore.state,
    ProjectState.PROJECT_READY,
)

check(
    "and bootstrap still writes the one file",
    bootstrap(tidy, no_ignore),
    [".gitignore"],
)

print()
print("=" * 80)
print("THE PLANNER IS TOLD, AND TOLD NOT TO PLAN SETUP")
print("=" * 80)

import services.llm_factory as factory
from agents.planner_agent import PlannerAgent

SEEN: list[str] = []

PLAN = {
    "files": [
        {
            "path": "1",
            "content": "Create the interface",
            "description": "Define it.",
            "priority": "HIGH",
            "dependencies": [],
        },
        {
            "path": "2",
            "content": "Implement it",
            "description": "Build it.",
            "priority": "MEDIUM",
            "dependencies": [1],
        },
    ]
}


class FakeLLM:
    def generate_text(self, prompt: str) -> str:

        SEEN.append(prompt)

        return json.dumps(PLAN)

    def generate_code(self, prompt: str) -> str:
        return ""


factory.LLMFactory.create = classmethod(lambda cls: FakeLLM())

SEEN.clear()

PlannerAgent().execute("Build a notifier.", "", empty)

check(
    "an empty repository is described as empty",
    "The repository is empty." in SEEN[0],
    True,
)

check(
    "and setup is declared somebody else's job",
    "do not plan tasks for it" in SEEN[0],
    True,
)

SEEN.clear()

PlannerAgent().execute("Build a notifier.", "", fresh)

check(
    "a set-up repository is described as it is",
    "The repository already exists:" in SEEN[0],
    True,
)

check(
    "naming what it has",
    "package.json: present" in SEEN[0],
    True,
)

check(
    "and what it runs tests with",
    "test framework: Vitest" in SEEN[0],
    True,
)

check(
    "the rule against setup tasks is always there",
    "do not plan project setup" in SEEN[0],
    True,
)

SEEN.clear()

PlannerAgent().execute("Build a notifier.")

check(
    "with no repository, nothing is claimed about one",
    "The repository" in SEEN[0],
    False,
)

print()
print("=" * 80)
print("WHAT BOOTSTRAP WROTE IS RECORDED, NOT ASSUMED")
print("=" * 80)

# Scaffolding is a change to someone's repository that no
# generated-file list would mention. It ran silently once,
# and a plan of eleven tasks then looked like it had
# skipped project setup entirely.
import sqlite3

from database.task_repository import TaskRepository
from models.task import Task
from models.task_status import TaskStatus

database = os.path.join(folder(), "tasks.db")

recorded = Task(
    description="x",
    status=TaskStatus.APPROVED,
    environment=["package.json", "tsconfig.json"],
)

TaskRepository(database).save(recorded)

restored = TaskRepository(database).get_by_id(recorded.id)

check(
    "it survives a restart",
    restored.environment,
    ["package.json", "tsconfig.json"],
)

check(
    "and the fields after it are not shifted",
    (restored.status, restored.description),
    (TaskStatus.APPROVED, "x"),
)

legacy = os.path.join(folder(), "legacy.db")

TaskRepository(legacy).save(Task(description="old"))

connection = sqlite3.connect(legacy)

connection.execute(
    "ALTER TABLE tasks DROP COLUMN environment"
)

connection.commit()

connection.close()

older = TaskRepository(legacy).get_all()

check(
    "a row written before the column still loads",
    (older[0].description, older[0].environment),
    ("old", []),
)

check(
    "a run that created nothing records nothing",
    Task(description="x").environment,
    [],
)

print()
print("=" * 80)
print("WHAT THE PIPELINE DID IS KEPT, NOT JUST PRINTED")
print("=" * 80)

from models.pipeline_step import PipelineStep, StepRecorder

recorder = StepRecorder()

recorder.record("step.developer", "3 file(s), 900 chars")

recorder.record("step.architect", "#1 · 85/100")

recorder.record("step.tests", "FAILED · 0/3", ok=False)

check("three steps", len(recorder.steps), 3)

check(
    "in the order they happened",
    [step.name for step in recorder.steps],
    ["step.developer", "step.architect", "step.tests"],
)

check(
    "a step that went wrong says so",
    [step.ok for step in recorder.steps],
    [True, True, False],
)

check(
    "and each one is timed",
    all(step.seconds >= 0 for step in recorder.steps),
    True,
)

check(
    "a step with no measurable time shows none",
    PipelineStep(seconds=0).duration,
    "",
)

check(
    "seconds under a minute",
    PipelineStep(seconds=42).duration,
    "42s",
)

check(
    "minutes above one",
    PipelineStep(seconds=150).duration,
    "2.5m",
)

stepped = os.path.join(folder(), "steps.db")

carried = Task(
    description="x",
    status=TaskStatus.APPROVED,
    steps=recorder.steps,
)

TaskRepository(stepped).save(carried)

restored_steps = TaskRepository(stepped).get_by_id(
    carried.id
)

check(
    "they survive a restart",
    [
        (step.name, step.detail, step.ok)
        for step in restored_steps.steps
    ],
    [
        (step.name, step.detail, step.ok)
        for step in recorder.steps
    ],
)

check(
    "and the fields after them are not shifted",
    (
        restored_steps.status,
        restored_steps.description,
        restored_steps.environment,
    ),
    (TaskStatus.APPROVED, "x", []),
)

older_steps = os.path.join(folder(), "legacy-steps.db")

TaskRepository(older_steps).save(Task(description="old"))

connection = sqlite3.connect(older_steps)

connection.execute("ALTER TABLE tasks DROP COLUMN steps")

connection.commit()

connection.close()

check(
    "a row written before the column still loads",
    [
        (item.description, item.steps)
        for item in TaskRepository(older_steps).get_all()
    ],
    [("old", [])],
)

check(
    "every step name is a key the dictionary knows",
    [
        name
        for name in (
            "step.bootstrap",
            "step.developer",
            "step.architect",
            "step.improve",
            "step.qa",
            "step.written",
            "step.tests",
            "step.tests_retry",
        )
        if name not in MESSAGES
    ],
    [],
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL CONTEXT CHECKS PASSED")
print("=" * 80)
