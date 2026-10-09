# Command reference

## `agentckpt init [--root PATH]`

Create the shadow store. Idempotent.

## `agentckpt snap [-m MSG] [--max-bytes N] [--json]`

Snapshot the working tree (tracked + untracked, gitignore-aware).

## `agentckpt watch [--debounce MS]`

Poll for changes and auto-snap. Ctrl-C to stop.

## `agentckpt ls [--json]`

List snapshots: id, time, file count, message (newest first).

## `agentckpt diff <id> [path] [--to id2] [--json]`

Diff snapshot vs working tree, or between two snapshots.

## `agentckpt restore <id> [--path P] [--force] [--json]`

Restore files from a snapshot into the working tree. Never touches real `.git`. Exit `1` if conflicts were skipped.

## `agentckpt prune [--keep N] [--json]`

Keep the newest N snapshots (default 50); rewrite the shadow history to drop older ones.

## `agentckpt doctor [--json]`

Sanity-check store, gitignore, and git on PATH. Exit `1` on issues.

## `agentckpt demo`

Self-contained temp-dir exercise for CI and README. Exit `0` on success.

## `agentckpt --version`
