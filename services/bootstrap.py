import json
import os

from models.repository_context import RepositoryContext

PACKAGE_JSON = {
    "name": "generated-project",
    "private": True,
    "type": "module",
    "scripts": {"test": "vitest run"},
    "devDependencies": {
        "typescript": "^5.6.0",
        "vitest": "^2.1.0",
    },
}

TSCONFIG = {
    "compilerOptions": {
        "target": "ES2022",
        "module": "ESNext",
        "moduleResolution": "bundler",
        "strict": True,
        "esModuleInterop": True,
        "skipLibCheck": True,
        "forceConsistentCasingInFileNames": True,
        "types": ["vitest/globals"],
        "outDir": "dist",
    },
    "include": ["src", "tests"],
}

# Everything a generated TypeScript project produces that
# nobody should commit. node_modules is the one that
# matters: an install puts tens of thousands of files
# there, and one careless `git add .` carries them all
# into the history.
GITIGNORE = """node_modules/
dist/
build/
coverage/
*.tsbuildinfo

.env
.env.local

.DS_Store
Thumbs.db
"""

VITEST_CONFIG = """import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: ['tests/**/*.test.ts'],
  },
});
"""

# What each missing file is filled with. Templates, not a
# model: the contents of a tsconfig for a Vitest project
# are known exactly, and running the developer, three
# rounds of architect, QA and the test gate to produce
# fifteen lines of JSON is minutes of model time for
# something a constant does correctly every time.
TEMPLATES = {
    "package.json": json.dumps(PACKAGE_JSON, indent=2)
    + "\n",
    "tsconfig.json": json.dumps(TSCONFIG, indent=2) + "\n",
    "vitest.config.ts": VITEST_CONFIG,
    ".gitignore": GITIGNORE,
}


def bootstrap(
    repository_path: str,
    context: RepositoryContext,
) -> list[str]:
    """Writes the scaffolding this repository is missing.

    Only what is missing, and never over the top of a file
    that is there: somebody's package.json is theirs, and
    a repository arriving half configured is the normal
    case rather than the odd one.

    Returns what it created, so the run can say so. An
    empty list means there was nothing to do.
    """

    if not repository_path or not os.path.isdir(
        repository_path
    ):
        return []

    written: list[str] = []

    for name in context.missing:

        template = TEMPLATES.get(name)

        if template is None:
            continue

        absolute = os.path.join(repository_path, name)

        if os.path.exists(absolute):
            continue

        try:

            with open(
                absolute,
                "w",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(template)

        except OSError as error:

            # A folder we cannot write to is a problem for
            # the whole run, and the writer will say so
            # more clearly than this would.
            print(f"BOOTSTRAP: could not write {name} ({error})")

            continue

        written.append(name)

    return written
