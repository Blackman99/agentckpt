# Goal

Automatically checkpoint a working tree (including untracked files) while coding agents run, and restore any snapshot without touching the user's git branches or index.

## Guardrails

Every change must serve that sentence. In practice:

- **Agent-safe undo.** Snapshots capture tracked *and* untracked files. Restore writes files into the working tree and never runs `git add` / `git commit` / branch moves in the user's real `.git`.
- **Shadow store only.** State lives under `.agentckpt/` (a private git repo via `--git-dir` / `--work-tree`). `.agentckpt/` must stay gitignored.
- **Zero runtime dependencies.** Stdlib + `git` on PATH. No watchdog/required extras for MVP.
- **Honest conflicts.** Restore refuses to overwrite divergent working-tree files unless `--force`, and says so clearly.
