# Roadmap

## v0.1.0 — MVP ✅

- `init` / `snap` / `watch` / `ls` / `diff` / `restore` / `prune` / `doctor` / `demo`
- Shadow git store under `.agentckpt/`, respects `.gitignore`, size-caps large files
- Never touches the user's real git index or branches
- Stdlib-only polling watch, `--json` where useful, exit codes for scripting

## v0.2.0 — Agent hooks ✅

- `agentckpt hook`: one adapter for Codex `notify` (argv JSON) and Claude Code / Codex / Gemini CLI lifecycle hooks (stdin JSON). Always exits 0, never denies
- Pre-turn / post-turn / pre-edit auto-snap via `UserPromptSubmit`, `PreToolUse`, `Stop` (and Gemini equivalents); `agentckpt run -- <agent>` wrapper for agents without hooks
- Drop-in configs in `examples/` for Codex, Claude Code, Gemini CLI, an OpenCode plugin, and shell wrappers

## v0.3 — Selective restore & quotas

- Interactive / path-filtered restore UX
- Ignore overrides (`.agentckptignore`)
- Compression and store quota

## v0.4 — MCP server

- MCP tools exposing `snap` / `ls` / `diff` / `restore` for agent runtimes

## v1.0 — Stable

- Frozen JSON schema for snapshot metadata
- PyPI release, signed tags
