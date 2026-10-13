"""Agent hook adapter tests (v0.2): argv / stdin payloads, messages, root resolution, never-deny."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agentckpt import hooks as H
from agentckpt import store as S
from agentckpt.cli import main


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    (root / "README.md").write_text("hi\n", encoding="utf-8")
    return root


def _messages(root: Path):
    return [s.message for s in S.list_snapshots(root)]


def _cli(args, *, stdin_text=None, cwd=None):
    """Run the real console entry in a subprocess (exercises argv + stdin + exit code)."""
    return subprocess.run(
        [sys.executable, "-m", "agentckpt", *args],
        input=stdin_text if stdin_text is not None else "",
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=60,
    )


# ------------------------------------------------------------------ parsing


def test_parse_payload_rejects_non_objects():
    assert H.parse_payload('{"a": 1}') == {"a": 1}
    assert H.parse_payload("") is None
    assert H.parse_payload("not json") is None
    assert H.parse_payload("[1, 2]") is None
    assert H.parse_payload('"str"') is None


def test_read_stdin_handles_text_streams_and_ttys():
    assert H.read_stdin(io.StringIO('{"x": 1}')) == '{"x": 1}'

    class FakeTTY(io.StringIO):
        def isatty(self):
            return True

    assert H.read_stdin(FakeTTY('{"x": 1}')) is None


def test_payload_prefers_argv_then_stdin():
    argv = json.dumps({"type": "agent-turn-complete", "cwd": "/a"})
    stdin = io.StringIO(json.dumps({"hook_event_name": "Stop", "cwd": "/b"}))
    obj, where = H.payload_from_inputs(argv, stdin)
    assert where == "argv" and obj["cwd"] == "/a"

    stdin = io.StringIO(json.dumps({"hook_event_name": "Stop", "cwd": "/b"}))
    obj, where = H.payload_from_inputs(None, stdin)
    assert where == "stdin" and obj["cwd"] == "/b"

    obj, where = H.payload_from_inputs("garbage", io.StringIO(""))
    assert obj is None and where == "none"


def test_normalize_event_and_source():
    assert H.normalize_event({"type": "agent-turn-complete"}) == "agent-turn-complete"
    assert H.normalize_event({"hook_event_name": "PreToolUse"}) == "PreToolUse"
    assert H.normalize_event({"hook_event_name": "BeforeTool"}) == "PreToolUse"
    assert H.normalize_event({"hook_event_name": "AfterAgent"}) == "Stop"
    assert H.normalize_event({"hook_event_name": "Stop"}, override="SessionStart") == "SessionStart"
    assert H.infer_source({"type": "agent-turn-complete"}) == "codex"
    assert H.infer_source({"hook_event_name": "BeforeAgent"}) == "gemini"
    assert H.infer_source({"hook_event_name": "PreToolUse"}) == "agent"
    assert H.infer_source({}, explicit="claude") == "claude"


# ------------------------------------------------------------------ messages


@pytest.mark.parametrize(
    "payload,source,expected",
    [
        (
            {"type": "agent-turn-complete", "input-messages": ["Rename `foo` to `bar`"]},
            "codex",
            'codex: turn complete "Rename `foo` to `bar`"',
        ),
        (
            {"hook_event_name": "UserPromptSubmit", "prompt": "fix\n  the   login bug"},
            "claude",
            'claude: before prompt "fix the login bug"',
        ),
        (
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/app.py", "old_string": "a", "new_string": "b"},
            },
            "claude",
            "claude: before Edit src/app.py",
        ),
        (
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "rm -rf build"}},
            "claude",
            "claude: before Bash `rm -rf build`",
        ),
        (
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: src/a.rs\n*** Add File: b.rs\n*** End Patch"
                },
            },
            "codex",
            "codex: before apply_patch src/a.rs +1",
        ),
        (
            {"hook_event_name": "AfterTool", "tool_name": "write_file", "tool_input": {"file_path": "x.md"}},
            "gemini",
            "gemini: after write_file x.md",
        ),
        ({"hook_event_name": "Stop"}, "claude", "claude: turn end"),
        ({"hook_event_name": "SessionStart", "source": "startup"}, "codex", "codex: session start (startup)"),
        (
            {"hook_event_name": "Notification", "message": "Claude needs your permission"},
            "claude",
            'claude: notification "Claude needs your permission"',
        ),
        ({"hook_event_name": "SomethingNew"}, "agent", "agent: SomethingNew"),
        (None, "agent", "agent: hook"),
    ],
)
def test_build_message(payload, source, expected):
    ev = H.normalize_event(payload)
    assert H.build_message(payload, source=source, event=ev) == expected


def test_build_message_is_single_line_and_bounded():
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": "word " * 500}
    msg = H.build_message(payload, source="claude", event="UserPromptSubmit")
    assert "\n" not in msg
    assert len(msg) <= H.MESSAGE_MAX
    assert msg.endswith('..."')


# ------------------------------------------------------------------ root resolution


def test_resolve_root_from_payload_cwd(proj: Path, tmp_path: Path, monkeypatch):
    S.init_store(proj)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    # payload cwd in a subdirectory walks up to the store, like the rest of the CLI
    assert H.resolve_root({"cwd": str(proj / "src")}) == proj.resolve()
    # explicit --root wins
    assert H.resolve_root({"cwd": str(proj)}, explicit_root=str(elsewhere)) == elsewhere.resolve()
    # missing / bogus cwd falls back to the process cwd
    assert H.resolve_root({"cwd": str(tmp_path / "nope")}) == elsewhere.resolve()
    assert H.resolve_root(None) == elsewhere.resolve()


# ------------------------------------------------------------------ run_hook behaviour


def test_hook_skips_uninitialized_project_without_creating_store(proj: Path):
    res = H.run_hook(payload={"hook_event_name": "Stop", "cwd": str(proj)}, source="claude")
    assert res["ok"] is False
    assert "not initialized" in res["skipped"]
    assert not (proj / ".agentckpt").exists()
    assert not (proj / ".gitignore").exists()


def test_hook_auto_init(proj: Path):
    res = H.run_hook(payload={"hook_event_name": "Stop", "cwd": str(proj)}, source="claude", auto_init=True)
    assert res["ok"] and res["created"]
    assert S.is_initialized(proj)
    assert _messages(proj) == ["claude: turn end"]


def test_hook_message_override_and_dedupe(proj: Path):
    S.init_store(proj)
    p = {"hook_event_name": "UserPromptSubmit", "prompt": "x", "cwd": str(proj)}
    r1 = H.run_hook(payload=p, message="my label")
    assert r1["created"] and r1["snapshot"]["message"] == "my label"
    r2 = H.run_hook(payload=p)
    assert r2["ok"] and not r2["created"]
    assert r2["skipped"] == "no changes since last snapshot"
    assert _messages(proj) == ["my label"]


def test_hook_never_raises(proj: Path, monkeypatch):
    S.init_store(proj)

    def boom(*a, **k):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(S, "snap", boom)
    res = H.run_hook(payload={"cwd": str(proj)})
    assert res["ok"] is False and "disk on fire" in res["skipped"]


def test_store_lock_is_exclusive_and_released(proj: Path):
    S.init_store(proj)
    with H.store_lock(proj) as got:
        assert got
        with H.store_lock(proj, wait=0.2) as got2:
            assert got2 is False
    assert not (proj / ".agentckpt" / H.LOCK_NAME).exists()
    with H.store_lock(proj, wait=0.2) as got3:
        assert got3


# ------------------------------------------------------------------ CLI contract


def test_cli_hook_codex_notify_argv(proj: Path, tmp_path: Path):
    S.init_store(proj)
    payload = {
        "type": "agent-turn-complete",
        "thread-id": "b5f6c1c2",
        "turn-id": "12345",
        "cwd": str(proj),
        "client": "codex-tui",
        "input-messages": ["Rename foo to bar"],
        "last-assistant-message": "Done.",
    }
    # Codex appends the JSON as the last argv; run from an unrelated cwd to prove cwd resolution
    proc = _cli(["hook", "--source", "codex", json.dumps(payload)], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    assert _messages(proj) == ['codex: turn complete "Rename foo to bar"']


def test_cli_hook_stdin_pretooluse_never_denies(proj: Path, tmp_path: Path):
    S.init_store(proj)
    payload = {
        "session_id": "abc",
        "cwd": str(proj),
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "rm -rf src"},
        "tool_use_id": "toolu_1",
    }
    proc = _cli(["hook", "--source", "claude"], stdin_text=json.dumps(payload), cwd=tmp_path)
    # exit 0 + empty stdout == "no decision": the tool call proceeds normally
    assert proc.returncode == 0
    assert proc.stdout == ""
    assert "deny" not in proc.stdout and "block" not in proc.stdout
    assert _messages(proj) == ["claude: before Bash `rm -rf src`"]


def test_cli_hook_userpromptsubmit_keeps_stdout_clean(proj: Path):
    # Claude Code / Codex add plain stdout on UserPromptSubmit to the model context.
    S.init_store(proj)
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": "hello", "cwd": str(proj)}
    proc = _cli(["hook", "--source", "claude"], stdin_text=json.dumps(payload))
    assert proc.returncode == 0 and proc.stdout == ""


def test_cli_hook_exit_zero_on_bad_input(proj: Path, tmp_path: Path):
    for args, stdin_text in [
        (["hook", "--definitely-not-a-flag"], ""),
        (["hook", "--max-bytes", "NaN"], ""),
        (["hook"], "{not json"),
        (["hook", "--root", str(tmp_path / "missing")], ""),
    ]:
        proc = _cli(args, stdin_text=stdin_text, cwd=proj)
        assert proc.returncode == 0, (args, proc.stderr)
        assert proc.stdout == ""


def test_cli_hook_json_output(proj: Path):
    S.init_store(proj)
    payload = {"hook_event_name": "Stop", "cwd": str(proj)}
    proc = _cli(["hook", "--json", "--source", "gemini"], stdin_text=json.dumps(payload))
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["ok"] and data["event"] == "Stop" and data["source"] == "gemini"
    assert data["snapshot"]["message"] == "gemini: turn end"


def test_cli_hook_in_process(proj: Path, monkeypatch, capsys):
    S.init_store(proj)
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "n.txt"}}
    monkeypatch.chdir(proj / "src")  # no cwd in payload: walk up from process cwd
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert main(["hook", "--source", "claude"]) == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert "claude: before Write n.txt" in out.err
    assert _messages(proj) == ["claude: before Write n.txt"]


def test_cli_run_wraps_command(proj: Path, monkeypatch):
    S.init_store(proj)
    monkeypatch.chdir(proj)
    code = main(
        [
            "run",
            "-m",
            "fake-agent",
            "--",
            sys.executable,
            "-c",
            "open('agent.txt','w').write('x'); raise SystemExit(3)",
        ]
    )
    assert code == 3
    msgs = _messages(proj)
    assert msgs[0] == "run: after fake-agent (exit 3)"
    assert msgs[1] == "run: before fake-agent"
    tip = S.current_tip(proj)
    assert "agent.txt" in S._files_in_tree(proj, tip.full_id)


def test_snap_ignores_inherited_git_index_env(proj: Path, tmp_path: Path, monkeypatch):
    # Hooks can run inside environments that export GIT_INDEX_FILE / GIT_DIR.
    fake_index = tmp_path / "user-index"
    monkeypatch.setenv("GIT_INDEX_FILE", str(fake_index))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "not-a-repo"))
    S.init_store(proj)
    snap, _ = S.snap(proj, message="env")
    assert not fake_index.exists()
    assert "src/app.py" in S._files_in_tree(proj, snap.full_id)
    assert os.environ["GIT_INDEX_FILE"] == str(fake_index)  # we don't mutate the caller's env


def test_doctor_flags_stale_hook_lock(proj: Path):
    S.init_store(proj)
    S.snap(proj, message="x")
    lock = proj / ".agentckpt" / H.LOCK_NAME
    lock.write_text("123", encoding="utf-8")
    assert S.doctor(proj)["ok"]  # fresh lock = a hook is running, not an issue
    old = lock.stat().st_mtime - H.LOCK_STALE_S - 10
    os.utime(lock, (old, old))
    rep = S.doctor(proj)
    assert not rep["ok"] and any("stale hook lock" in i for i in rep["issues"])
    # and a hook clears a stale lock instead of waiting on it forever
    (proj / "README.md").write_text("changed\n", encoding="utf-8")
    res = H.run_hook(payload={"cwd": str(proj)}, source="t")
    assert res["ok"] and res["created"]
    assert not lock.exists()


def test_message_paths_relative_to_root(proj: Path):
    S.init_store(proj)
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(proj / "src" / "app.py")},
        "cwd": str(proj),
    }
    res = H.run_hook(payload=payload, source="claude")
    assert res["message"] == "claude: before Edit src/app.py"
    # paths outside the project stay as given
    outside = {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": "/etc/hosts"}}
    msg = H.build_message(outside, source="claude", event="PreToolUse", root=proj)
    assert msg == "claude: before Write /etc/hosts"
