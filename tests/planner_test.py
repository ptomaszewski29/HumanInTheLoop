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
from models.task_breakdown import Priority, TaskBreakdown

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

check(
    "a task may not depend on itself",
    PlannerAgent._dependencies(
        {"dependencies": [2, 3]},
        2,
    ),
    [3],
)

check(
    "a dependency on a task that does not exist is dropped",
    PlannerAgent._drop_unknown(
        [
            TaskBreakdown(
                1, "a", "", Priority.HIGH, [9, 2]
            ),
            TaskBreakdown(2, "b", "", Priority.HIGH),
        ]
    )[0].dependencies,
    [2],
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

plan.completed = [1]

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

store.update_completed(plan.id, [1, 2])

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
