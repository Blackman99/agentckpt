# Claude Code + agentckpt

Merge the `hooks` block from [`settings.json`](settings.json) into one of:

- `.claude/settings.json`: this project, committed with the repo
- `.claude/settings.local.json`: this project, just you
- `~/.claude/settings.json`: every project (ones you never ran `agentckpt init` in are skipped)

```bash
pipx install git+https://github.com/Blackman99/agentckpt
cd your-repo && agentckpt init
```

| Event | Fires | Snapshot message |
|-------|-------|------------------|
| `UserPromptSubmit` | before Claude sees each prompt (pre-turn) | `claude: before prompt "fix the login bug"` |
| `PreToolUse` on `Edit\|Write\|MultiEdit\|NotebookEdit\|Bash` | before each file edit or shell command | `claude: before Edit src/app.py`, ``claude: before Bash `rm -rf build` `` |
| `Stop` (async) | when Claude finishes responding (post-turn) | `claude: turn end` |

Claude Code pipes the hook JSON on stdin. `agentckpt hook` reads `cwd` from it, so worktrees and `cd` inside the session land in the right store.

Safety contract:

- **Never blocks.** It always exits 0 and prints nothing on stdout, so Claude Code reads it as "no decision". The tool call goes through the normal permission flow. `PreToolUse` is never denied, and `UserPromptSubmit` never injects context.
- **Synchronous before edits.** `PreToolUse` must not be `async`, or the snapshot could race the edit. `Stop` is async because nothing waits on it.
- **Cheap when idle.** If nothing changed since the last checkpoint, no new snapshot is written.

Drop `Bash` from the matcher in huge repos if the per-command snapshot is noticeable. Undo with `agentckpt ls` → `agentckpt restore <id> --force`. Check what's wired up with `/hooks`.
