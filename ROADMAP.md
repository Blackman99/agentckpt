# Roadmap

## v0.1.0 — MVP ✅

- `init` / `snap` / `watch` / `ls` / `diff` / `restore` / `prune` / `doctor` / `demo`
- Shadow git store under `.agentckpt/`, respects `.gitignore`, size-caps large files
- Never touches the user's real git index or branches
- Stdlib-only polling watch, `--json` where useful, exit codes for scripting

## v0.2 — Agent hooks

- Drop-in snippets for Codex `notify`, Claude Code hooks, OpenCode, Gemini CLI
- Optional pre-turn / post-turn auto-snap helpers
- Example configs in `examples/`

## v0.3 — Selective restore & quotas

- Interactive / path-filtered restore UX
- Ignore overrides (`.agentckptignore`)
- Compression and store quota

## v0.4 — MCP server

- MCP tools exposing `snap` / `ls` / `diff` / `restore` for agent runtimes

## v1.0 — Stable

- Frozen JSON schema for snapshot metadata
- PyPI release, signed tags
