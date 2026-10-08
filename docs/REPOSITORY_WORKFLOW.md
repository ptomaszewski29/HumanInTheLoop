# Repository workflow

What happens to the files, from the moment you pick a folder to the moment
a pull request exists.

---

## 1. Selecting a repository

Sidebar → **📦 Repositories** → **➕ Add repository**. A name and a path to
an existing folder.

- The folder must already exist; the app will not create it.
- It does not have to be a git repository. Generation works either way; the
  commit, push and pull request stages need one.
- The same folder cannot be registered twice.
- A task creation is blocked until a repository is selected.

Removing a repository asks for confirmation when tasks are linked to it,
and says how many. Removal does not delete those tasks: each one also
stores the **path** it wrote to, so re-adding the same folder reconnects
them, and their files stay readable even while it is unregistered.

---

## 2. Generating files

The Developer returns a file set as JSON. Each path is validated before
anything is written:

- rejected: `..` in any segment, absolute paths, drive letters, control
  characters, empty segments
- rejected, not repaired: stripping the dangerous part of `../x.ts` would
  turn it into a legitimate-looking `x.ts` that then gets written
- normalised: a leading `./`, Windows separators

Paths are then resolved against the repository root and checked again, so a
path that survives validation still cannot escape the folder.

Where the files land is derived from the code itself:

| Generated code | Path |
|---|---|
| `export class NotificationService` | `src/services/notification.service.ts` |
| `export class EmailValidator` | `src/validators/email.validator.ts` |
| `export interface Notifier` | `src/notifier.ts` |
| a file declaring many classes | named after the task, e.g. `src/notification-system.ts` |

Tests go to `tests/<same stem>.test.ts`.

Existing files are **overwritten**. That is visible afterwards in the Diff
Review tab as `modified`, but it is a reason to point this at a sandbox
rather than at work you care about.

---

## 3. Reviewing the diff

Before you approve, the Diff Review tab shows what the generated files
would change **in git terms**, not on disk. The files are already written
by the time you look, so the disk is not a baseline; git HEAD is.

| Verdict | Meaning |
|---|---|
| `added` | git has never seen this file |
| `modified` | it differs from the committed version |
| `unchanged` | identical to what is committed |
| `deleted` | the task claims a file that is not on disk |

The whole pass is read-only. A test asserts that generating a diff leaves
the working tree and HEAD untouched.

Without git there is no baseline, so every file reads as `added` and the
gate still works.

---

## 4. Committing

Approval creates `feature/task-<first 8 characters of the task id>` and
commits.

**The branch is cut from the base branch** (`main`, else `master`), not
from whatever was checked out. Without that, the second task would branch
off the first, and its pull request would carry the first task's commits.
If there is no base branch yet, the current HEAD is used.

**Only the files this task generated are staged.** Not `git add .`. Work
in progress elsewhere in your repository is left alone, and a test proves
it by keeping an unrelated file in the repository and asserting it never
reaches the commit.

The commit message carries the task, the architecture score, the
recommendation and the file list.

---

## 5. Pushing

A separate click. It validates first:

- the task is approved
- a local commit exists
- the folder is a git repository
- a remote named `origin` is configured

The push sends one branch, fully qualified
(`refs/heads/x:refs/heads/x`), so it can only create or fast-forward. Force,
delete, mirror, tags and `--all` are refused.

A failure records why and changes nothing else: the approval stands, the
local commit stands, and you can retry.

---

## 6. Opening a pull request

Another separate click, needing `GITHUB_PAT` in `.env`.

The base is the repository's default branch, read from the GitHub API
rather than assumed. If a pull request already exists for the branch, it is
reused rather than duplicated.

The description is built from the run: summary, architecture score,
recommendation, review iterations, generated files, generated tests,
structural findings, blockers, warnings and suggestions.

A failure records why — authentication, rate limit, missing repository,
network — and leaves the push and the approval untouched.

---

## What this looks like in a repository

After three tasks against a repository with `main`:

```text
main
 ├── feature/task-a1b2c3d4   one commit, this task's files only
 ├── feature/task-e5f6a7b8   one commit, this task's files only
 └── feature/task-9c0d1e2f   one commit, this task's files only
```

Not a chain. Each branch is independent, and each pull request shows only
its own work.
