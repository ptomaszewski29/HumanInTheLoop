# Workflow

```text
Epic
  ↓
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
```

---

## Planning

A plan is optional. You can describe one task and skip the Planner
entirely.

Given an epic, the Planner returns between 2 and 12 tasks with a priority
and a dependency list each. The ordering is computed in code: dependencies
first, then priority, then id. A task whose dependencies have not run is
shown as blocked and cannot be started.

If the model produces a dependency cycle, the tasks caught in it are
reported and appended at the end rather than dropped or looped over.

**Run single task** runs one. **Run entire plan** walks the remaining tasks
in order, stopping at the first failure so you can see what went wrong.

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
