# Usage

## One-time init

From your project root (walks up for `.git` if needed):

```bash
agentckpt init
```

Creates `.agentckpt/` (private git store) and ensures `.agentckpt/` is in `.gitignore`.

## Snap before an agent turn

```bash
agentckpt snap -m "before codex"
```

Includes **untracked** files, respects `.gitignore`, skips files over 10 MiB by default, never stores `.agentckpt` itself.

## Auto-snap while the agent works

```bash
agentckpt watch --debounce 800
```

Stdlib polling (no watchdog required). Takes a snapshot whenever the tree fingerprint changes.

## List and inspect

```bash
agentckpt ls
agentckpt ls --json
agentckpt diff <id>
agentckpt diff <id> --to <id2>
agentckpt diff <id> src/app.py
```

## Restore

```bash
agentckpt restore <id>              # skips conflicting files
agentckpt restore <id> --force      # overwrite divergent working-tree files
agentckpt restore <id> --path src/  # only this subtree
```

**Conflict rule:** if a working-tree file exists and its bytes differ from the snapshot, restore skips it unless `--force`. Your real `.git` index and branches are never modified.

## Housekeeping

```bash
agentckpt prune --keep 50
agentckpt doctor
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Partial failure (e.g. restore conflicts without `--force`, doctor issues) |
| 2 | Hard error (not initialized, unknown id, missing git) |
