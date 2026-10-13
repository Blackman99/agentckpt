# Shell wrapper (any agent)

For agents without hooks, or as a coarse layer on top of them, wrap the CLI:

```bash
agentckpt run -- aider --model sonnet
# run: before aider --model sonnet         <- snapshot
# … agent session …
# run: after aider --model sonnet (exit 0) <- snapshot
```

`agentckpt run` snaps, runs the command with your terminal attached, snaps again, and exits with the command's exit code. If the project isn't initialized it warns and still runs the command. Pass `--init` to create the store.

[`agentckpt-aliases.sh`](agentckpt-aliases.sh) has ready-made shell functions (`aider`, `cursor-agent`, `opencode`, and a generic `ackpt`). Source it from your shell rc.

PowerShell:

```powershell
function aider { agentckpt run -m aider -- aider.exe @args }
```

Wrappers checkpoint per **session**. For per-prompt and per-edit checkpoints, use the hook examples for [Codex](../codex/), [Claude Code](../claude-code/), [Gemini CLI](../gemini-cli/) or [OpenCode](../opencode/).
