# Architecture

The platform is a pipeline of agents with a human gate in the middle.
Everything above the gate is advice; everything below it touches your
repository.

## The one rule worth knowing

**Anything that can be decided mechanically is decided in code, not asked
of the model.**

This is not a stylistic preference. It came from watching a local 8B model
approve code with an unbalanced brace, import a file it had never
generated, and report a symbol as undefined that was exported two lines
above. Judgement is left to the model; facts are not.

In practice:

| Decided in code | Left to the model |
|---|---|
| Does this import resolve? | Is this abstraction right? |
| Is this symbol exported? | Is the coupling too tight? |
| Is there a dependency cycle? | Is the naming clear? |
| Does a blocker exist, so what is the recommendation? | What counts as a blocker? |
| In what order do planned tasks run? | How should the epic be split? |
| Which issue does this task serve? | What does the issue actually ask for? |
| Do the generated tests pass? | What should the tests assert? |
| Which file does a path belong to? | What should the file contain? |

---

## Agents

### IssueAgent — `agents/issue_agent.py`

Brings work in from a GitHub backlog and reports back to it. It reads open
issues, turns one into a Requirement, and comments once a pull request
exists.

It never closes an issue. The service can, and there is a button for it,
but nothing in the pipeline calls it: deciding that work is finished is a
human's judgement.

Owns: the link between a backlog and this platform.

### PlannerAgent — `agents/planner_agent.py`

Turns an epic into a list of tasks. The model proposes the breakdown; the
ordering, the dependency checks and the cycle detection happen in code.

A task may not depend on itself, on a task that does not exist, or sit in a
cycle without being reported: each of those is recorded on the plan and
shown, rather than quietly repaired. A truncated answer keeps the tasks the
model finished rather than being discarded.

Execution is tracked per task — see `models/task_execution.py`. The planner
decides what *may* run; the plan records what *did*.

`Plan.next_ready()` is what a run-all asks between tasks, and `Plan.log()`
and `Plan.running` are what the page draws from. All three read the stored
executions, so a run that is watched and a run that is reopened after a
restart show the same thing.

Owns: what a task *is*.
Does not own: anything about the code that task produces.

### DeveloperAgent — `agents/developer_agent.py`

Writes the source files. Returns a JSON file set, not a blob, so a task
produces the files a real project would have.

`execute` writes from scratch; `improve` receives the current files and the
review, and returns the complete set again.

When the JSON is unusable it falls back to a single file rather than
failing the run, because a model that ignores the format still produces
usable code.

Owns: the content of the files.

### ArchitectAgent — `agents/architect_agent.py`

Reviews design: dependency boundaries, the Open/Closed and Single
Responsibility principles, separation of concerns, abstraction quality,
naming, extensibility.

It is **grounded**: the structural validator runs first, its findings are
given to the Architect as already handled, and any claim the Architect
makes about missing files, missing imports, missing symbols, requirement
coverage or compilation is filtered out before it reaches the review.

It is also **stateful**: every review sees the previous rounds and must
classify each earlier finding as resolved or still open.

Owns: whether the design is sound.
Does not own: whether the code compiles.

### Structural validator — `services/structure_validator.py`

Not an agent. A deterministic pass over the generated files that reports:

- a file imported but never generated
- a symbol imported but never exported
- a class used but neither declared nor imported
- a circular dependency
- a requirement from the task with no implementation

Its findings always block, whatever the Architect decided. It understands
`export { X }`, `export * from`, `export default`, folder `index` files,
multi-line imports and parent-relative paths, so those do not produce false
positives.

Owns: whether the file set holds together.

### QAAgent — `agents/qa_agent.py`

Writes one Vitest suite per source file worth testing, as its own file.
Same JSON contract and same single-file fallback as the Developer.

Owns: the tests.

### TestExecutionAgent — `agents/test_execution_agent.py`

Runs the generated Vitest suite and reports what happened. It judges
nothing: the workflow acts on the status.

A failure or a crash sends the files back to the Developer with the test
output. A missing toolchain does not, because rewriting code cannot install
node.

This is the only place the platform executes code it did not write; the
limits are in [SECURITY.md](SECURITY.md).

Owns: whether the generated code actually works.

### GitAgent — `agents/git_agent.py`

Creates the branch, stages exactly the files the task generated, commits,
and — as a separate call — pushes.

Branches are cut from the base branch (`main` or `master`) rather than from
whatever happened to be checked out, so task branches do not stack on one
another.

Owns: local and remote git.
Does not own: anything on GitHub beyond the push.

### PullRequestAgent — `agents/pull_request_agent.py`

Opens a pull request for a pushed branch, with a description built from the
run: the task, the score, the findings and the file list. Reuses an
existing pull request for a branch instead of opening a second one.

Owns: the pull request.
Cannot: merge, close, delete or comment — those calls are not reachable.

---

## Orchestration

`workflows/workflow_orchestrator.py` runs one task:

1. Developer writes the files.
2. Architect reviews them, after the structural validator has run.
3. If any structural finding or architecture blocker remains, the files go
   back to the Developer with a brief that puts repository problems first.
   At most `MAX_REVIEW_LOOPS` rounds.
4. QA writes the tests.
5. Everything is written into the repository.
6. The diff against git HEAD is computed as review evidence.

`workflows/recommendation_policy.py` turns findings into a recommendation.
The model's own recommendation is advisory: a structural finding forces
`REQUEST_CHANGES` regardless, and an absence of blockers forces `APPROVE`
even if the model asked for changes.

`workflows/langgraph_workflow.py` is an alternative wiring of the same
agents. The Streamlit app uses the orchestrator; LangGraph is exercised by
its own test.

---

## Services

| Service | Responsibility |
|---|---|
| `structure_validator` | imports, exports, cycles, requirement coverage |
| `review_parser` | the Architect's answer into sections |
| `finding_filter` | drops claims the validator owns, caps review length |
| `file_parser` | a model's JSON into files, including truncated answers |
| `file_writer` | writes inside the repository, and nowhere else |
| `file_naming` | derives repository paths from the generated code |
| `file_bundle` | renders a file set for prompts and display |
| `test_runner` | runs vitest, reads its summary, under a timeout |
| `git_service` | local and remote git, behind an allow list |
| `git_diff_service` | what the generated files would change |
| `github_service` | the GitHub calls, behind an allow list |
| `github_issue_service` | issues: read, comment, label, close |
| `review_history_formatter` | previous rounds, for the Architect |
| `code_cleaner` | strips fences and reasoning blocks |
| `llm_factory` | picks Ollama or Gemini |

---

## Data

`models/` holds what the pipeline passes around. The two that matter most:

**`Task`** — one run end to end: the description, the generated files, the
review, the findings, the diffs, the commit, the push, the pull request and
the status.

**`Requirement`** — what someone wants built, before it becomes tasks. The
single entry point: typed by hand, or imported from an issue. The planner
reads this and nothing else.

**`Plan`** — a requirement, the tasks the planner carved out of it, and a
`TaskExecution` for each one that has been attempted.

**`TaskExecution`** — one attempt: its status, when it started, when it
ended, the error if it failed, and the `Task` row it produced. A task with
no record has not been attempted, and its status is worked out from the
dependency graph instead. Which tasks are `completed` is derived from these
records rather than stored separately, so the two cannot drift apart.

These persist to SQLite (`database/`). Columns are added by a migration
that runs on startup, so an older database keeps working — a plan saved
before executions existed has its completed list read back as a set of
`COMPLETED` records, and loses nothing.

---

## Where the human sits

```text
Requirement → Requirement → Planner → Developer → Architect ⇄ Validator → QA → Files
                          ↑                          ↓
                          └──── failing tests ── Test Gate
                                                     ↓
                                              Diff Review
                                                     ↓
                                            HUMAN APPROVAL
                                                     ↓
                                        Commit → Push → Pull Request
```

Nothing below the gate happens without an explicit click, and push and pull
request are separate clicks again. See [SECURITY.md](SECURITY.md) for what
the agents are allowed to do once past it.
