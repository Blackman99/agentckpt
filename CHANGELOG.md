# Changelog

## 0.1.0 — 2026-10-09

- Initial release: `init`, `snap`, `watch`, `ls`, `diff`, `restore`, `prune`, `doctor`, `demo`
- Shadow git store under `.agentckpt/`; never touches the user's real `.git`
- Respects `.gitignore`, skips files over 10 MiB by default
- Stdlib polling watch with `--debounce`
