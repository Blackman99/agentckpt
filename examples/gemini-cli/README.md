# Gemini CLI + agentckpt

Merge the `hooks` block from [`settings.json`](settings.json) into `.gemini/settings.json` (project) or `~/.gemini/settings.json` (user).

```bash
pipx install git+https://github.com/Blackman99/agentckpt
cd your-repo && agentckpt init
```

| Gemini event | Fires | Snapshot message |
|--------------|-------|------------------|
| `BeforeAgent` | after you submit a prompt, before planning | `gemini: before prompt "…"` |
| `BeforeTool` on `write_file\|replace\|run_shell_command` | before file writes, edits and shell commands | `gemini: before replace src/app.ts` |
| `AfterAgent` | once per turn, after the final response | `gemini: turn end` |

Gemini CLI pipes the hook JSON on stdin. `agentckpt hook` maps Gemini's event names onto the same messages it uses for Claude Code and Codex.

Why `--quiet`: on exit 0, Gemini CLI parses stdout as JSON, and if stdout is empty it falls back to **stderr** and shows that text as a system message. `--quiet` drops agentckpt's one-line stderr summary so nothing shows up in your session. The hook always exits 0 and never returns a `deny` decision, so tools and turns go ahead unchanged.

`timeout` is in milliseconds here (Codex and Claude Code use seconds). The first time Gemini CLI sees a project hook it shows a warning before it trusts it. That's expected.
