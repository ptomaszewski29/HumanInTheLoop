import re

from models.generated_file import GeneratedFile
from models.structure_report import StructureReport

# import ... from "./x";  export ... from "./x";  import "./x";
MODULE_REFERENCE = re.compile(
    r"""(?:import|export)\s+
        (?:(?P<clause>[\s\S]*?)\s+from\s+)?
        ['"](?P<target>[^'"]+)['"]""",
    re.VERBOSE,
)

NAMED_CLAUSE = re.compile(r"\{(?P<names>[^}]*)\}")

IDENTIFIER = r"[A-Za-z_$][A-Za-z0-9_$]*"

EXPORTED_DECLARATION = re.compile(
    r"\bexport\s+(?:declare\s+)?(?:abstract\s+)?"
    r"(?:default\s+)?"
    r"(?:class|interface|type|enum|function|const|let|var)\s+"
    rf"({IDENTIFIER})"
)

EXPORTED_LIST = re.compile(r"\bexport\s*\{([^}]*)\}")

EXPORT_STAR = re.compile(r"\bexport\s*\*\s*from")

DEFAULT_EXPORT = re.compile(r"\bexport\s+default\b")

SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".mjs")

# A PascalCase name in one of these positions is a class
# or interface, so it has to come from somewhere.
USED_SYMBOL = re.compile(
    rf"\b(?:new|implements|extends)\s+({IDENTIFIER})"
)

DECLARED_LOCALLY = re.compile(
    r"\b(?:abstract\s+)?"
    r"(?:class|interface|type|enum|function|const|let|var)\s+"
    rf"({IDENTIFIER})"
)

IMPORT_CLAUSE = re.compile(
    r"\bimport\s+(?P<clause>[\s\S]*?)\s+from\s+['\"]"
)

NAMESPACE_IMPORT = re.compile(
    rf"\*\s*as\s+({IDENTIFIER})"
)

# Names TypeScript and the runtime provide, which are
# never imported and must not be reported as missing.
AMBIENT_SYMBOLS = frozenset(
    {
        "AbortController",
        "Array",
        "ArrayBuffer",
        "Blob",
        "Boolean",
        "Buffer",
        "DataView",
        "Date",
        "Error",
        "Event",
        "EventTarget",
        "EvalError",
        "Float32Array",
        "Float64Array",
        "Function",
        "Headers",
        "Int8Array",
        "Int16Array",
        "Int32Array",
        "Intl",
        "JSON",
        "Map",
        "Math",
        "Number",
        "Object",
        "Promise",
        "Proxy",
        "RangeError",
        "ReferenceError",
        "Reflect",
        "RegExp",
        "Request",
        "Response",
        "Set",
        "String",
        "Symbol",
        "SyntaxError",
        "TextDecoder",
        "TextEncoder",
        "TypeError",
        "URIError",
        "URL",
        "URLSearchParams",
        "Uint8Array",
        "Uint16Array",
        "Uint32Array",
        "WeakMap",
        "WeakSet",
        "WebSocket",
    }
)

# Requirement words that describe a design quality rather
# than an artifact, so their absence from the code is not
# a missing file.
NON_FILE_REQUIREMENTS = frozenset(
    {
        "abstraction",
        "architecture",
        "clean",
        "coupling",
        "dependency",
        "design",
        "injection",
        "interface",
        "interfaces",
        "inversion",
        "maintainable",
        "pattern",
        "patterns",
        "principle",
        "principles",
        "readable",
        "reusable",
        "scalable",
        "solid",
        "testable",
        "typescript",
    }
)


def directory_of(path: str) -> str:

    return path.rsplit("/", 1)[0] if "/" in path else ""


def normalise(path: str) -> str:
    """Collapses . and .. in a repository-relative path."""

    parts: list[str] = []

    for segment in path.split("/"):

        if segment in ("", "."):
            continue

        if segment == "..":

            if parts:
                parts.pop()

            continue

        parts.append(segment)

    return "/".join(parts)


class StructureValidator:
    """Checks a file set the way a compiler would.

    Imports, exports and requirement coverage are decided
    here rather than asked of the model, because they are
    facts about the files rather than matters of judgement.
    """

    @staticmethod
    def imports(
        content: str,
    ) -> list[tuple[str, list[str]]]:
        """Every module this file references, with symbols."""

        found: list[tuple[str, list[str]]] = []

        for match in MODULE_REFERENCE.finditer(content):

            target = match.group("target")

            clause = match.group("clause") or ""

            names: list[str] = []

            named = NAMED_CLAUSE.search(clause)

            if named:

                for raw in named.group("names").split(","):

                    name = raw.strip().split(" as ")[0].strip()

                    if re.fullmatch(IDENTIFIER, name or ""):
                        names.append(name)

            found.append((target, names))

        return found

    @staticmethod
    def exports(content: str) -> set[str]:

        names = {
            match.group(1)
            for match in EXPORTED_DECLARATION.finditer(
                content
            )
        }

        for match in EXPORTED_LIST.finditer(content):

            for raw in match.group(1).split(","):

                name = raw.strip().split(" as ")[-1].strip()

                if re.fullmatch(IDENTIFIER, name or ""):
                    names.add(name)

        return names

    @staticmethod
    def imported_names(content: str) -> set[str]:
        """Every name this file brings in from elsewhere."""

        names: set[str] = set()

        for match in IMPORT_CLAUSE.finditer(content):

            clause = match.group("clause")

            namespace = NAMESPACE_IMPORT.search(clause)

            if namespace:
                names.add(namespace.group(1))

            named = NAMED_CLAUSE.search(clause)

            if named:

                for raw in named.group("names").split(","):

                    name = raw.strip().split(" as ")[-1].strip()

                    if re.fullmatch(IDENTIFIER, name or ""):
                        names.add(name)

            # The default import sits before any brace.
            head = clause.split("{")[0].split(",")[0].strip()

            if re.fullmatch(IDENTIFIER, head or ""):
                names.add(head)

        return names

    @staticmethod
    def undefined_symbols(content: str) -> list[str]:
        """Classes used here but neither declared nor imported."""

        available = (
            {
                match.group(1)
                for match in DECLARED_LOCALLY.finditer(content)
            }
            | StructureValidator.imported_names(content)
            | AMBIENT_SYMBOLS
        )

        missing: list[str] = []

        for match in USED_SYMBOL.finditer(content):

            name = match.group(1)

            if not name[0].isupper():
                continue

            if name in available or name in missing:
                continue

            missing.append(name)

        return missing

    @staticmethod
    def resolve(
        importer: str,
        target: str,
        known: set[str],
    ) -> str | None:
        """The file a relative import points at, if any."""

        if not target.startswith("."):
            return None

        base = normalise(
            f"{directory_of(importer)}/{target}"
        )

        candidates = [
            base,
            *[
                f"{base}{suffix}"
                for suffix in SOURCE_SUFFIXES
            ],
            *[
                f"{base}/index{suffix}"
                for suffix in SOURCE_SUFFIXES
            ],
        ]

        for candidate in candidates:

            if candidate in known:
                return candidate

        return None

    @staticmethod
    def requirements(task_description: str) -> list[str]:
        """The bullet requirements that name an artifact."""

        wanted: list[str] = []

        for line in task_description.splitlines():

            stripped = line.strip()

            if not stripped.startswith(("-", "*")):
                continue

            text = stripped.lstrip("-* ").strip()

            words = re.findall(r"[A-Za-z]+", text.lower())

            if not words or len(words) > 2:
                continue

            if any(
                word in NON_FILE_REQUIREMENTS
                for word in words
            ):
                continue

            wanted.append(words[0])

        return wanted

    @staticmethod
    def validate(
        files: list[GeneratedFile],
        task_description: str = "",
        existing=None,
    ) -> StructureReport:
        """Checks a file set, optionally against a repository.

        'existing' is a RepositorySurvey. Without it, every
        import has to resolve inside this task's own
        output, which is right for a task on an empty
        folder and wrong for every later one: importing a
        file an earlier task wrote would be reported as
        importing a file that does not exist.
        """

        report = StructureReport(file_count=len(files))

        known = {item.path for item in files}

        content_by_path = {
            item.path: item.content for item in files
        }

        exports_by_path = {
            item.path: StructureValidator.exports(
                item.content
            )
            for item in files
        }

        # What is on disk counts as known, but anything
        # this task wrote wins: it is the newer version of
        # the same file.
        opaque: set[str] = set()

        if existing is not None:

            known |= set(existing.files) | set(
                existing.exports
            )

            opaque = set(existing.opaque)

            for path, names in existing.exports.items():

                exports_by_path.setdefault(path, names)

        graph: dict[str, set[str]] = {
            item.path: set() for item in files
        }

        for item in files:

            for target, names in StructureValidator.imports(
                item.content
            ):

                report.import_count += 1

                if not target.startswith("."):
                    continue

                resolved = StructureValidator.resolve(
                    item.path,
                    target,
                    known,
                )

                if resolved is None:

                    report.missing_files.append(
                        f"{item.path} imports '{target}' "
                        "but no such file was generated"
                    )

                    continue

                # A file already in the repository whose
                # exports could not be read: the import may
                # be perfectly good, so it is not a finding.
                if resolved in opaque:

                    if resolved in graph:
                        graph[item.path].add(resolved)

                    continue

                graph[item.path].add(resolved)

                target_content = content_by_path.get(
                    resolved, ""
                )

                # A star re-export or a default export can
                # supply a name this pass cannot see.
                if EXPORT_STAR.search(
                    target_content
                ) or DEFAULT_EXPORT.search(target_content):
                    continue

                available = exports_by_path.get(
                    resolved, set()
                )

                for name in names:

                    if name not in available:

                        report.broken_imports.append(
                            f"{item.path} imports '{name}' "
                            f"from '{target}', which does "
                            "not export it"
                        )

        for item in files:

            for name in StructureValidator.undefined_symbols(
                item.content
            ):

                report.broken_imports.append(
                    f"{item.path} uses '{name}' but never "
                    "declares or imports it"
                )

        report.cycle_paths = (
            StructureValidator.find_cycle_paths(graph)
        )

        report.cycles = [
            "Circular dependency: " + " -> ".join(loop)
            for loop in report.cycle_paths
        ]

        report.uncovered_requirements = (
            StructureValidator.find_uncovered(
                files,
                task_description,
            )
        )

        return report

    @staticmethod
    def find_cycle_paths(
        graph: dict[str, set[str]],
    ) -> list[list[str]]:
        """Each cycle as the files it runs through.

        The path is what makes a cycle fixable: a sentence
        saying one exists leaves the developer guessing
        which import to drop, and three rounds of guessing
        is what it cost before this returned the route.
        """

        paths: list[list[str]] = []

        seen: set[str] = set()

        def walk(node: str, trail: list[str]) -> None:

            if node in trail:

                loop = trail[trail.index(node) :] + [node]

                key = " ".join(sorted(set(loop)))

                if key in seen:
                    return

                seen.add(key)

                paths.append(loop)

                return

            for neighbour in sorted(graph.get(node, ())):
                walk(neighbour, [*trail, node])

        for start in sorted(graph):
            walk(start, [])

        return paths

    @staticmethod
    def find_cycles(
        graph: dict[str, set[str]],
    ) -> list[str]:

        return [
            "Circular dependency: " + " -> ".join(loop)
            for loop in StructureValidator.find_cycle_paths(
                graph
            )
        ]

    @staticmethod
    def find_uncovered(
        files: list[GeneratedFile],
        task_description: str,
    ) -> list[str]:

        wanted = StructureValidator.requirements(
            task_description
        )

        if not wanted:
            return []

        haystack = " ".join(
            f"{item.path} {item.content}" for item in files
        ).lower()

        return [
            f"The task requires '{word}' but no generated "
            "file mentions it"
            for word in wanted
            if word not in haystack
        ]
