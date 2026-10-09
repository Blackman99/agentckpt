---
title: "Your coding agent just wrecked the working tree. Here's an undo that stays out of git."
description: Coding agents edit and delete files, including ones git never tracked. agentckpt snapshots the whole working tree into a private shadow store and restores it without touching your branches or index.
---

# Your coding agent just wrecked the working tree. Here's an undo that stays out of git.

*October 2026 · [中文](agent-undo-without-touching-git-zh.md)*

You hand a task to a coding agent (Codex, Claude Code, Gemini CLI, OpenCode, a Cursor agent). It runs for a few minutes, edits a dozen files, deletes a couple, creates some new ones. The result is wrong, and now you want the tree back exactly as it was before that turn.

That sounds like what git is for. In practice it often isn't.

## Why the usual tools don't cover it

**Built-in `/undo` is missing or unreliable.** Codex removed `/undo`; [openai/codex#9203](https://github.com/openai/codex/issues/9203) asking for reliable rollback has 522 👍 and is still open. Threads like [V2EX 1218209](https://www.v2ex.com/t/1218209) and [V2EX 1220282](https://www.v2ex.com/t/1220282) describe the same thing from the user side.

**Untracked files are invisible to the obvious git commands.** Agents create and delete files git has never seen: a scratch note, a new module you haven't added yet, a config you were still editing. `git checkout -- .` and `git restore` only know about tracked content. If the agent deleted an untracked file, git has no copy of it.

**`git stash` and WIP commits touch the things you care about.** They go through your index, your reflog and often your branch. Committing "wip before agent" every turn mixes agent noise into history you later have to clean up, and a half-broken tree is not something you want on a branch at all.

What's actually needed is boring: a copy of the whole working tree, tracked and untracked, taken before (or while) the agent works, that you can put back on disk without git noticing.

## What agentckpt does

agentckpt is a small CLI that keeps a **private shadow git store** under `.agentckpt/` in your project. Every command runs git like this:

```bash
git --git-dir=.agentckpt/git --work-tree=<project root> ...
```

So the snapshot machinery is git (content-addressed, deduplicated, diffable), but it is a *separate* repository. It has its own index and its own history. Your real `.git` is never the target of `add`, `commit`, `checkout` or a branch move.

Concretely:

- **`init`** creates `.agentckpt/` and appends `.agentckpt/` to your `.gitignore` so the store never ends up in your real repo. `.agentckpt/` and `.git/` are also excluded from snapshots inside the shadow store.
- **`snap`** stages *everything* in the working tree into the shadow index (tracked and untracked, honouring your `.gitignore`), drops anything over 10 MiB by default, and commits it in the shadow store. If nothing changed since the last snapshot, it returns the existing one instead of creating an empty one.
- **`restore <id>`** reads each file out of the snapshot and writes the bytes straight into the working tree. It doesn't check out anything. If a file on disk exists and differs from the snapshot, restore **skips it and exits 1** unless you pass `--force`. Paths inside `.git/` or `.agentckpt/` are never written.
- **`watch`** polls the tree (stdlib only, no watchdog) and takes a snapshot whenever the file list, mtimes or sizes change, so you get restore points while the agent is working.
- **`diff`**, **`ls`**, **`prune`**, **`doctor`** do what you'd expect. Most commands have `--json`, and exit codes are `0` success, `1` partial (e.g. conflicts skipped), `2` hard error.

The package is pure Python 3.9+ with zero runtime dependencies; the only requirement is `git` on `PATH`. CI runs on Linux (Python 3.9 to 3.13), macOS and Windows.

## Install

agentckpt **is not on PyPI yet**. v0.1.0 is published on [GitHub Releases](https://github.com/Blackman99/agentckpt/releases/tag/v0.1.0) as a wheel and sdist. Install the wheel directly:

```bash
pipx install https://github.com/Blackman99/agentckpt/releases/download/v0.1.0/agentckpt-0.1.0-py3-none-any.whl
# or: pip install <same URL>
agentckpt --version   # agentckpt 0.1.0
```

Or try it without installing, straight from the repo:

```bash
uvx --from git+https://github.com/Blackman99/agentckpt agentckpt demo
```

`agentckpt demo` builds a throwaway project in a temp dir, snaps it, "corrupts" it, restores it, checks the conflict rule, prunes and runs `doctor`. It's the same check CI runs.

## Quick usage

```bash
cd your-project
agentckpt init
agentckpt snap -m "before agent"

# ... the agent edits, deletes and creates files ...

agentckpt ls                       # list snapshots, newest first
agentckpt diff <id>                # what changed since that snapshot
agentckpt restore <id>             # put files back, skipping ones that now differ
agentckpt restore <id> --force     # put files back, overwriting differences
agentckpt restore <id> --path src/ # only one subtree
```

Here's what that looks like on a small repo where the agent modified `a.txt` and deleted an untracked `untracked.md`:

```text
$ agentckpt restore b66469f
Skipped 1 conflict(s) (working tree differs; re-run with --force to overwrite):
  ! a.txt
Restored 2 file(s) from b66469f
  + .gitignore
  + untracked.md

$ agentckpt restore b66469f --force
Restored 3 file(s) from b66469f
  + .gitignore
  + a.txt
  + untracked.md
```

The deleted untracked file comes back, and `git log` in the real repo is unchanged.

For longer sessions, leave `agentckpt watch` running in another terminal (`--debounce 800` is the default poll interval in ms). Keep the store small with `agentckpt prune --keep 50`.

## Limits (v0.1.0)

Being honest about what it does *not* do:

- **Restore doesn't delete files.** It writes back what the snapshot has. Files the agent *created* after the snapshot stay on disk. Use `agentckpt diff <id>` to see them and remove them yourself.
- **Only what the snapshot saw.** Files matched by `.gitignore` and files over 10 MiB (change with `--max-bytes`) aren't stored. That's deliberate (no `node_modules`, no build output), but it means those can't be restored.
- **`watch` is polling, not hooks.** It snapshots when it notices a change, which may be mid-edit. A manual `snap` right before each agent turn is the cleanest restore point. Drop-in hooks for Codex, Claude Code, OpenCode and Gemini CLI are on the [roadmap](https://github.com/Blackman99/agentckpt/blob/main/ROADMAP.md) for v0.2.
- **The store lives inside the project.** `.agentckpt/` is gitignored, so something like `git clean -fdx` (or deleting the project directory) removes your snapshots too. It is an undo buffer, not a backup.
- **`.gitignore` gets one line.** `init` appends `.agentckpt/` to it. That's the only change to files you own, and it's there so the store never gets committed.
- **No selective/interactive restore UX, no quotas, no MCP server yet.** Those are v0.3 and v0.4 on the roadmap. PyPI and a frozen JSON schema are planned for v1.0.

## Try it

```bash
uvx --from git+https://github.com/Blackman99/agentckpt agentckpt demo
```

Docs: [blackman99.github.io/agentckpt/docs](https://blackman99.github.io/agentckpt/docs/) · Source (MIT): [github.com/Blackman99/agentckpt](https://github.com/Blackman99/agentckpt). Issues and agent-hook recipes are welcome.
