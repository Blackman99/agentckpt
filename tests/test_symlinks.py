"""Restore of symlinks and all-or-nothing staging (#6)."""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from agentckpt import store as S


def _can_symlink(tmp: Path) -> bool:
    try:
        os.symlink("x", tmp / "probe")
        os.unlink(tmp / "probe")
        return True
    except (OSError, NotImplementedError):
        return False


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    if not _can_symlink(tmp_path):
        pytest.skip("symlinks not available (e.g. Windows without developer mode)")
    root = tmp_path / "proj"
    (root / "certs" / "real").mkdir(parents=True)
    (root / "certs" / "real" / "ca.crt").write_text("CA\n")
    (root / "target.txt").write_text("target\n")
    (root / "a.txt").write_text("a\n")
    os.symlink("real", root / "certs" / "dirlink")  # -> directory
    os.symlink("target.txt", root / "filelink")  # -> file
    S.init_store(root)
    snap, _ = S.snap(root, "base")
    if "filelink" not in S._files_in_tree(root, snap.full_id) or S._tree_entries(root, snap.full_id, "filelink")[0][0] != "120000":
        pytest.skip("git stores symlinks as plain files here (core.symlinks=false)")
    return root


def _snap_id(root: Path) -> str:
    return S.list_snapshots(root)[0].id


def test_restore_untouched_tree_with_dir_symlink_does_not_crash(proj: Path):
    res = S.restore(proj, _snap_id(proj))
    assert "certs/dirlink" in res["restored"] and "certs/dirlink" not in res["skipped_conflict"]
    assert os.readlink(proj / "certs" / "dirlink") == "real"
    assert (proj / "certs" / "real" / "ca.crt").read_text() == "CA\n"


def test_deleted_symlinks_come_back_as_symlinks(proj: Path):
    os.unlink(proj / "certs" / "dirlink")
    os.unlink(proj / "filelink")
    S.restore(proj, _snap_id(proj))
    assert os.path.islink(proj / "certs" / "dirlink") and os.readlink(proj / "certs" / "dirlink") == "real"
    assert os.path.islink(proj / "filelink") and os.readlink(proj / "filelink") == "target.txt"
    # targets were never overwritten with the link text
    assert (proj / "target.txt").read_text() == "target\n"


def test_retargeted_link_is_conflict_then_force_fixes(proj: Path):
    os.unlink(proj / "filelink")
    os.symlink("a.txt", proj / "filelink")
    res = S.restore(proj, _snap_id(proj))
    assert "filelink" in res["skipped_conflict"]
    S.restore(proj, _snap_id(proj), force=True)
    assert os.readlink(proj / "filelink") == "target.txt"
    assert (proj / "a.txt").read_text() == "a\n"


def test_file_replaced_by_symlink_is_not_written_through(proj: Path):
    outside = proj.parent / "outside.txt"
    outside.write_text("keep me\n")
    (proj / "a.txt").unlink()
    os.symlink(str(outside), proj / "a.txt")
    S.restore(proj, _snap_id(proj), force=True)
    assert outside.read_text() == "keep me\n"
    assert not os.path.islink(proj / "a.txt") and (proj / "a.txt").read_text() == "a\n"


def test_symlinked_parent_dir_is_never_followed(proj: Path, tmp_path: Path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (proj / "certs" / "real" / "ca.crt").unlink()
    (proj / "certs" / "real").rmdir()
    os.symlink(str(outside), proj / "certs" / "real")
    res = S.restore(proj, _snap_id(proj), force=True)
    assert "certs/real/ca.crt" in res["skipped_conflict"] + res["skipped_protected"]
    assert "certs/real/ca.crt" not in res["restored"]
    assert list(outside.iterdir()) == []


def test_directory_in_the_way_is_never_deleted(proj: Path):
    (proj / "a.txt").unlink()
    (proj / "a.txt").mkdir()
    (proj / "a.txt" / "keep").write_text("k")
    res = S.restore(proj, _snap_id(proj), force=True)
    assert "a.txt" in res["skipped_conflict"]
    assert (proj / "a.txt" / "keep").read_text() == "k"


def test_failure_while_staging_leaves_tree_unchanged(proj: Path, monkeypatch):
    (proj / "a.txt").write_text("edited\n")
    (proj / "target.txt").write_text("edited too\n")
    real_open = builtins.open

    def flaky(file, mode="r", *a, **k):
        if "agentckpt-tmp" in str(file) and "target.txt" in str(file):
            raise OSError("disk full")
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", flaky)
    with pytest.raises(S.AgentckptError, match="before changing any file"):
        S.restore(proj, _snap_id(proj), force=True)
    monkeypatch.setattr(builtins, "open", real_open)
    assert (proj / "a.txt").read_text() == "edited\n"
    assert (proj / "target.txt").read_text() == "edited too\n"
    assert not [p for p in proj.rglob("*agentckpt-tmp*")]
