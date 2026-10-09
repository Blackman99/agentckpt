# Contributing

Thanks for helping! Read [GOAL.md](GOAL.md) first: every change must make agent-safe checkpoint/restore more reliable or easier to use — without touching the user's real git branches or index.

## Dev setup

```bash
git clone https://github.com/Blackman99/agentckpt && cd agentckpt
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -q
agentckpt demo
```

No runtime dependencies are allowed (stdlib + `git` on PATH). `pytest` is the only required dev dependency.

## Pull requests

- Keep PRs focused; include tests.
- `pytest -q` and `ruff check src tests --select F,E9` must pass.
- Do not add runtime deps. Prefer stdlib polling over watchdog.
- Changes that affect the shadow-store layout need a CHANGELOG entry and a `doctor` check.
