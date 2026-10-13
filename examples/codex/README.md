# Codex + agentckpt

Two independent pieces. Use either or both.

| File | Goes in | Fires | Snapshot message |
|------|---------|-------|------------------|
| [`config.toml`](config.toml) | `~/.codex/config.toml` | after every turn (`notify`) | `codex: turn complete "…prompt…"` |
| [`hooks.json`](hooks.json) | `~/.codex/hooks.json` or `<repo>/.codex/hooks.json` | before each prompt, before `apply_patch` / shell | `codex: before prompt "…"`, `codex: before apply_patch src/app.rs` |

```bash
pipx install git+https://github.com/Blackman99/agentckpt   # agentckpt must be on PATH for Codex
cd your-repo && agentckpt init                             # opt this project in
```

## Post-turn: `notify`

```toml
# ~/.codex/config.toml
notify = ["agentckpt", "hook", "--source", "codex"]
```

Codex appends the `agent-turn-complete` JSON as the last argument. `agentckpt hook` reads its `cwd`, walks up to the project's `.agentckpt/`, and snaps. `notify` is fire-and-forget. Codex only honours it in the **user-level** config, so it fires for every project. Projects without `agentckpt init` are skipped silently. Use `["agentckpt", "hook", "--source", "codex", "--init"]` if you want every project checkpointed.

Codex allows one `notify` program. If you already use one for desktop alerts, call `agentckpt hook --source codex "$1"` from that script.

## Pre-turn and pre-edit: lifecycle hooks

Copy [`hooks.json`](hooks.json) to `~/.codex/hooks.json` (all projects) or `.codex/hooks.json` in a repo (that project only, once the project's `.codex/` layer is trusted). Then open `/hooks` in Codex and **trust** the two new hooks. Codex skips hooks it hasn't trusted.

The same thing as inline TOML in `config.toml`:

```toml
[[hooks.UserPromptSubmit]]
[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = "agentckpt hook --source codex"
timeout = 30

[[hooks.PreToolUse]]
matcher = "^(apply_patch|Bash)$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "agentckpt hook --source codex"
timeout = 30
```

Notes:

- The hook prints nothing on stdout and always exits 0, so it never adds model context, never denies a tool call and never stops a turn.
- Snaps run synchronously, so the checkpoint is taken before the edit happens. Don't set `async = true` on the `PreToolUse` hook. A background snap could race the edit it is meant to precede.
- In very large repos, drop `Bash` from the matcher (`"^apply_patch$"`) so only file edits pay for a snapshot. Unchanged trees never create a new snapshot either way.
- Undo: `agentckpt ls`, then `agentckpt restore <id> --force`.
