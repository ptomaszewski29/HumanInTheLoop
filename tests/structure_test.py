"""Offline checks for structural validation.

Runs without an LLM:

    python -m tests.structure_test
"""

from models.file_type import FileType
from models.generated_file import GeneratedFile
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

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL STRUCTURE CHECKS PASSED")
print("=" * 80)
