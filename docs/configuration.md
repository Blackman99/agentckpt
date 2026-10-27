# Configuration

agentckpt is intentionally config-light. Besides an optional [`.agentckptignore`](#agentckptignore), the only config file is the optional `agentckpt.toml` (or `[tool.agentckpt]` in `pyproject.toml`), and it controls only the [gitignored-file](#gitignored-files-env-generated-config-build-output) behaviour.

## Store location

Always `<project-root>/.agentckpt/`.

- Detect root: walk up for an existing `.agentckpt/`, else for `.git`, else use cwd.
- Override on init: `agentckpt init --root /path/to/project`

## Ignore rules

1. Your project's `.gitignore` (and nested ones) — respected via shadow `git add`.
2. `.agentckptignore` at the project root (optional, see below).
3. Always excluded: `.agentckpt/`, `.git/`.
4. Large files: `--max-bytes` on `snap` (default `10485760` = 10 MiB). Skipped paths are printed to stderr.

### `.agentckptignore`

Some files belong in your git repo but not in agent snapshots: a committed `dist/` bundle, fixture
dumps, a big lockfile cache, or logs a test run rewrites every turn. List them in `.agentckptignore`
at the project root. It uses `.gitignore` syntax (globs, `dir/`, `!negation`, `#` comments):

```gitignore
# .agentckptignore
dist/
logs/*.log
!logs/keep.log
fixtures/*.sql
```

- It only affects snapshots. Your own `git status` and `.gitignore` are untouched.
- `snap`, `watch` and agent hooks all pick it up on the next run. Adding a pattern drops those paths
  from the *next* snapshot; older snapshots still hold them and can restore them.
- `restore` never deletes excluded files, and they don't show up in the gitignored-file warnings.
- It can only exclude more. A `!` line can't bring back something `.gitignore` ignores (use
  [`include_ignored`](#opting-in-to-capture) for that), and it can never include `.agentckpt/` or `.git/`.
- `agentckpt doctor` shows how many patterns it found.

## Gitignored files (`.env`, generated config, build output)

Gitignored files are **never stored by default**, and `restore` never writes or deletes them.
Your local `.env` is left alone. What agentckpt does instead:

- **Manifest (on by default).** Every `snap` records metadata for each gitignored file: path,
  size, mtime and a SHA-256. It never records contents, and secret-looking files (see the list
  below) get no hash at all, only size and mtime. The manifest lives in
  `.agentckpt/manifests/<snapshot>.json`.
- **Restore warning.** `agentckpt restore` compares the snapshot's manifest with the working tree
  and warns on stderr about gitignored files that changed, were added or went missing since that
  snapshot. They are not restored, so you know the code is back but the local state differs:

  ```text
  warning: 2 gitignored file(s) differ from snapshot a1b2c3d and were NOT restored (agentckpt only records their metadata):
    ~ changed: .env
    - missing now: build/config.json
  ```

  `--json` reports the same under `ignored_changes` (`added` / `removed` / `changed` / `truncated`).
  The warning doesn't change the exit code. Snapshots taken before this feature have no manifest
  and produce no warning.
- **Cheap by default.** Fully ignored directories are listed by git without being descended. The
  manifest doesn't walk `node_modules`, `.venv`, `venv`, `env`, `__pycache__`, `.tox`, `.nox`,
  `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.gradle`, `.next`, `.cache`, `target`,
  `site-packages` or `.eggs`, and it stops after 2,000 files (then reported as `truncated`).
  A file is re-hashed only when its size or mtime changed. Files over `--max-bytes` are compared
  by size and mtime only.

### Opting in to capture

To snapshot specific ignored paths, list them in `agentckpt.toml` at the project root, or in
`[tool.agentckpt]` in `pyproject.toml`. `agentckpt.toml` wins if both exist.

```toml
# agentckpt.toml
include_ignored = ["build/config.json", "conf.local.json", "generated/"]

# Optional knobs (defaults shown)
# allow_secrets = false
# ignored_manifest = true
# manifest_max_files = 2000
# manifest_skip_dirs = ["node_modules", ".venv", "venv", "env", "__pycache__", ...]
```

Each entry matches an exact path, everything under a directory, or an `fnmatch` glob
(`generated/*.json`). Captured files are stored like any other file, so `restore` brings them
back (with the same conflict rules and `--force`), and `--max-bytes` still applies. Remove an
entry and the next snapshot stops tracking that file.

**Secrets are refused.** Paths that look like credentials are skipped and listed on stderr, even
when `include_ignored` names them: `.env`, `.env.*`, `*.env`, `.envrc`, `*.pem`, `*.key`,
`*.p12`, `*.pfx`, `*.jks`, `*.keystore`, `*.kdbx`, `*.gpg`, `*.asc`, `id_rsa*`, `id_dsa*`,
`id_ecdsa*`, `id_ed25519*`, `.netrc`, `.npmrc`, `.pypirc`, `.pgpass`, `.htpasswd`,
`credentials*`, `*secret*`, `service-account*.json`. Set `allow_secrets = true` to capture them anyway.

> **Risk:** with `allow_secrets = true`, those files are stored as **plain, unencrypted git
> objects** in `.agentckpt/` and kept until `agentckpt prune` removes the snapshots. Anyone who can
> read your project directory can read them. Only enable it on a machine you trust, and never
> copy `.agentckpt/` anywhere.

## Watch debounce

`agentckpt watch --debounce MS` — milliseconds between polls (default `800`). Lower = snappier, more CPU.

## Environment

Uses normal `git` from `PATH`. Shadow commits set local author `agentckpt <agentckpt@local>` inside the private store only — this does **not** change your repo's `user.name` / `user.email`.
