# agentckpt

**Checkpoint a working tree while coding agents run, and restore any snapshot without touching your git branches or index.**

Coding agents (Codex, Claude Code, Gemini CLI, OpenCode, Cursor agents, …) edit and delete files. Built-in `/undo` is often missing or unreliable — see [openai/codex#9203](https://github.com/openai/codex/issues/9203) (522👍, still open) and discussions on [V2EX](https://www.v2ex.com/t/1218209).

agentckpt keeps a **private shadow git store** under `.agentckpt/`. You snap freely (including untracked files). Restore writes files into the working tree and **never** runs `git add` / `git commit` or moves branches in your real `.git`.

```bash
agentckpt init
agentckpt snap -m "before agent"
# … agent rewrites the tree …
agentckpt restore <id> --force
```

## Quick FAQ

**How big does the store get in long sessions?** Measured on a psf/requests clone, with one small edit per snap: ~4.2 MB after the first snapshot, ~9.4 MB after 200 (~27 KB each), because storage is content-addressed and unchanged files are deduplicated. Files over 10 MiB are skipped (`--max-bytes`), and `agentckpt prune --keep N` (default 50) trims old snapshots.

**What about `.gitignore` and big build dirs?** `.gitignore` is respected, so `build/`, `node_modules/`, `.venv/` and similar are never stored. To capture a specific ignored path, list it in `include_ignored`. To keep committed files out of snapshots (a checked-in `dist/`, fixture dumps), list them in `.agentckptignore`, which uses `.gitignore` syntax and only affects snapshots (on `main`, ships in the next release).

**Ignored `.env` or generated config?** Contents are not stored by default. Each snap records metadata only (path, size, mtime, hash), and `restore` warns if these files changed or went missing. Opt in with `include_ignored`; secret-looking files also need `allow_secrets = true` and are stored unencrypted. *Released in v0.3.0* ([#4](https://github.com/Blackman99/agentckpt/issues/4)). Details: [configuration](configuration.md).

## Next

- [Install](install.md)
- [Usage](usage.md)
- [Agent hooks](hooks.md): Codex, Claude Code, Gemini CLI, OpenCode
- [Command reference](reference.md)
- [FAQ](faq.md)
- [Blog](blog/index.md): [English intro](blog/agent-undo-without-touching-git.md) · [中文介绍](blog/agent-undo-without-touching-git-zh.md)
