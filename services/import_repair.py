from models.generated_file import GeneratedFile
from services.structure_validator import (
    MODULE_REFERENCE,
    StructureValidator,
)


def _end_of_statement(content: str, end: int) -> int:
    """Past the semicolon and the line it sat on.

    The import pattern stops at the closing quote, so
    cutting on it alone leaves a bare ';' behind -- which
    is valid TypeScript and looks like a bug to whoever
    reads the diff.
    """

    index = end

    while index < len(content) and content[index] in " \t;":
        index += 1

    if index < len(content) and content[index] == "\r":
        index += 1

    if index < len(content) and content[index] == "\n":
        index += 1

    return index


def drop_self_imports(
    files: list[GeneratedFile],
) -> tuple[list[GeneratedFile], list[str]]:
    """Removes imports a file makes of itself.

    The commonest cycle a small model writes is a file
    importing its own path, and it is the one cycle that
    needs no judgement to break: the symbols are already
    in scope, so the import is dead weight and deleting it
    is always right.

    Every other cycle is a design question -- which of
    several real dependencies to cut -- and stays with the
    developer, told which edge to remove.

    Returns the files and a note of what was taken out,
    because a repair nobody is told about is a repair that
    hides how often the model does this.
    """

    known = {item.path for item in files}

    repaired: list[GeneratedFile] = []

    notes: list[str] = []

    for item in files:

        spans = [
            match.span()
            for match in MODULE_REFERENCE.finditer(
                item.content
            )
            if StructureValidator.resolve(
                item.path,
                match.group("target"),
                known,
            )
            == item.path
        ]

        if not spans:
            repaired.append(item)
            continue

        content = item.content

        # Back to front, so an earlier removal does not
        # shift the offsets of a later one.
        for start, end in reversed(spans):
            content = (
                content[:start]
                + content[_end_of_statement(content, end) :]
            )

        notes.append(
            f"{item.path} imported itself "
            f"{len(spans)} time(s); removed"
        )

        repaired.append(
            GeneratedFile(
                path=item.path,
                file_type=item.file_type,
                content=content.lstrip("\n"),
            )
        )

    return repaired, notes
