"""Offline checks for structural validation.

Runs without an LLM:

    python -m tests.structure_test
"""

from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.structure_report import StructureReport
from services.import_repair import drop_self_imports
from services.structure_validator import (
    StructureValidator,
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


def source(
    path: str,
    content: str,
) -> GeneratedFile:

    return GeneratedFile(path, FileType.SOURCE, content)


TASK = """Create a notification system.

Requirements:

- email
- sms
- push
- interfaces
- dependency inversion
"""

print("=" * 80)
print("A FILE REFERENCED BUT NEVER GENERATED")
print("=" * 80)

report = StructureValidator.validate(
    [
        source(
            "src/notification.service.ts",
            'import { NotificationStrategy } from '
            '"./notification.strategy";\n'
            "export class NotificationService {}",
        ),
    ],
)

check("one missing file", len(report.missing_files), 1)

check(
    "the import is named",
    "notification.strategy" in report.missing_files[0],
    True,
)

check("it blocks", len(report.blockers), 1)

print()
print("=" * 80)
print("A SYMBOL IMPORTED BUT NEVER EXPORTED")
print("=" * 80)

report = StructureValidator.validate(
    [
        source("src/a.ts", "export class Alpha {}"),
        source(
            "src/b.ts",
            'import { Beta } from "./a";',
        ),
    ],
)

check("one broken import", len(report.broken_imports), 1)

check(
    "the symbol is named",
    "'Beta'" in report.broken_imports[0],
    True,
)

print()
print("=" * 80)
print("A CLASS USED BUT NEVER DECLARED OR IMPORTED")
print("=" * 80)

report = StructureValidator.validate(
    [
        source(
            "src/factory.ts",
            "export class Factory {\n"
            "  create() { return new EmailProvider(); }\n"
            "}",
        ),
    ],
)

check(
    "the undefined class is caught",
    len(report.broken_imports),
    1,
)

check(
    "it is named",
    "EmailProvider" in report.broken_imports[0],
    True,
)

check(
    "a built-in is never reported",
    StructureValidator.undefined_symbols(
        "throw new Error('x');\nconst m = new Map();"
    ),
    [],
)

check(
    "an imported class is fine",
    StructureValidator.undefined_symbols(
        "import { A } from './a';\nconst x = new A();"
    ),
    [],
)

print()
print("=" * 80)
print("A CIRCULAR DEPENDENCY")
print("=" * 80)

report = StructureValidator.validate(
    [
        source(
            "src/a.ts",
            'import { B } from "./b";\nexport class A {}',
        ),
        source(
            "src/b.ts",
            'import { A } from "./a";\nexport class B {}',
        ),
    ],
)

check("one cycle", len(report.cycles), 1)

print()
print("=" * 80)
print("A REQUIREMENT WITH NO IMPLEMENTATION")
print("=" * 80)

check(
    "only file-shaped requirements are checked",
    StructureValidator.requirements(TASK),
    ["email", "sms", "push"],
)

report = StructureValidator.validate(
    [
        source(
            "src/email.provider.ts",
            "export class EmailProvider {}",
        ),
    ],
    TASK,
)

check(
    "sms and push are missing",
    len(report.uncovered_requirements),
    2,
)

report = StructureValidator.validate(
    [
        source(
            "src/email.provider.ts",
            "export class EmailProvider {}",
        ),
        source(
            "src/sms.provider.ts",
            "export class SmsProvider {}",
        ),
        source(
            "src/push.provider.ts",
            "export class PushProvider {}",
        ),
    ],
    TASK,
)

check(
    "a complete set covers them",
    report.uncovered_requirements,
    [],
)

print()
print("=" * 80)
print("A SOUND FILE SET RAISES NOTHING")
print("=" * 80)

sound = [
    source(
        "src/notification.strategy.ts",
        "export interface NotificationStrategy "
        "{ send(m: string): void; }",
    ),
    source(
        "src/email.provider.ts",
        'import { NotificationStrategy } from '
        '"./notification.strategy";\n'
        "export class EmailProvider "
        "implements NotificationStrategy {}",
    ),
    source(
        "src/sms.provider.ts",
        "export class SmsProvider {}",
    ),
    source(
        "src/push.provider.ts",
        "export class PushProvider {}",
    ),
    GeneratedFile(
        "tests/email.provider.test.ts",
        FileType.TEST,
        'import { EmailProvider } from '
        '"../src/email.provider";\n'
        'import { describe } from "vitest";',
    ),
]

report = StructureValidator.validate(sound, TASK)

check("no blockers at all", report.blockers, [])

check("files counted", report.file_count, 5)

check(
    "an external package is not a missing file",
    report.missing_files,
    [],
)

print()
print("=" * 80)
print("EXPORT FORMS THAT MUST NOT FALSE-POSITIVE")
print("=" * 80)

for label, files in (
    (
        "export { X }",
        [
            source(
                "src/a.ts",
                "class Alpha {}\nexport { Alpha };",
            ),
            source(
                "src/b.ts",
                'import { Alpha } from "./a";',
            ),
        ],
    ),
    (
        "export * from",
        [
            source("src/a.ts", 'export * from "./c";'),
            source("src/c.ts", "export class Gamma {}"),
            source(
                "src/b.ts",
                'import { Gamma } from "./a";',
            ),
        ],
    ),
    (
        "export default",
        [
            source(
                "src/a.ts",
                "export default class Alpha {}",
            ),
            source("src/b.ts", 'import Alpha from "./a";'),
        ],
    ),
    (
        "a folder index",
        [
            source(
                "src/providers/index.ts",
                "export class P {}",
            ),
            source(
                "src/b.ts",
                'import { P } from "./providers";',
            ),
        ],
    ),
    (
        "a multi-line import",
        [
            source(
                "src/a.ts",
                "export class Alpha {}\n"
                "export class Beta {}",
            ),
            source(
                "src/b.ts",
                "import {\n  Alpha,\n  Beta,\n} "
                "from './a';",
            ),
        ],
    ),
):
    check(
        f"no false positive for {label}",
        StructureValidator.validate(files).blockers,
        [],
    )

print()
print("=" * 80)
print("THE VALIDATION REPORT")
print("=" * 80)

report = StructureValidator.validate(sound, TASK)

print(report.summary())

check(
    "files are counted",
    "Files: 5" in report.summary(),
    True,
)

check(
    "imports are counted",
    report.import_count,
    3,
)

print()
print("=" * 80)
print("A CYCLE IS REPORTED AS AN IMPORT TO REMOVE")
print("=" * 80)

# Naming the route is what makes a cycle fixable. Told
# only that one exists, the developer rewrote files for
# three rounds running and the cycle survived all three:
# it writes one file at a time and cannot see which import
# closes the loop.
looping = [
    GeneratedFile(
        path="src/DeliveryLog.ts",
        file_type=FileType.SOURCE,
        content=(
            "import { PushProvider } from './PushProvider';"
            + chr(10)
            + "export class DeliveryLog {}"
        ),
    ),
    GeneratedFile(
        path="src/PushProvider.ts",
        file_type=FileType.SOURCE,
        content=(
            "import { DeliveryLog } from './DeliveryLog';"
            + chr(10)
            + "export class PushProvider {}"
        ),
    ),
]

report = StructureValidator.validate(looping)

check("the cycle is found", len(report.cycles), 1)

check(
    "and its route is kept, not just its existence",
    report.cycle_paths,
    [
        [
            "src/DeliveryLog.ts",
            "src/PushProvider.ts",
            "src/DeliveryLog.ts",
        ]
    ],
)

check(
    "it becomes one instruction",
    len(report.cuts()),
    1,
)

check(
    "naming the file that must change",
    report.cuts()[0].startswith(
        "In src/DeliveryLog.ts, remove the import of "
        "src/PushProvider.ts."
    ),
    True,
)

check(
    "a clean file set has nothing to cut",
    StructureValidator.validate(
        [
            GeneratedFile(
                path="src/a.ts",
                file_type=FileType.SOURCE,
                content="export class A {}",
            )
        ]
    ).cuts(),
    [],
)

# The same cycle has to produce the same instruction every
# round: sent to cut a different edge each time, the
# developer would move the loop around instead of breaking
# it.
check(
    "the same cycle gives the same cut twice",
    StructureValidator.validate(looping).cuts(),
    report.cuts(),
)

check(
    "a repeated cycle is not repeated advice",
    StructureReport(
        cycle_paths=[
            ["src/a.ts", "src/b.ts", "src/a.ts"],
            ["src/a.ts", "src/b.ts", "src/a.ts"],
        ]
    ).cuts(),
    StructureReport(
        cycle_paths=[["src/a.ts", "src/b.ts", "src/a.ts"]]
    ).cuts(),
)

check(
    "a path too short to hold an edge is skipped",
    StructureReport(cycle_paths=[["src/a.ts"]]).cuts(),
    [],
)

print()
print("=" * 80)
print("A FILE IMPORTING ITSELF IS CUT, NOT DISCUSSED")
print("=" * 80)

# The commonest cycle a small model writes, and the only
# one with no design question in it: the symbols are
# already in scope. Asked to fix exactly this, a 3B model
# did not, twice running.
selfish = [
    GeneratedFile(
        path="src/RetryPolicy.ts",
        file_type=FileType.SOURCE,
        content=(
            "import { RetryPolicy } from './RetryPolicy';"
            + chr(10)
            + "export class RetryPolicy { run() {} }"
        ),
    ),
    GeneratedFile(
        path="src/Dispatcher.ts",
        file_type=FileType.SOURCE,
        content=(
            "import { RetryPolicy } from './RetryPolicy';"
            + chr(10)
            + "export class Dispatcher {}"
        ),
    ),
]

check(
    "the validator sees it first",
    StructureValidator.validate(selfish).cycles,
    [
        (
            "Circular dependency: src/RetryPolicy.ts -> "
            "src/RetryPolicy.ts"
        )
    ],
)

repaired, notes = drop_self_imports(selfish)

check(
    "the self import is gone",
    repaired[0].content,
    "export class RetryPolicy { run() {} }",
)

check(
    "a real import of the same file is untouched",
    repaired[1].content,
    selfish[1].content,
)

check(
    "and the cycle with it",
    StructureValidator.validate(repaired).cycles,
    [],
)

check(
    "the repair is reported, not silent",
    notes,
    ["src/RetryPolicy.ts imported itself 1 time(s); removed"],
)

check(
    "a clean file set is returned untouched",
    drop_self_imports(
        [
            GeneratedFile(
                path="src/a.ts",
                file_type=FileType.SOURCE,
                content="export class A {}",
            )
        ]
    ),
    (
        [
            GeneratedFile(
                path="src/a.ts",
                file_type=FileType.SOURCE,
                content="export class A {}",
            )
        ],
        [],
    ),
)

check(
    "a two-file cycle is left for the developer to decide",
    len(
        drop_self_imports(
            [
                GeneratedFile(
                    path="src/a.ts",
                    file_type=FileType.SOURCE,
                    content="import { B } from './b';",
                ),
                GeneratedFile(
                    path="src/b.ts",
                    file_type=FileType.SOURCE,
                    content="import { A } from './a';",
                ),
            ]
        )[1]
    ),
    0,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL STRUCTURE CHECKS PASSED")
print("=" * 80)
