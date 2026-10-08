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
| 8.5 | **Test execution gate** — the generated tests are run, and failures send work back |

### Planning

| Sprint | What it added |
|---|---|
| 9 | **Planner agent** — an epic becomes ordered tasks with dependencies and priorities, feeding the existing pipeline unchanged |
| 9.1 | **Requirements workspace** — one place where work is described, and the planner's only input |
| 9.5 | **Execution layer** — every attempt is recorded, failures survive a restart, and a plan reports where it stands |
| 10 | **GitHub issues** — a backlog becomes requirements, and a pull request reports back to the issue it came from |

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

**9.5** — a failure that is not recorded is a failure that repeats. Before
this, a task that blew up simply reappeared as ready: the UI could not tell
"never tried" from "tried and broke". Deriving `READY`/`PENDING` is right,
because the graph knows them; deriving `FAILED` is impossible, because only
the run knows. Store the attempt, derive the rest.

**10** — a message pushed into session state is invisible unless something
on screen renders it. The second time this bit: a failure reported from the
sidebar went nowhere, because the only renderer sat inside a task's details.

**8.5** — on Windows, vitest reports failures with characters the default
codepage cannot decode, so the captured output came back empty for exactly
the runs that matter. Found by running a real failing suite, not by reading
the code.

**Across all of them** — the offline test suites caught none of these. Each
came from a real run against a real model.

---

## Next

### Sprint 10 and beyond, unbuilt

```text
Azure Boards            a second backlog, normalising into Requirement
Multi-repository plans  one requirement spanning several repositories
Review feedback         the human's comments feeding the next round
```

### Known gaps

**The test gate needs a real JS project.** A repository without
`package.json` and an installed vitest cannot be tested, and the gate says
so rather than pretending.


**The model is the weakest link.** A local 8B model will clear every
structural finding in one round and reintroduce one in the next. The gates
hold and the system refuses to approve, but generation quality is the
model's, not the pipeline's.

**The structural filter is text-based.** Claims the Architect makes about
files and imports are matched against known phrasings. A new wording could
reach the review as noise, though not as a wrong decision.

**Running a whole plan blocks the UI.** Tasks run in sequence in the
browser request; a five-task plan on a local model is a long wait with no
way to stop it part-way.
