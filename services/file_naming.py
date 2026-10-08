import re

NAME = r"\s+([A-Za-z_$][A-Za-z0-9_$]*)"

# Tried in order. Generated code usually declares the
# interfaces before the class that implements them, so a
# concrete class names the file better than whatever
# symbol happens to appear first.
SYMBOL_PATTERNS = (
    re.compile(
        r"\bexport\s+(?:default\s+)?(?!abstract\b)class" + NAME
    ),
    re.compile(
        r"\bexport\s+(?:default\s+)?abstract\s+class" + NAME
    ),
    re.compile(
        r"\bexport\s+(?:default\s+)?"
        r"(?:interface|type|enum|function|const)" + NAME
    ),
    re.compile(r"\b(?!abstract\b)class" + NAME),
    re.compile(r"\binterface" + NAME),
)

PASCAL_WORDS = re.compile(
    r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+"
)

UNSAFE = re.compile(r"[^a-z0-9.-]+")

# Trailing words that name an architectural role and
# therefore earn their own folder. Anything else stays
# directly in src/, because inventing a folder from an
# arbitrary word produces nonsense like src/emails/.
ROLE_WORDS = frozenset(
    {
        "adapter",
        "client",
        "component",
        "controller",
        "factory",
        "guard",
        "handler",
        "helper",
        "mapper",
        "middleware",
        "model",
        "provider",
        "repository",
        "service",
        "store",
        "util",
        "validator",
    }
)

STOP_WORDS = frozenset(
    {
        "also",
        "create",
        "from",
        "implement",
        "into",
        "must",
        "requirement",
        "requirements",
        "should",
        "that",
        "then",
        "this",
        "using",
        "with",
        "write",
    }
)

DEFAULT_BASE_NAME = "generated"

# Above this many top-level declarations a file is
# treated as a whole subsystem rather than one unit.
MANY_DECLARATIONS = 3


def pluralise(word: str) -> str:

    if word.endswith("y") and not word.endswith(
        ("ay", "ey", "iy", "oy", "uy")
    ):
        return f"{word[:-1]}ies"

    if word.endswith(("s", "x", "z", "ch", "sh")):
        return f"{word}es"

    return f"{word}s"


def candidate_symbols(code: str) -> list[str]:
    """Every symbol that could name the file, best first."""

    found: list[str] = []

    for pattern in SYMBOL_PATTERNS:

        for match in pattern.finditer(code):

            name = match.group(1)

            if name not in found:
                found.append(name)

    return found


def task_keywords(task_description: str) -> dict[str, int]:
    """Task words by weight, earliest words weighing most.

    The opening words say what is being built; the ones
    further down are usually requirements and details.
    """

    words: list[str] = []

    for word in re.findall(
        r"[a-z]+",
        task_description.lower(),
    ):
        if (
            len(word) > 3
            and word not in STOP_WORDS
            and word not in words
        ):
            words.append(word)

    total = len(words)

    return {
        word: total - index
        for index, word in enumerate(words)
    }


def primary_symbol(
    code: str,
    task_description: str = "",
) -> str | None:
    """The name the file is most likely about.

    A single generated file often declares several
    classes, so the one whose name echoes the task wins
    over whichever happens to come first.
    """

    candidates = candidate_symbols(code)

    if not candidates:
        return None

    keywords = task_keywords(task_description)

    if not keywords:
        return candidates[0]

    def score(symbol: str) -> int:

        words = {
            word.lower()
            for word in PASCAL_WORDS.findall(symbol)
        }

        return sum(
            keywords.get(word, 0) for word in words
        )

    best = max(candidates, key=score)

    if score(best) == 0:
        return candidates[0]

    return best


def task_words(
    task_description: str,
    limit: int = 3,
) -> list[str]:
    """The few task words that best name a file."""

    keywords = task_keywords(task_description)

    ordered = sorted(
        keywords,
        key=lambda word: -keywords[word],
    )

    return ordered[:limit]


def slugify(text: str) -> str:

    cleaned = UNSAFE.sub("-", text.lower()).strip("-.")

    return re.sub(r"-{2,}", "-", cleaned)


class FileNaming:
    """Derives repository paths from generated code.

    A symbol whose last word names a role, such as
    NotificationService, becomes
    src/services/notification.service.ts. Every other
    symbol lands directly in src/.
    """

    @staticmethod
    def _words(
        code: str,
        task_description: str,
    ) -> list[str]:

        from_task = task_words(task_description)

        # A file that declares a whole subsystem has no
        # single symbol that represents it, so the task
        # names it better than any one class would.
        crowded = (
            len(candidate_symbols(code)) > MANY_DECLARATIONS
        )

        if from_task and crowded:
            return from_task

        symbol = primary_symbol(
            code,
            task_description,
        )

        if symbol:
            return [
                word.lower()
                for word in PASCAL_WORDS.findall(symbol)
            ]

        return from_task or [DEFAULT_BASE_NAME]

    @staticmethod
    def _base_and_folder(
        code: str,
        task_description: str,
    ) -> tuple[str, str | None]:

        words = FileNaming._words(
            code,
            task_description,
        )

        if not words:
            return DEFAULT_BASE_NAME, None

        role = words[-1]

        if len(words) >= 2 and role in ROLE_WORDS:

            feature = "-".join(words[:-1])

            return f"{feature}.{role}", pluralise(role)

        return "-".join(words), None

    @staticmethod
    def base_name(
        code: str,
        task_description: str = "",
    ) -> str:

        return FileNaming._base_and_folder(
            code,
            task_description,
        )[0]

    @staticmethod
    def code_path(
        code: str,
        task_description: str = "",
    ) -> str:

        base, folder = FileNaming._base_and_folder(
            code,
            task_description,
        )

        if folder:
            return f"src/{folder}/{base}.ts"

        return f"src/{base}.ts"

    @staticmethod
    def test_path(
        code: str,
        task_description: str = "",
    ) -> str:

        return f"tests/{FileNaming.base_name(code, task_description)}.test.ts"
