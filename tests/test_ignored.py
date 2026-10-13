"""Gitignored state: manifest warnings, opt-in capture, secret refusal (#4)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from agentckpt import ignored as I
from agentckpt import store as S
from agentckpt.cli import main


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
    (root / ".gitignore").write_text(".env\nbuild/\n*.log\nnode_modules/\nconf.local.json\n")
    (root / ".env").write_text("TOKEN=one\n")
    (root / "build").mkdir()
    (root / "build" / "config.json").write_text('{"v": 1}\n')
    (root / "conf.local.json").write_text('{"db": "a"}\n')
    S.init_store(root)
    return root


def _bump(p: Path, text: str) -> None:
    p.write_text(text)
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


def test_ignored_files_not_captured_by_default(proj: Path):
    snap, _ = S.snap(proj, "base")
    files = S._files_in_tree(proj, snap.full_id)
    assert "app.py" in files
    assert ".env" not in files and "build/config.json" not in files


def test_manifest_stores_metadata_not_contents(proj: Path):
    snap, _ = S.snap(proj, "base")
    m = I.read_manifest(S.store_path(proj), snap.full_id)
    assert set(m["files"]) >= {".env", "build/config.json", "conf.local.json"}
    entry = m["files"][".env"]
    assert set(entry) == {"size", "mtime_ns", "sha256"}
    raw = (I.manifest_dir(S.store_path(proj)) / f"{snap.full_id}.json").read_text()
    assert "TOKEN=one" not in raw


def test_restore_warns_about_ignored_drift(proj: Path, capsys):
    snap, _ = S.snap(proj, "base")
    _bump(proj / ".env", "TOKEN=two\n")
    (proj / "build" / "config.json").unlink()
    (proj / "debug.log").write_text("new\n")
    (proj / "app.py").write_text("broken\n")
    res = S.restore(proj, snap.id, force=True)
    ch = res["ignored_changes"]
    assert ch["changed"] == [".env"]
    assert ch["removed"] == ["build/config.json"]
    assert ch["added"] == ["debug.log"]
    # restore never touches ignored files
    assert (proj / ".env").read_text() == "TOKEN=two\n"
    assert (proj / "app.py").read_text() == "print('hi')\n"


def test_restore_cli_prints_warning(proj: Path, capsys, monkeypatch):
    monkeypatch.chdir(proj)
    snap, _ = S.snap(proj, "base")
    _bump(proj / "conf.local.json", '{"db": "b"}\n')
    assert main(["restore", snap.id, "--force"]) == 0
    err = capsys.readouterr().err
    assert "gitignored file(s) differ" in err and "conf.local.json" in err


def test_unchanged_ignored_files_no_warning(proj: Path):
    snap, _ = S.snap(proj, "base")
    res = S.restore(proj, snap.id)
    ch = res["ignored_changes"]
    assert ch["added"] == ch["removed"] == ch["changed"] == []


def test_include_ignored_captures_and_restores(proj: Path):
    (proj / "agentckpt.toml").write_text('include_ignored = ["build/", "conf.local.json"]\n')
    rep: dict = {}
    snap, _ = S.snap(proj, "with config", report=rep)
    assert rep["captured_ignored"] == ["build/config.json", "conf.local.json"]
    files = S._files_in_tree(proj, snap.full_id)
    assert "build/config.json" in files and "conf.local.json" in files
    (proj / "build" / "config.json").write_text('{"v": 999}\n')
    (proj / "conf.local.json").unlink()
    res = S.restore(proj, snap.id, force=True)
    assert (proj / "build" / "config.json").read_text() == '{"v": 1}\n'
    assert (proj / "conf.local.json").read_text() == '{"db": "a"}\n'
    # captured files are restored, so they are not reported as drift
    assert "conf.local.json" not in res["ignored_changes"]["removed"]


def test_pyproject_tool_table(proj: Path):
    (proj / "pyproject.toml").write_text(
        '[project]\nname = "x"\n\n[tool.agentckpt]\ninclude_ignored = [\n  "conf.local.json",  # local db\n]\n'
    )
    cfg = I.load_config(proj)
    assert cfg.include_ignored == ["conf.local.json"]
    assert I._mini_toml(
        '[tool.agentckpt]\ninclude_ignored = [\n  "a",\n  "b#c",  # x\n]\nallow_secrets = true\n'
    ) == {"tool": {"agentckpt": {"include_ignored": ["a", "b#c"], "allow_secrets": True}}}


def test_secrets_refused_without_allow_secrets(proj: Path):
    (proj / "id_ed25519").write_text("KEY\n")
    (proj / ".gitignore").write_text((proj / ".gitignore").read_text() + "id_ed25519\n")
    (proj / "agentckpt.toml").write_text('include_ignored = [".env", "id_ed25519"]\n')
    rep: dict = {}
    snap, _ = S.snap(proj, "s", report=rep)
    assert rep["captured_ignored"] == []
    assert rep["refused_secrets"] == [".env", "id_ed25519"]
    assert ".env" not in S._files_in_tree(proj, snap.full_id)


def test_allow_secrets_opt_in(proj: Path):
    (proj / "agentckpt.toml").write_text('include_ignored = [".env"]\nallow_secrets = true\n')
    snap, _ = S.snap(proj, "s")
    assert ".env" in S._files_in_tree(proj, snap.full_id)


@pytest.mark.parametrize(
    "path",
    [".env", ".env.local", "prod.env", "certs/server.pem", "tls.key", "id_rsa", "x/id_ed25519.pub",
     ".npmrc", "credentials.json", "my_secret.txt"],
)
def test_secret_patterns(path):
    assert I.is_secret_path(path)


@pytest.mark.parametrize("path", ["build/config.json", "tokenizer.json", "dist/app.js", "keys.md"])
def test_non_secret_patterns(path):
    assert not I.is_secret_path(path)


def test_removing_include_untracks_file(proj: Path):
    (proj / "agentckpt.toml").write_text('include_ignored = ["conf.local.json"]\n')
    S.snap(proj, "with")
    (proj / "agentckpt.toml").write_text("include_ignored = []\n")
    snap2, _ = S.snap(proj, "without")
    assert "conf.local.json" not in S._files_in_tree(proj, snap2.full_id)


def test_include_respects_max_bytes(proj: Path):
    (proj / "build" / "big.bin").write_bytes(b"x" * 4096)
    (proj / "agentckpt.toml").write_text('include_ignored = ["build/"]\n')
    rep: dict = {}
    snap, skipped = S.snap(proj, "s", max_bytes=1024, report=rep)
    assert "build/big.bin" in skipped
    assert "build/big.bin" not in S._files_in_tree(proj, snap.full_id)
    assert "build/config.json" in S._files_in_tree(proj, snap.full_id)


def test_manifest_skips_heavy_dirs_and_caps(proj: Path):
    nm = proj / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    for i in range(50):
        (nm / f"f{i}.js").write_text("x")
    snap, _ = S.snap(proj, "s")
    m = I.read_manifest(S.store_path(proj), snap.full_id)
    assert not any(p.startswith("node_modules/") for p in m["files"])
    assert not any(p.startswith(".agentckpt") or p.startswith(".git/") for p in m["files"])
    (proj / "agentckpt.toml").write_text("manifest_max_files = 2\n")
    (proj / "x.log").write_text("1")
    snap2, _ = S.snap(proj, "s2")
    m2 = I.read_manifest(S.store_path(proj), snap2.full_id)
    assert len(m2["files"]) == 2 and m2["truncated"] is True


def test_manifest_can_be_disabled(proj: Path):
    (proj / "agentckpt.toml").write_text("ignored_manifest = false\n")
    snap, _ = S.snap(proj, "s")
    assert I.read_manifest(S.store_path(proj), snap.full_id) is None
    assert S.restore(proj, snap.id)["ignored_changes"] is None


def test_lazy_hash_reuses_previous(proj: Path, monkeypatch):
    S.snap(proj, "s1")
    calls = []
    real = I._sha256
    monkeypatch.setattr(I, "_sha256", lambda p: calls.append(p) or real(p))
    (proj / "app.py").write_text("v2\n")
    S.snap(proj, "s2")
    assert calls == []  # nothing ignored changed -> nothing re-hashed


def test_prune_keeps_manifests(proj: Path):
    for i in range(4):
        (proj / "app.py").write_text(f"v{i}\n")
        time.sleep(0.01)
        S.snap(proj, f"s{i}")
    S.prune(proj, keep=2)
    snaps = S.list_snapshots(proj)
    for s in snaps:
        assert I.read_manifest(S.store_path(proj), s.full_id) is not None
    assert len(list(I.manifest_dir(S.store_path(proj)).glob("*.json"))) == 2


def test_mini_toml_multiline_array_with_bracket_glob():
    data = I._mini_toml(
        '[tool.agentckpt]\ninclude_ignored = [\n  "gen/[ab]*.json",  # c\n  "build/",\n]\n'
        "allow_secrets = false\n"
    )
    assert data["tool"]["agentckpt"]["include_ignored"] == ["gen/[ab]*.json", "build/"]
    assert data["tool"]["agentckpt"]["allow_secrets"] is False


def test_secret_files_are_not_hashed_in_manifest(proj: Path):
    (proj / ".env").write_text("TOKEN=abc\n", encoding="utf-8")
    (proj / "conf.local.json").write_text("{}\n", encoding="utf-8")
    snap, _ = S.snap(proj, message="m")
    m = I.read_manifest(S.store_path(proj), snap.full_id)
    assert m["files"][".env"]["sha256"] is None
    assert m["files"]["conf.local.json"]["sha256"]
