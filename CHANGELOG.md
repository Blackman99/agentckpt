# Changelog

## Unreleased

- **Gitignored state ([#4](https://github.com/Blackman99/agentckpt/issues/4)):** `snap` now records a metadata-only manifest of gitignored files (path, size, mtime, SHA-256; never contents, and no hash for secret-looking files). `restore` warns about gitignored files that changed, were added or went missing since the snapshot (`ignored_changes` in `--json`). Heavy dirs like `node_modules` / `.venv` are skipped, the scan is capped at 2,000 files, and files are only re-hashed when size or mtime changed
- **`include_ignored`** in `agentckpt.toml` or `[tool.agentckpt]`: opt-in capture of named gitignored paths, which `restore` then brings back. Secret-looking paths (`.env*`, `*.pem`, `*.key`, `id_*`, `.npmrc`, …) are refused unless `allow_secrets = true`. `--max-bytes` still applies
- **Fix:** files larger than `--max-bytes` are now skipped *before* `git add`, so their blobs are never written into `.agentckpt/` (previously a skipped 50 MB file still grew the store by ~53 MB until `prune`/gc). ([#2](https://github.com/Blackman99/agentckpt/issues/2))

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
