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

## Next

- [Install](install.md)
- [Usage](usage.md)
- [Command reference](reference.md)
- [FAQ](faq.md)
- [Blog](blog/index.md): [English intro](blog/agent-undo-without-touching-git.md) · [中文介绍](blog/agent-undo-without-touching-git-zh.md)
