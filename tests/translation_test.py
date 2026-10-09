"""The dictionary is complete, and the interface uses it.

A half-translated interface is the normal end state of
this kind of work, so the checks here are the thing that
stops it:

    python -m tests.translation_test
"""

import ast
import re

from services.translations import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    MESSAGES,
    translate,
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
print("EVERY MESSAGE EXISTS IN EVERY LANGUAGE")
print("=" * 80)

check(
    "two languages, and the default is one of them",
    DEFAULT_LANGUAGE in LANGUAGES,
    True,
)

missing = [
    f"{key}/{language}"
    for key, entry in MESSAGES.items()
    for language in LANGUAGES
    if not entry.get(language, "").strip()
]

check("nothing untranslated", missing, [])

extra = [
    f"{key}/{language}"
    for key, entry in MESSAGES.items()
    for language in entry
    if language not in LANGUAGES
]

check("and no language nobody can select", extra, [])

# A placeholder in one language and not the other means
# one of them silently drops a value, which is how a
# number or a file name goes missing from a message.
PLACEHOLDER = re.compile(r"\{(\w+)\}")

mismatched = [
    key
    for key, entry in MESSAGES.items()
    if len(
        {
            frozenset(PLACEHOLDER.findall(text))
            for text in entry.values()
        }
    )
    > 1
]

check(
    "the same placeholders in both languages",
    mismatched,
    [],
)

print()
print("=" * 80)
print("A MISSING MESSAGE IS LOUD, NOT BLANK")
print("=" * 80)

check(
    "an unknown key shows itself",
    translate("nothing.like.this"),
    "⟨nothing.like.this⟩",
)

check(
    "a known key translates",
    translate("board.total", "en"),
    "Total",
)

check(
    "and differs by language",
    translate("board.total", "pl")
    != translate("board.total", "en"),
    True,
)

check(
    "an unknown language falls back rather than failing",
    translate("board.total", "de"),
    translate("board.total", DEFAULT_LANGUAGE),
)

check(
    "placeholders are filled",
    translate("plan.run_all", "en", count=3),
    "⏩ Run the whole plan (3)",
)

check(
    "a placeholder nobody supplied leaves the text intact",
    "{count}" in translate("plan.run_all", "en"),
    True,
)

print()
print("=" * 80)
print("THE INTERFACE SAYS NOTHING THE DICTIONARY HAS NOT GOT")
print("=" * 80)

with open("app.py", encoding="utf-8") as handle:
    source = handle.read()

tree = ast.parse(source)

# Argument positions that are a label on the page rather
# than a widget key, a language code or a format string
# for a number.
SPOKEN = {
    "write",
    "caption",
    "info",
    "warning",
    "error",
    "success",
    "button",
    "subheader",
    "header",
    "metric",
    "expander",
    "text_input",
    "text_area",
    "selectbox",
    "checkbox",
    "radio",
    "markdown",
    "spinner",
}

# Text that is not prose: a path, a marker the parser
# reads, a label that is the same word in both languages
# and carries no grammar.
EXEMPT = re.compile(
    r"^(?:[\s\d\W]*|[A-Z_]+|https?://\S+|\w+\.(?:ts|json|py|md)"
    r"|PASS|FAIL|UNAVAILABLE|NOT_RUN|ERROR"
    r"|Pull Request|TypeScript|Git|package\.json"
    # A unit left over from a format string: "s", "ms".
    r"|s|ms|kB|MB)$"
)

untranslated: list[str] = []

for node in ast.walk(tree):

    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in SPOKEN
    ):
        continue

    candidates = list(node.args) + [
        keyword.value
        for keyword in node.keywords
        if keyword.arg in ("label", "help", "text", "body")
    ]

    for argument in candidates:

        text = ""

        if isinstance(argument, ast.Constant) and isinstance(
            argument.value,
            str,
        ):
            text = argument.value

        elif isinstance(argument, ast.JoinedStr):
            text = "".join(
                piece.value
                for piece in argument.values
                if isinstance(piece, ast.Constant)
            )

        if not text.strip() or EXEMPT.match(text.strip()):
            continue

        untranslated.append(
            f"line {node.lineno}: {text[:60]!r}"
        )

check(
    "no literal prose left in app.py",
    untranslated,
    [],
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL TRANSLATION CHECKS PASSED")
print("=" * 80)
