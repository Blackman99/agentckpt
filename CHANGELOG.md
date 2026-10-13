# Changelog

## 0.2.0 — 2026-10-13

- **`agentckpt hook`**: snapshot from agent hooks. Accepts Codex `notify` JSON as the last argument and Claude Code / Codex / Gemini CLI hook JSON on stdin. Resolves the project from the payload `cwd` and derives messages like `claude: before Edit src/app.py` or `codex: turn complete "…"`. Always exits 0 with silent stdout, so it never blocks a prompt or denies a tool call. Skips uninitialized projects unless `--init`. Parallel hooks are serialized via `.agentckpt/hook.lock`
- **`agentckpt run -- <cmd>`**: snap before and after any agent CLI and pass its exit code through
- **`examples/`**: drop-in configs for Codex (`notify` + `hooks.json`), Claude Code (`.claude/settings.json`), Gemini CLI (`.gemini/settings.json`), an OpenCode plugin, and shell wrappers
- **Safety fix:** shadow-store git calls now drop inherited `GIT_INDEX_FILE` / `GIT_DIR` / `GIT_WORK_TREE` / object-dir variables. A snap run from inside a git or agent environment could otherwise write the user's real index
- `doctor` reports a stale hook lock
- Docs: new [Agent hooks](https://blackman99.github.io/agentckpt/docs/hooks/) page

## 0.1.0 — 2026-10-09

- Initial release: `init`, `snap`, `watch`, `ls`, `diff`, `restore`, `prune`, `doctor`, `demo`
- Shadow git store under `.agentckpt/`; never touches the user's real `.git`
- Respects `.gitignore`, skips files over 10 MiB by default
- Stdlib polling watch with `--debounce`
