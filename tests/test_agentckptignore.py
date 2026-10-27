"""`.agentckptignore`: snapshot-only exclusions in gitignore syntax."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agentckpt import store as S
from agentckpt.cli import main


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "dist").mkdir()
    (root / "dist" / "bundle.js").write_text("x" * 100)
    (root / "logs").mkdir()
    (root / "logs" / "run.log").write_text("log\n")
    (root / "logs" / "keep.log").write_text("keep\n")
    (root / ".gitignore").write_text(".env\n")
    (root / ".env").write_text("A=1\n")
    S.init_store(root)
    return root


def _files(root: Path, snap) -> list:
    return S._files_in_tree(root, snap.full_id)


def test_ignore_file_excludes_paths_and_supports_negation(proj: Path):
    (proj / ".agentckptignore").write_text("# build output\ndist/\nlogs/*.log\n!logs/keep.log\n")
    snap, _ = S.snap(proj, "base")
    files = _files(proj, snap)
    assert "app.py" in files and ".agentckptignore" in files
    assert "dist/bundle.js" not in files
    assert "logs/run.log" not in files
    assert "logs/keep.log" in files


def test_adding_pattern_drops_previously_snapped_path(proj: Path):
    s1, _ = S.snap(proj, "before")
    assert "dist/bundle.js" in _files(proj, s1)
    (proj / ".agentckptignore").write_text("dist/\n")
    s2, _ = S.snap(proj, "after")
    assert "dist/bundle.js" not in _files(proj, s2)
    # The old snapshot still has it and can bring it back.
    (proj / "dist" / "bundle.js").unlink()
    res = S.restore(proj, s1.id, path="dist")
    assert res["restored"] == ["dist/bundle.js"]


def test_excluded_paths_stay_out_of_ignored_manifest_warnings(proj: Path):
    (proj / ".agentckptignore").write_text("dist/\n")
    snap, _ = S.snap(proj, "base")
    (proj / "dist" / "bundle.js").write_text("changed")
    (proj / "dist" / "new.js").write_text("new")
    res = S.restore(proj, snap.id)
    ch = res["ignored_changes"] or {}
    flat = json.dumps(ch)
    assert "dist/" not in flat
    # Real gitignored state is still watched.
    (proj / ".env").write_text("A=2\n")
    res = S.restore(proj, snap.id)
    assert ".env" in json.dumps(res["ignored_changes"])


def test_restore_never_deletes_excluded_files(proj: Path):
    (proj / ".agentckptignore").write_text("dist/\n")
    snap, _ = S.snap(proj, "base")
    (proj / "app.py").write_text("broken\n")
    S.restore(proj, snap.id, force=True)
    assert (proj / "app.py").read_text() == "print('hi')\n"
    assert (proj / "dist" / "bundle.js").exists()


def test_watch_fingerprint_respects_ignore_file(proj: Path):
    (proj / ".agentckptignore").write_text("dist/\n")
    fp = S.fingerprint_tree(proj)
    assert "app.py" in fp and "dist/bundle.js" not in fp


def test_ignore_file_never_touches_user_git(proj: Path):
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    (proj / ".agentckptignore").write_text("dist/\n")
    S.snap(proj, "base")
    out = subprocess.run(["git", "status", "--porcelain"], cwd=proj, capture_output=True, text=True)
    assert "dist/" in out.stdout  # still visible to the user's own git


def test_crlf_and_bom_tolerated(proj: Path):
    (proj / ".agentckptignore").write_bytes(b"\xef\xbb\xbfdist/\r\n\r\n# c\r\n")
    assert S.read_ignore_patterns(proj) == ["dist/"]
    snap, _ = S.snap(proj, "base")
    assert "dist/bundle.js" not in _files(proj, snap)


def test_doctor_reports_ignore_file(proj: Path, capsys, monkeypatch):
    (proj / ".agentckptignore").write_text("dist/\nlogs/\n")
    monkeypatch.chdir(proj)
    main(["doctor"])
    assert ".agentckptignore (2 pattern(s))" in capsys.readouterr().out
    rep = S.doctor(proj)
    assert rep["ignore_patterns"] == 2


def test_negation_cannot_reinclude_store_or_git(proj: Path):
    (proj / ".agentckptignore").write_text("!.agentckpt/\n!.agentckpt\n!.git/\n")
    snap, _ = S.snap(proj, "base")
    assert not any(f.split("/")[0] in (".agentckpt", ".git") for f in _files(proj, snap))
