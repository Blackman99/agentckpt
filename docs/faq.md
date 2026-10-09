# FAQ

## Does this mess with my git branches?

No. agentckpt uses `git --git-dir=.agentckpt/git --work-tree=<root>` and never runs `git add` / `git commit` / checkout in your real `.git`.

## Why not just `git stash` / WIP commits?

Stash and WIP commits interact with your index and reflog. Agents often leave untracked files and half-broken trees you do not want on a branch. A private store keeps undo out of your history.

## What about secrets / large binaries?

Respects `.gitignore`. Files over 10 MiB are skipped by default (`--max-bytes`). Still: do not snap directories full of credentials you wouldn't commit.

## Is `/undo` in Codex / Claude Code enough?

Often not — see [openai/codex#9203](https://github.com/openai/codex/issues/9203) (`/undo` removed, 522👍) and [V2EX threads](https://www.v2ex.com/t/1218209). agentckpt is an external safety net.

## Windows?

Supported (CI runs py3.12 on windows-latest). Requires `git` on PATH.
