# Workflow

```text
Requirement                   typed by hand, or imported
  ↓                           from a GitHub issue
Planner Agent                 breaks it into ordered tasks
  ↓
Task
  ↓
Developer  ──────────────┐    writes the source files
  ↓                      │
Architect                │    reviews the design
  ↓                      │    work goes back while anything blocks
Structural Validator ────┘    checks imports, symbols, cycles
  ↓
QA                            writes the tests
  ↓
Generated Files               written into the repository
  ↓
Test Execution                the suite is run; failures send work back
  ↓
Diff Review                   what would change, read from git
  ↓
HUMAN APPROVAL                nothing below here is automatic
  ↓
Local Commit                  on a branch cut from the base
  ↓
Remote Push                   a separate click
  ↓
Pull Request                  another separate click
  ↓
Issue Comment                 if the work came from an issue
```

---

## Where work comes from

Everything enters as a **Requirement**: a title and a description, written
in the workspace or imported from a GitHub issue. The planner reads a
Requirement and nothing else, so a new backlog source only has to produce
one rather than grow its own path into the pipeline.

Importing the same issue twice updates the requirement it produced instead
of making a second one.

A requirement's status is derived from the plans it produced, never stored:

| Status | Meaning |
|---|---|
| `DRAFT` | written, not planned |
| `PLANNED` | a plan exists, nothing has run |
| `EXECUTING` | some tasks have run, some remain |
| `COMPLETED` | every planned task has run |

Once a pull request exists, the issue a task came from gets a comment with
the architecture score, the recommendation, the test result and the pull
request URL, and its labels are updated. **The issue is never closed
automatically** — deciding the work is done is a judgement, so it stays a
button a human presses.

---

## Planning

A plan is optional. You can describe one task and skip the Planner
entirely.

Given an epic, the Planner returns between 2 and 12 tasks with a priority
and a dependency list each. The ordering is computed in code: dependencies
first, then priority, then id. A task whose dependencies have not run is
shown as blocked and cannot be started.

The breakdown the model proposes is validated before it is shown. Three
things are reported rather than quietly repaired:

| Problem | What happens |
|---|---|
| a task depends on itself | the dependency is dropped, and said so |
| a task depends on an id the plan does not contain | the same |
| two or more tasks form a cycle | they are named, and listed last |

The plan stays usable in every case — the point of reporting is that you
see what the model got wrong, instead of a graph that was silently edited
into shape behind you.

The **Dependency graph** panel shows the tasks as layers: everything in one
step can run once the steps above it are done.

**Run single task** runs one. **Run entire plan** walks the remaining tasks
in order, stopping at the first failure so you can see what went wrong.

### What a plan remembers

Every attempt is recorded, not just the successes. A task that was started
holds a status, when it began, when it ended, and — if it went wrong — why.

| Status | Meaning |
|---|---|
| `PENDING` | a dependency has not completed yet; cannot be started |
| `READY` | every dependency is done; the run button is enabled |
| `RUNNING` | started and not yet finished |
| `COMPLETED` | finished, and its dependents are now unblocked |
| `FAILED` | it ran and did not finish; the reason is shown |

Only `PENDING` and `READY` are worked out from the dependency graph. The
other three are facts about a run that happened, so they are stored and
survive a restart — a failure is still a failure after the app is closed,
and the tasks that depended on it stay blocked.

A failed task keeps a **Run again** button. Retrying replaces the old
record rather than adding a second one, so the dashboard above the plan
always counts each task once:

```text
Total   Completed   Running   Ready   Blocked   Failed
  7         3           1       1        1         1
```

A run interrupted part-way — the browser closed, the process killed —
reads as `RUNNING` when you come back, which is honest: nobody knows
whether it finished. It too offers **Run again**.

### Watching a run happen

**Run entire plan** does **one task per script run**, not all of them in a
single pass. The sequence for each task is:

1. The task is marked `RUNNING` and written to SQLite.
2. The page is drawn from what is now stored — the banner, the dashboard,
   the progress bar and the log all show the task as running.
3. Only then does the work start.
4. When it ends, the outcome is written and the page reruns, which picks up
   the next task.

The order matters. Persisting before drawing is what makes a run watchable:
the dashboard moves while the plan is running instead of jumping from 0 to
11 at the end, and a failure appears the moment it happens rather than when
the last task gives up.

While a run is in flight the per-task buttons are disabled and the run-all
button becomes **Stop after this task** — the click lands on the next
script run, which is the one that would have started the following task.

The **Execution log** is built from the stored executions rather than
appended to as the run goes, so the log you see after a restart is the same
log that was on screen before it:

```text
09:30 ▶️  Started    — task 1: Create the interface
09:32 ✅  Completed  — task 1: Create the interface
09:32 ▶️  Started    — task 2: Create the provider
09:35 ❌  Failed     — task 2: Create the provider · no files returned
```

---

## The review loop

Each round:

1. The structural validator runs over the current files.
2. Its findings go to the Architect as *already handled* — the Architect is
   told not to repeat them and not to look for more of their kind.
3. The Architect returns findings classified as blockers, warnings or
   suggestions, plus which of the previous round's findings it considers
   resolved.
4. Claims about files, imports, symbols, requirements or compilation are
   dropped from the Architect's answer, because the validator owns those.
5. The recommendation is computed: any structural finding or blocker means
   `REQUEST_CHANGES`.

The loop continues while structural findings or blockers remain, up to
`MAX_REVIEW_LOOPS` rounds. Warnings and suggestions never send work back —
they are recorded and shipped with the task.

The Architect sees every previous round, so the review reads as a
conversation rather than a fresh opinion each time:

```text
Iteration 1   score 60   3 structural, 1 blocker    REQUEST_CHANGES
Iteration 2   score 90   0 structural, 1 blocker    REQUEST_CHANGES
Iteration 3   score 95   0 structural, 0 blockers   APPROVE
```

---

## The test gate

After the files are written, the generated Vitest suite is run.

| Outcome | What happens |
|---|---|
| all pass | the task continues to the human |
| some fail | the files go back to the Developer with the failures |
| the run crashes | same: the Developer is told it did not complete |
| node or vitest missing | the gate is skipped and says so loudly |

The last row is a deliberate departure from treating every failure the
same. A missing toolchain is not something the Developer can fix by
rewriting code, so looping would burn review rounds for nothing. The task
proceeds, and the UI says plainly that you are reviewing untested code.

`MAX_TEST_LOOPS` bounds the retries. Each one repeats the Developer,
Architect and QA stages, so it is expensive on a local model; the default
is one.

---

## Severity

| Level | Meaning | Effect |
|---|---|---|
| Structural | the file set does not hold together | always `REQUEST_CHANGES` |
| Blocker | the design must change before shipping | `REQUEST_CHANGES` |
| Warning | should be fixed, does not block | recorded, shipped |
| Suggestion | optional improvement | recorded, shipped |

The model's own recommendation is advisory. A structural finding overrides
an `APPROVE`; an absence of blockers overrides a `REQUEST_CHANGES`.

---

## The human gate

By the time you are asked, you can see:

- every generated file, read back from disk
- the diff each one would make against git HEAD
- what the Architect found, separated from what the validator found
- every review round and what it resolved
- the branch name and the commit message that would be used

**Approve** commits. **Reject** does nothing to git.

Approval never fails because of git: if the folder is not a repository, or
the commit cannot be made, the task is still approved and you are told why
nothing was committed.

---

## After approval

Push and pull request are separate, deliberate actions. Neither is a side
effect of approval, and a failure in either leaves everything before it
intact:

- a failed push does not undo the approval or the local commit
- a failed pull request does not undo the push

Both record what went wrong and let you retry.

See [REPOSITORY_WORKFLOW.md](REPOSITORY_WORKFLOW.md) for what happens to
the files themselves.
