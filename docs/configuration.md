# Configuration

agentckpt is intentionally config-light.

## Store location

Always `<project-root>/.agentckpt/`.

- Detect root: walk up for an existing `.agentckpt/`, else for `.git`, else use cwd.
- Override on init: `agentckpt init --root /path/to/project`

## Ignore rules

1. Your project's `.gitignore` (and nested ones) — respected via shadow `git add`.
2. Always excluded: `.agentckpt/`, `.git/`.
3. Large files: `--max-bytes` on `snap` (default `10485760` = 10 MiB). Skipped paths are printed to stderr.

## Watch debounce

`agentckpt watch --debounce MS` — milliseconds between polls (default `800`). Lower = snappier, more CPU.

## Environment

Uses normal `git` from `PATH`. Shadow commits set local author `agentckpt <agentckpt@local>` inside the private store only — this does **not** change your repo's `user.name` / `user.email`.
