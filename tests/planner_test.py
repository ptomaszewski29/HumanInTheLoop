"""Offline checks for the planner.

Runs without an LLM:

    python -m tests.planner_test
"""

import json
import os
import tempfile

import services.llm_factory as factory

PLAN = {
    "files": [
        {
            "path": "1",
            "content": "Create the notification interface",
            "description": "Define the contract.",
            "priority": "HIGH",
            "dependencies": [],
        },
        {
            "path": "2",
            "content": "Create the email provider",
            "description": "Implement it for email.",
            "priority": "HIGH",
            "dependencies": [1],
        },
        {
            "path": "3",
            "content": "Create the dispatcher",
            "description": "Route to providers.",
            "priority": "MEDIUM",
            "dependencies": [2],
        },
    ]
}


class FakeLLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def generate_text(self, prompt: str) -> str:
        return self.answer

    def generate_code(self, prompt: str) -> str:
        return ""


def use(answer: str) -> None:

    factory.LLMFactory.create = classmethod(
        lambda cls: FakeLLM(answer)
    )


use(json.dumps(PLAN))

from agents.planner_agent import (
    PlannerAgent,
    find_cycles,
    order_tasks,
)
from database.plan_repository import PlanRepository
from models.plan import Plan
from models.task_breakdown import Priority, TaskBreakdown
from models.task_execution import (
    ExecutionStatus,
    TaskExecution,
)

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


print("=" * 80)
print("AN EPIC BECOMES TASKS")
print("=" * 80)

plan = PlannerAgent().execute(
    "Build a notification platform.",
    "repo-1",
)

check("three tasks", len(plan.tasks), 3)

check(
    "the epic is kept",
    plan.epic,
    "Build a notification platform.",
)

check(
    "priorities are parsed",
    [item.priority for item in plan.tasks],
    [Priority.HIGH, Priority.HIGH, Priority.MEDIUM],
)

check(
    "dependencies are parsed",
    plan.task(3).dependencies,
    [2],
)

print()
print("=" * 80)
print("DEPENDENCIES DECIDE THE ORDER")
print("=" * 80)

position = {
    item.id: index
    for index, item in enumerate(plan.tasks)
}

for item in plan.tasks:

    for dependency in item.dependencies:

        check(
            f"task {item.id} comes after {dependency}",
            position[dependency] < position[item.id],
            True,
        )

check("no cycles", find_cycles(plan.tasks), [])

check(
    "priority breaks a tie",
    [
        item.id
        for item in order_tasks(
            [
                TaskBreakdown(1, "low", "", Priority.LOW),
                TaskBreakdown(2, "high", "", Priority.HIGH),
                TaskBreakdown(
                    3, "medium", "", Priority.MEDIUM
                ),
            ]
        )
    ],
    [2, 3, 1],
)

print()
print("=" * 80)
print("A CYCLE IS REPORTED, NOT LOOPED OVER")
print("=" * 80)

cyclic = [
    TaskBreakdown(1, "a", "", Priority.HIGH, [2]),
    TaskBreakdown(2, "b", "", Priority.HIGH, [1]),
    TaskBreakdown(3, "c", "", Priority.HIGH, []),
]

check("the cycle is named", find_cycles(cyclic), [1, 2])

check(
    "nothing is dropped",
    sorted(item.id for item in order_tasks(cyclic)),
    [1, 2, 3],
)

check(
    "the free task still comes first",
    order_tasks(cyclic)[0].id,
    3,
)

print()
print("=" * 80)
print("A MALFORMED PLAN IS CLEANED, NOT TRUSTED")
print("=" * 80)

reports: list[str] = []

check(
    "a task may not depend on itself",
    PlannerAgent._dependencies(
        {"dependencies": [2, 3]},
        2,
        "a",
        reports,
    ),
    [3],
)

check(
    "and that is reported",
    len(reports),
    1,
)

reports = []

check(
    "a dependency on a task that does not exist is dropped",
    PlannerAgent._drop_unknown(
        [
            TaskBreakdown(
                1, "a", "", Priority.HIGH, [9, 2]
            ),
            TaskBreakdown(2, "b", "", Priority.HIGH),
        ],
        reports,
    )[0].dependencies,
    [2],
)

check(
    "and that is reported too",
    len(reports),
    1,
)

check(
    "an unknown priority falls back",
    Priority.parse("URGENT"),
    Priority.MEDIUM,
)

use(
    '{"files": [{"path": "1", "content": "First",'
    ' "priority": "HIGH", "dependencies": []},'
    ' {"path": "2", "content": "Second"'
)

salvaged = PlannerAgent().execute("Epic.")

check(
    "a truncated plan keeps what it finished",
    [item.title for item in salvaged.tasks],
    ["First"],
)

use("I cannot plan that.")

try:
    PlannerAgent().execute("Epic.")

    failures.append("an unusable answer")

    print("FAIL an unusable answer was accepted")

except RuntimeError:
    print("OK   an unusable answer fails loudly")

print()
print("=" * 80)
print("INVALID DEPENDENCIES ARE REPORTED, NOT HIDDEN")
print("=" * 80)

use(
    json.dumps(
        {
            "files": [
                {
                    "path": "1",
                    "content": "First",
                    "priority": "HIGH",
                    "dependencies": [1],
                },
                {
                    "path": "2",
                    "content": "Second",
                    "priority": "LOW",
                    "dependencies": [99, "abc"],
                },
            ]
        }
    )
)

reported = PlannerAgent().execute("Epic.")

text = " ".join(reported.issues)

check(
    "three problems are reported",
    len(reported.issues),
    3,
)

check(
    "a self-dependency is named",
    "depended on itself" in text,
    True,
)

check(
    "an unknown task is named",
    "which the plan does not contain" in text,
    True,
)

check(
    "a dependency that is not an id is named",
    "not a task id" in text,
    True,
)

check(
    "the plan is still usable",
    len(reported.tasks),
    2,
)

check(
    "and the bad dependencies are gone",
    [item.dependencies for item in reported.tasks],
    [[], []],
)

use(
    json.dumps(
        {
            "files": [
                {
                    "path": "1",
                    "content": "A",
                    "priority": "HIGH",
                    "dependencies": [2],
                },
                {
                    "path": "2",
                    "content": "B",
                    "priority": "HIGH",
                    "dependencies": [1],
                },
            ]
        }
    )
)

looped = PlannerAgent().execute("Epic.")

check(
    "a cycle is reported",
    any(
        "Circular dependency" in issue
        for issue in looped.issues
    ),
    True,
)

check(
    "and both tasks are named",
    "1, 2" in " ".join(looped.issues),
    True,
)

use(json.dumps(PLAN))

clean = PlannerAgent().execute("Epic.")

check(
    "a sound plan reports nothing",
    clean.issues,
    [],
)

print()
print("=" * 80)
print("THE DEPENDENCY GRAPH READS AS LAYERS")
print("=" * 80)

levels = plan.levels()

check(
    "three steps",
    [[item.id for item in layer] for layer in levels],
    [[1], [2], [3]],
)

check(
    "every task appears once",
    sorted(
        item.id for layer in levels for item in layer
    ),
    [1, 2, 3],
)

check(
    "a task in a cycle still gets a place",
    sorted(
        item.id
        for layer in looped.levels()
        for item in layer
    ),
    [1, 2],
)

print()
print("=" * 80)
print("READINESS FOLLOWS THE GRAPH")
print("=" * 80)

check(
    "only the first task is ready",
    [
        item.id
        for item in plan.tasks
        if plan.is_ready(item)
    ],
    [1],
)

plan.record(
    TaskExecution(
        task_id=1,
        status=ExecutionStatus.COMPLETED,
    )
)

check(
    "the next one unlocks",
    [
        item.id
        for item in plan.remaining
        if plan.is_ready(item)
    ],
    [2],
)

check(
    "the last is still blocked",
    plan.blocked_by(plan.task(3)),
    [2],
)

check(
    "a task carries its title and description onward",
    plan.task(1).prompt,
    "Create the notification interface\n\n"
    "Define the contract.",
)

print()
print("=" * 80)
print("EXECUTION IS TRACKED PER TASK")
print("=" * 80)

tracked = PlannerAgent().execute("Epic.")

check(
    "nothing attempted yet",
    [
        tracked.status_of(item).value
        for item in tracked.tasks
    ],
    ["READY", "PENDING", "PENDING"],
)

check(
    "the dashboard agrees",
    {
        key: value
        for key, value in tracked.dashboard().items()
        if value
    },
    {"PENDING": 2, "READY": 1, "TOTAL": 3},
)

check("nothing complete", tracked.percent_complete, 0.0)

tracked.record(
    TaskExecution(
        task_id=1,
        status=ExecutionStatus.COMPLETED,
        started_at="2026-10-08T10:00:00+00:00",
        completed_at="2026-10-08T10:02:00+00:00",
    )
)

check(
    "the first is done and the second unlocks",
    [
        tracked.status_of(item).value
        for item in tracked.tasks
    ],
    ["COMPLETED", "READY", "PENDING"],
)

check(
    "progress follows",
    round(tracked.percent_complete, 2),
    0.33,
)

check(
    "a duration is reported",
    tracked.execution(1).duration,
    "2.0m",
)

tracked.record(
    TaskExecution(
        task_id=2,
        status=ExecutionStatus.FAILED,
        error="the developer returned no files",
    )
)

check(
    "a failure is remembered",
    tracked.status_of(tracked.task(2)),
    ExecutionStatus.FAILED,
)

check(
    "and it does not unblock what came after",
    tracked.status_of(tracked.task(3)),
    ExecutionStatus.PENDING,
)

check(
    "a failed task is still outstanding",
    [item.id for item in tracked.remaining],
    [2, 3],
)

check(
    "the dashboard counts it",
    tracked.dashboard()["FAILED"],
    1,
)

tracked.record(
    TaskExecution(
        task_id=2,
        status=ExecutionStatus.COMPLETED,
    )
)

check(
    "retrying replaces the record rather than adding one",
    len(
        [
            item
            for item in tracked.executions
            if item.task_id == 2
        ]
    ),
    1,
)

check(
    "and the failure is gone",
    tracked.dashboard()["FAILED"],
    0,
)

check(
    "a run interrupted mid-way reads as RUNNING",
    Plan(
        tasks=[TaskBreakdown(1, "a", "", Priority.HIGH)],
        executions=[
            TaskExecution(
                task_id=1,
                status=ExecutionStatus.RUNNING,
            )
        ],
    )
    .status_of(TaskBreakdown(1, "a", "", Priority.HIGH))
    .value,
    "RUNNING",
)

print()
print("=" * 80)
print("A RUN IS WATCHABLE WHILE IT HAPPENS")
print("=" * 80)

live = PlannerAgent().execute("Epic.")

check(
    "nothing is running yet",
    live.running,
    None,
)

check(
    "the first task is the one to pick up",
    live.next_ready().id,
    1,
)

check("and the log is empty", live.log(), [])

live.record(
    TaskExecution(
        task_id=1,
        status=ExecutionStatus.RUNNING,
        started_at="2026-10-09T09:30:00+00:00",
    )
)

check(
    "a running task names itself",
    live.running.id,
    1,
)

check(
    "and the dashboard counts it",
    live.dashboard()["RUNNING"],
    1,
)

check(
    "the log opens with the start",
    [
        (entry.event, entry.task_id)
        for entry in live.log()
    ],
    [("STARTED", 1)],
)

live.record(
    TaskExecution(
        task_id=1,
        status=ExecutionStatus.COMPLETED,
        started_at="2026-10-09T09:30:00+00:00",
        completed_at="2026-10-09T09:32:00+00:00",
    )
)

check(
    "nothing is running once it finishes",
    live.running,
    None,
)

check(
    "the next task is picked up",
    live.next_ready().id,
    2,
)

live.record(
    TaskExecution(
        task_id=2,
        status=ExecutionStatus.FAILED,
        started_at="2026-10-09T09:32:00+00:00",
        completed_at="2026-10-09T09:35:00+00:00",
        error="boom",
    )
)

check(
    "the log reads in order",
    [
        (entry.at[11:19], entry.event, entry.task_id)
        for entry in live.log()
    ],
    [
        ("09:30:00", "STARTED", 1),
        ("09:32:00", "COMPLETED", 1),
        ("09:32:00", "STARTED", 2),
        ("09:35:00", "FAILED", 2),
    ],
)

check(
    "a failure carries its reason into the log",
    live.log()[-1].detail,
    "boom",
)

check(
    "and its title",
    live.log()[-1].title,
    live.task(2).title,
)

check(
    "a failed task is offered again",
    live.next_ready().id,
    2,
)

check(
    "nothing is ready once the rest is blocked",
    Plan(
        tasks=[
            TaskBreakdown(1, "a", "", Priority.HIGH),
            TaskBreakdown(
                2, "b", "", Priority.HIGH, [1]
            ),
        ],
        executions=[
            TaskExecution(
                task_id=1,
                status=ExecutionStatus.FAILED,
            )
        ],
    ).next_ready().id,
    1,
)

check(
    "a finished plan has nothing to pick up",
    Plan(
        tasks=[TaskBreakdown(1, "a", "", Priority.HIGH)],
        executions=[
            TaskExecution(
                task_id=1,
                status=ExecutionStatus.COMPLETED,
            )
        ],
    ).next_ready(),
    None,
)

print()
print("=" * 80)
print("A PLAN SURVIVES A RESTART")
print("=" * 80)

database = os.path.join(
    tempfile.mkdtemp(),
    "planner_test.db",
)

store = PlanRepository(database)

store.save(plan)

restored = PlanRepository(database).get_by_id(plan.id)

check("tasks restored", len(restored.tasks), 3)

check(
    "titles restored",
    [item.title for item in restored.tasks],
    [item.title for item in plan.tasks],
)

check(
    "priorities restored",
    [item.priority for item in restored.tasks],
    [item.priority for item in plan.tasks],
)

check(
    "dependencies restored",
    restored.task(3).dependencies,
    [2],
)

check("progress restored", restored.completed, [1])

store.save(tracked)

recovered = PlanRepository(database).get_by_id(tracked.id)

check(
    "only attempted tasks have a record",
    len(recovered.executions),
    2,
)

check(
    "an unattempted task has none",
    recovered.execution(3),
    None,
)

check(
    "statuses restored",
    [
        recovered.status_of(item).value
        for item in recovered.tasks
    ],
    [
        tracked.status_of(item).value
        for item in tracked.tasks
    ],
)

check(
    "timestamps restored",
    recovered.execution(1).started_at,
    "2026-10-08T10:00:00+00:00",
)

check(
    "a failure's reason restored",
    PlanRepository(database)
    ._parse_executions(
        '[{"task_id": 1, "status": "FAILED", '
        '"error": "boom"}]',
        "[]",
    )[0]
    .error,
    "boom",
)

check(
    "a plan saved before executions existed keeps its progress",
    [
        item.task_id
        for item in PlanRepository(database)
        ._parse_executions("[]", "[1, 2]")
    ],
    [1, 2],
)

check(
    "reported problems are restored too",
    PlanRepository(database)
    .get_by_id(reported.id)
    .issues
    if PlanRepository(database).get_by_id(reported.id)
    else None,
    None,
)

store.save(reported)

check(
    "a plan with problems keeps them",
    len(
        PlanRepository(database)
        .get_by_id(reported.id)
        .issues
    ),
    3,
)

plan.record(
    TaskExecution(
        task_id=2,
        status=ExecutionStatus.COMPLETED,
    )
)

store.update_progress(plan)

check(
    "progress updated",
    PlanRepository(database)
    .get_by_id(plan.id)
    .completed,
    [1, 2],
)

store.delete(plan.id)

check(
    "deleted",
    PlanRepository(database).get_by_id(plan.id),
    None,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PLANNER CHECKS PASSED")
print("=" * 80)
