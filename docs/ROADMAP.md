# Roadmap

What has been built, in the order it was built, and what the next step is.

---

## Delivered

### Foundation

| Sprint | What it added |
|---|---|
| 0 | Project skeleton, virtual environment, Ruff, `.gitignore` |
| 1 | Gemini integration and a Streamlit dashboard |
| 2 | SQLite persistence and task history |
| 3 | Architect agent prototype |

### The review loop

| Sprint | What it added |
|---|---|
| 4 | Multi-agent workflow: Developer → Architect → QA |
| 4A | Structured architecture review with a score and a recommendation |
| 4B | **Stateful Architect** — every review sees the previous rounds and must say which findings were resolved |
| 4C | **Severity model** — blockers, warnings and suggestions; only blockers send work back. The recommendation is computed in code, so a lenient model cannot approve broken work |

### Repositories and files

| Sprint | What it added |
|---|---|
| 5A | **Repository awareness** — a task belongs to a real folder |
| 6 | **File generation** — code and tests written to disk, inside the repository and nowhere else |
| 6B | **Multiple files per task** — a file set, not a blob |
| 6C | **Structural validator** — a deterministic pass for broken imports, missing files, undefined symbols, cycles and requirement coverage |
| 6D | **Grounded Architect** — the Architect reviews only what cannot be checked mechanically; its claims about files and imports are filtered out |

### Source control

| Sprint | What it added |
|---|---|
| 7A | **Local git** — an approved task becomes a branch and a commit, staging only its own files |
| 7A.1 | **Diff review gate** — what would change, read from git, before you approve |
| 7B | **Remote push** — one branch, no force, no delete |
| 8 | **Pull requests** — opened with a description built from the run |
| 8.1 | **Documentation** — this set of documents |

### Planning

| Sprint | What it added |
|---|---|
| 9 | **Planner agent** — an epic becomes ordered tasks with dependencies and priorities, feeding the existing pipeline unchanged |

---

## What each sprint actually taught

Worth recording, because the architecture is shaped by these rather than by
a plan:

**4C** — a model that is asked to be helpful will approve code with an
unbalanced brace. Recommendations moved into code.

**6B** — a path sanitiser that *cleans* a dangerous path is worse than one
that rejects it: `../x.ts` became a plausible `x.ts` and got written.

**6C** — the model imported a file it had never generated and approved the
result. Imports, exports and cycles moved into a deterministic pass.

**6D** — once the validator existed, the model started duplicating its
findings and inventing new ones. Responsibility had to be split explicitly,
and the split enforced by filtering.

**7A** — branches were cut from wherever HEAD happened to be, so the second
task branched off the first. Found three sprints later, in a real
repository, by looking at the commit graph.

**Across all of them** — the offline test suites caught none of these. Each
came from a real run against a real model.

---

## Next

### Sprint 10 and beyond, unbuilt

```text
Backlog integration     GitHub Issues, Azure Boards
Multi-repository plans   one epic spanning several repositories
Review feedback          the human's comments feeding the next round
```

### Known gaps

**The model is the weakest link.** A local 8B model will clear every
structural finding in one round and reintroduce one in the next. The gates
hold and the system refuses to approve, but generation quality is the
model's, not the pipeline's.

**The structural filter is text-based.** Claims the Architect makes about
files and imports are matched against known phrasings. A new wording could
reach the review as noise, though not as a wrong decision.

**Nothing runs the generated tests.** QA writes a Vitest suite; nobody
executes it. A task can be approved with tests that do not pass.

**Running a whole plan blocks the UI.** Tasks run in sequence in the
browser request; a five-task plan on a local model is a long wait with no
way to stop it part-way.
