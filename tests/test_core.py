"""Core snap / restore / diff / prune / demo tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentckpt import store as S
from agentckpt.cli import main


@pytest.fixture
def repo(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_text("beta\n", encoding="utf-8")
    (root / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (root / "noise.log").write_text("ignore me\n", encoding="utf-8")
    return root


def test_init_and_gitignore(repo: Path, monkeypatch):
    monkeypatch.chdir(repo)
    root, created = S.init_store(repo)
    assert created
    assert S.is_initialized(repo)
    assert ".agentckpt/" in (repo / ".gitignore").read_text(encoding="utf-8")
    # second init is idempotent
    _, created2 = S.init_store(repo)
    assert not created2


def test_snap_includes_untracked_respects_gitignore(repo: Path):
    S.init_store(repo)
    snap, skipped = S.snap(repo, message="first")
    assert snap.message == "first"
    assert snap.file_count >= 2
    names = S._files_in_tree(repo, snap.full_id)
    assert "a.txt" in names
    assert "sub/b.txt" in names
    assert "noise.log" not in names
    assert not any(n.startswith(".agentckpt") for n in names)
    assert skipped == []


def test_snap_skips_large_files(repo: Path):
    S.init_store(repo)
    big = repo / "big.bin"
    big.write_bytes(b"x" * (1024 * 100))  # 100 KiB
    snap, skipped = S.snap(repo, message="cap", max_bytes=1024)
    assert "big.bin" in skipped
    names = S._files_in_tree(repo, snap.full_id)
    assert "big.bin" not in names


def test_restore_and_conflict(repo: Path):
    S.init_store(repo)
    s1, _ = S.snap(repo, message="v1")
    (repo / "a.txt").write_text("changed by agent\n", encoding="utf-8")
    s2, _ = S.snap(repo, message="v2")

    # restore s1 with force
    result = S.restore(repo, s1.id, force=True)
    assert (repo / "a.txt").read_text(encoding="utf-8") == "alpha\n"
    assert "a.txt" in result["restored"]

    # conflict without force
    (repo / "a.txt").write_text("local\n", encoding="utf-8")
    result = S.restore(repo, s1.id, force=False)
    assert "a.txt" in result["skipped_conflict"]
    assert (repo / "a.txt").read_text(encoding="utf-8") == "local\n"


def test_restore_path_filter(repo: Path):
    S.init_store(repo)
    s1, _ = S.snap(repo, message="v1")
    (repo / "a.txt").write_text("AA\n", encoding="utf-8")
    (repo / "sub" / "b.txt").write_text("BB\n", encoding="utf-8")
    S.restore(repo, s1.id, path="sub/b.txt", force=True)
    assert (repo / "sub" / "b.txt").read_text(encoding="utf-8") == "beta\n"
    assert (repo / "a.txt").read_text(encoding="utf-8") == "AA\n"


def test_diff(repo: Path):
    S.init_store(repo)
    s1, _ = S.snap(repo, message="v1")
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    text = S.diff_snapshot(repo, s1.id)
    assert "a.txt" in text
    s2, _ = S.snap(repo, message="v2")
    text2 = S.diff_snapshot(repo, s1.id, to_id=s2.id)
    assert "a.txt" in text2


def test_prune(repo: Path):
    S.init_store(repo)
    ids = []
    for i in range(5):
        (repo / "a.txt").write_text(f"v{i}\n", encoding="utf-8")
        s, _ = S.snap(repo, message=f"s{i}")
        ids.append(s.id)
    dropped = S.prune(repo, keep=2)
    assert len(dropped) == 3
    left = S.list_snapshots(repo)
    assert len(left) == 2
    assert left[0].message == "s4"
    assert left[1].message == "s3"


def test_doctor(repo: Path):
    S.init_store(repo)
    S.snap(repo, message="x")
    rep = S.doctor(repo)
    assert rep["ok"]
    assert rep["snap_count"] >= 1


def test_never_touches_user_git(repo: Path):
    # Create a real user git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "u@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "u"], cwd=repo, check=True)
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "user"], cwd=repo, check=True, capture_output=True)
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    S.init_store(repo)
    (repo / "a.txt").write_text("agent edit\n", encoding="utf-8")
    (repo / "new_untracked.txt").write_text("u\n", encoding="utf-8")
    s, _ = S.snap(repo, message="agent")
    S.restore(repo, s.id, force=True)

    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()
    assert before == after
    # Index should be unchanged by agentckpt (we never git-add in user repo)
    # Working tree may differ; that's fine. Check we didn't create commits.
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip().splitlines()
    assert len(log) == 1


def test_cli_demo():
    assert main(["demo"]) == 0


def test_cli_ls_json(repo: Path, monkeypatch):
    monkeypatch.chdir(repo)
    assert main(["init"]) == 0
    assert main(["snap", "-m", "cli"]) == 0
    # capture via subprocess for json cleanliness
    proc = subprocess.run(
        [sys.executable, "-m", "agentckpt", "ls", "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout)
    assert isinstance(data, list)
    assert data[0]["message"] == "cli"
