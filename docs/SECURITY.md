# Security

The platform writes to your filesystem, runs git against your repository
and talks to GitHub with your token. These are the limits on what it can
do, and they are enforced in code rather than by convention. Every one has
a test.

---

## Why allow lists, not deny lists

A deny list protects against what you thought of. An allow list protects
against what you did not. Each layer here names what is permitted and
refuses everything else, so a future call site cannot quietly introduce an
operation nobody reviewed.

---

## Filesystem

Generated files are written only inside the selected repository folder.

Every path is validated **before** anything is created:

| Rejected | Why |
|---|---|
| `../escaped.ts` | leaves the repository |
| `src/../../escaped.ts` | leaves the repository |
| `/etc/passwd` | absolute |
| `C:/Windows/evil.ts` | absolute, drive letter |
| paths with control characters | not a real filename |
| empty path, empty segment | not a real filename |

Dangerous paths are **rejected, not cleaned up**. This matters more than it
sounds: an earlier version stripped the dangerous part, which turned
`../escaped.ts` into a legitimate-looking `escaped.ts` and wrote it. The
containment held, but the laundering was the bug.

After validation the path is resolved against the repository root and
checked again, so a path that survives the first pass still cannot escape.

A file whose path fails validation is skipped and reported; the rest of the
run continues.

---

## git

`services/git_service.py` passes arguments as lists, never through a shell,
and refuses anything not on this list:

**Allowed:** `add`, `branch`, `checkout`, `commit`, `diff`, `ls-files`,
`push`, `remote`, `rev-parse`, `status`, `symbolic-ref`

**Refused:** `pull`, `fetch`, `clone`, `rebase`, `merge`, `reset`, `tag`,
`cherry-pick`, `submodule`

Two commands are only safe in one shape, so they are checked at subcommand
level:

- `remote` may only `get-url`. It may not add, rewrite, rename or remove a
  remote.
- `push` may not pass `--force`, `-f`, `--force-with-lease`, `--delete`,
  `-d`, `--mirror`, `--all`, `--tags` or `--prune`. The refspec is fully
  qualified, so a push can only create or fast-forward one branch.

**Staging is explicit.** `git add -- <paths>`, never `git add .`. Only the
files the task generated are staged, so unrelated work in your repository
is never swept into a commit.

**Branch and remote names are validated.** A name starting with `-` would
reach git as a flag — `git checkout -b --force` is a real argument
injection — so leading dashes are rejected, along with spaces, `..`, `~`,
`^`, `:`, `?`, `*`, `[`, control characters, `@{`, and `.lock` segments.

**Credential prompts are disabled.** `GIT_TERMINAL_PROMPT=0` with empty
`GIT_ASKPASS` and `SSH_ASKPASS`, so an unauthenticated push fails with a
readable error instead of hanging the app on a prompt nobody can see.

---

## GitHub

`services/github_service.py` matches on method **and** path. Four calls
exist:

| Call | Purpose |
|---|---|
| `POST /repos/{owner}/{repo}/pulls` | create a pull request |
| `GET /repos/{owner}/{repo}/pulls` | find an existing one for a branch |
| `GET /repos/{owner}/{repo}/pulls/{n}` | read one back |
| `GET /repos/{owner}/{repo}` | read the default branch |

Everything else is refused before a request is built. Merging, closing,
deleting, commenting and reviewing are not "unimplemented" — they are
**unreachable**:

```text
PUT    /repos/o/r/pulls/1/merge        refused
PATCH  /repos/o/r/pulls/1              refused
DELETE /repos/o/r/git/refs/heads/x     refused
POST   /repos/o/r/issues/1/comments    refused
POST   /repos/o/r/pulls/1/reviews      refused
GET    /user                           refused
```

The owner and repository come from the remote URL. A remote that is not
GitHub is refused rather than guessed at.

---

## Credentials

The GitHub token is read from the environment at call time. It is never
written to the database, never logged, and stripped from any error text
before it is shown or stored.

Remote URLs of the form `https://user:token@host/...` are redacted to
`https://***@host/...` before being persisted or displayed, including
inside git's own error output.

`.env` and the SQLite database are both in `.gitignore`.

---

## The human gate

No commit, push or pull request happens without an explicit click, and each
of the three is its own click. The gate is checked in code, not only in the
UI:

- `GitAgent.can_commit` refuses any status other than `APPROVED`
- `GitAgent.can_push` additionally requires a local commit and a remote
- `PullRequestAgent.can_create` additionally requires a successful push and
  a token

A failure at any stage leaves the earlier stages intact. A failed push does
not undo the approval; a failed pull request does not undo the push.

---

## What is not protected

Honest limits:

- **Generation overwrites files whose paths collide.** You see it in the
  diff afterwards, but point this at a sandbox.
- **The structural filter is text-based.** Claims the Architect makes about
  files and imports are matched against known phrasings; a new wording
  could slip through into the review as noise. It cannot cause a wrong
  *decision*, because the recommendation comes from the validator.
- **Nothing sandboxes the generated code.** It is written to disk, not run.
