# Agent hook examples

Drop-in configs that make coding agents call `agentckpt` automatically. Every one of them runs `agentckpt hook`, which:

- reads the hook JSON from the last argument (Codex `notify`) or stdin (Claude Code, Codex, Gemini CLI hooks)
- resolves the project from the payload's `cwd` (walking up to `.agentckpt/` like the rest of the CLI)
- snaps with a readable message such as `claude: before Edit src/app.py`
- **always exits 0 and prints nothing on stdout**, so it never blocks a prompt, denies a tool call or injects model context
- skips projects you never ran `agentckpt init` in (pass `--init` to opt in automatically)

| Agent | Example | Pre-turn | Pre-edit | Post-turn |
|-------|---------|----------|----------|-----------|
| Codex | [codex/](codex/) | `UserPromptSubmit` | `PreToolUse` `apply_patch\|Bash` | `notify` |
| Claude Code | [claude-code/](claude-code/) | `UserPromptSubmit` | `PreToolUse` `Edit\|Write\|…\|Bash` | `Stop` |
| Gemini CLI | [gemini-cli/](gemini-cli/) | `BeforeAgent` | `BeforeTool` `write_file\|replace\|run_shell_command` | `AfterAgent` |
| OpenCode | [opencode/](opencode/) | — | plugin `tool.execute.before` | plugin `session.idle` |
| Anything else | [shell/](shell/) | `agentckpt run --` | — | `agentckpt run --` |

Then undo any step with:

```bash
agentckpt ls
agentckpt diff <id>
agentckpt restore <id> --force
```
