# Agent hooks

New in 0.2.0. Have the agent checkpoint the tree itself: before each prompt, before each edit or shell command, and after each turn. Every config below calls one command:

```bash
agentckpt hook [--source NAME] [--init] [-m MSG] [--quiet] [payload]
```

What `agentckpt hook` does:

1. Reads the hook JSON from the **last argument** (Codex `notify`) or from **stdin** (Claude Code, Codex and Gemini CLI lifecycle hooks). An open stdin with nothing on it costs at most 3 s, never a hang.
2. Resolves the project from the payload's `cwd` and walks up to `.agentckpt/` like every other command. `--root` overrides it, and without a `cwd` it falls back to the process cwd.
3. Snaps with a message derived from the event:

    | Event | Message |
    |-------|---------|
    | Codex `notify` (`agent-turn-complete`) | `codex: turn complete "Rename foo to bar"` |
    | `UserPromptSubmit` / Gemini `BeforeAgent` | `claude: before prompt "fix the login bug"` |
    | `PreToolUse` / Gemini `BeforeTool` | `claude: before Edit src/app.py`, ``codex: before Bash `rm -rf build` ``, `codex: before apply_patch src/a.rs +1` |
    | `PostToolUse` / Gemini `AfterTool` | `gemini: after write_file notes.md` |
    | `Stop` / Gemini `AfterAgent` | `claude: turn end` |
    | `SessionStart`, `SessionEnd`, `Notification`, `PreCompact`… | `codex: session start (startup)`… |

    `-m/--message` replaces the derived message. If nothing changed since the last checkpoint, no new snapshot is written.

4. **Always exits 0, writes nothing on stdout, and never returns a decision.** Agents read hook stdout and exit codes. Plain stdout on `UserPromptSubmit` becomes model context in Claude Code and Codex, and exit 2 means *block*. So the hook never denies a `PreToolUse`, never blocks a prompt and never stops a turn, even with a bad flag, broken JSON or `git` missing. A one-line summary goes to stderr (`--quiet` drops it). `--json` prints the result on stdout for scripts. Don't use it inside agent configs.

Projects where you never ran `agentckpt init` are **skipped**, so a user-level hook config doesn't litter every directory with `.agentckpt/`. Add `--init` to opt every project in automatically.

Parallel hooks (agents launch matching hooks concurrently) are serialized with a lock file at `.agentckpt/hook.lock`. `agentckpt doctor` reports one left behind by a crash.

## Codex

=== "Post-turn: ~/.codex/config.toml"

    ```toml
    # user-level only; Codex ignores `notify` in a project .codex/config.toml
    notify = ["agentckpt", "hook", "--source", "codex"]
    ```

=== "Pre-turn / pre-edit: .codex/hooks.json"

    ```json
    {
      "hooks": {
        "UserPromptSubmit": [
          { "hooks": [ { "type": "command", "command": "agentckpt hook --source codex", "timeout": 30 } ] }
        ],
        "PreToolUse": [
          {
            "matcher": "^(apply_patch|Bash)$",
            "hooks": [ { "type": "command", "command": "agentckpt hook --source codex", "timeout": 30 } ]
          }
        ]
      }
    }
    ```

After adding hooks, open `/hooks` in Codex and trust them. Codex skips untrusted hooks. Full example: [`examples/codex`](https://github.com/Blackman99/agentckpt/tree/main/examples/codex).

## Claude Code

`.claude/settings.json` (project), `.claude/settings.local.json` or `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "agentckpt hook --source claude", "timeout": 30 } ] }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash",
        "hooks": [ { "type": "command", "command": "agentckpt hook --source claude", "timeout": 30 } ]
      }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "agentckpt hook --source claude", "timeout": 30, "async": true } ] }
    ]
  }
}
```

Keep `PreToolUse` synchronous (no `async`) so the snapshot lands before the edit. Full example: [`examples/claude-code`](https://github.com/Blackman99/agentckpt/tree/main/examples/claude-code).

## Gemini CLI

`.gemini/settings.json` or `~/.gemini/settings.json`. Timeouts are in **milliseconds**:

```json
{
  "hooks": {
    "BeforeAgent": [
      { "matcher": "*", "hooks": [ { "name": "agentckpt-before-prompt", "type": "command", "command": "agentckpt hook --source gemini --quiet", "timeout": 30000 } ] }
    ],
    "BeforeTool": [
      { "matcher": "write_file|replace|run_shell_command", "hooks": [ { "name": "agentckpt-before-tool", "type": "command", "command": "agentckpt hook --source gemini --quiet", "timeout": 30000 } ] }
    ],
    "AfterAgent": [
      { "matcher": "*", "hooks": [ { "name": "agentckpt-turn-end", "type": "command", "command": "agentckpt hook --source gemini --quiet", "timeout": 30000 } ] }
    ]
  }
}
```

Use `--quiet` here. When stdout is empty, Gemini CLI shows the hook's stderr as a system message. Full example: [`examples/gemini-cli`](https://github.com/Blackman99/agentckpt/tree/main/examples/gemini-cli).

## OpenCode

OpenCode extends through JS plugins rather than hook JSON. Copy [`examples/opencode/agentckpt.js`](https://github.com/Blackman99/agentckpt/blob/main/examples/opencode/agentckpt.js) to `.opencode/plugins/`. It snaps on `tool.execute.before` (edit / write / patch / bash) and on `session.idle`, and never throws.

## Any other agent: `agentckpt run`

```bash
agentckpt run -- aider --model sonnet      # snap, run, snap; exits with aider's exit code
alias opencode='agentckpt run -m opencode -- opencode'
```

`run` checkpoints once per session. Pass `--init` to create the store if it's missing. Ready-made shell functions: [`examples/shell`](https://github.com/Blackman99/agentckpt/tree/main/examples/shell).

## Undo

```bash
agentckpt ls                       # find "claude: before Bash `rm -rf src`"
agentckpt diff <id>
agentckpt restore <id> --force
```
