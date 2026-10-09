"""Shadow-git store under .agentckpt/ — never touches the user's real .git."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

STORE_DIRNAME = ".agentckpt"
GIT_DIRNAME = "git"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
DEFAULT_KEEP = 50
EXCLUDE_ALWAYS = [".agentckpt/", ".agentckpt", ".git/"]


class AgentckptError(Exception):
    """User-facing error with a clear message."""


@dataclass
class Snapshot:
    id: str
    full_id: str
    timestamp: str
    message: str
    file_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def find_root(start: Optional[Path] = None) -> Path:
    """Walk up for an existing .agentckpt, else for .git, else use cwd."""
    cur = (start or Path.cwd()).resolve()
    found_git: Optional[Path] = None
    for p in [cur, *cur.parents]:
        if (p / STORE_DIRNAME).is_dir():
            return p
        if found_git is None and (p / ".git").exists():
            found_git = p
    return found_git or cur


def store_path(root: Path) -> Path:
    return root / STORE_DIRNAME


def git_dir(root: Path) -> Path:
    return store_path(root) / GIT_DIRNAME


def _require_git() -> str:
    path = shutil.which("git")
    if not path:
        raise AgentckptError(
            "git is required on PATH (agentckpt uses a private shadow repo under .agentckpt/)."
        )
    return path


def _run(
    root: Path,
    args: Sequence[str],
    *,
    check: bool = True,
    input_text: Optional[str] = None,
    env_extra: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    git = _require_git()
    cmd = [git, f"--git-dir={git_dir(root)}", f"--work-tree={root}", *args]
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "agentckpt")
    env.setdefault("GIT_AUTHOR_EMAIL", "agentckpt@local")
    env.setdefault("GIT_COMMITTER_NAME", "agentckpt")
    env.setdefault("GIT_COMMITTER_EMAIL", "agentckpt@local")
    if env_extra:
        env.update(env_extra)
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=True,
            text=True,
            input=input_text,
            env=env,
            cwd=str(root),
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip() or str(e)
        raise AgentckptError(f"git {' '.join(args)} failed: {err}") from e
    except FileNotFoundError as e:
        raise AgentckptError("git is required on PATH.") from e


def is_initialized(root: Path) -> bool:
    return (git_dir(root) / "HEAD").exists()


def ensure_gitignore(root: Path) -> bool:
    """Ensure .agentckpt/ is listed in root .gitignore. Returns True if changed."""
    gi = root / ".gitignore"
    line = ".agentckpt/"
    if gi.exists():
        text = gi.read_text(encoding="utf-8")
        for existing in text.splitlines():
            if existing.strip() in (".agentckpt/", ".agentckpt", "**/.agentckpt/"):
                return False
        if text and not text.endswith("\n"):
            text += "\n"
        gi.write_text(text + f"\n# agentckpt shadow store\n{line}\n", encoding="utf-8")
    else:
        gi.write_text(f"# agentckpt shadow store\n{line}\n", encoding="utf-8")
    return True


def _write_info_exclude(root: Path) -> None:
    info = git_dir(root) / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "exclude").write_text("\n".join(EXCLUDE_ALWAYS) + "\n", encoding="utf-8")


def init_store(root: Path) -> Tuple[Path, bool]:
    """Create the shadow store. Returns (root, created_new)."""
    _require_git()
    sp = store_path(root)
    gd = git_dir(root)
    created = not is_initialized(root)
    if created:
        sp.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [_require_git(), "init", "--bare", str(gd)],
            check=True,
            capture_output=True,
            text=True,
        )
        _run(root, ["config", "user.name", "agentckpt"])
        _run(root, ["config", "user.email", "agentckpt@local"])
        _run(root, ["config", "core.bare", "false"])
        _run(root, ["commit", "--allow-empty", "-m", "agentckpt: init"])
    ensure_gitignore(root)
    _write_info_exclude(root)
    (sp / "README").write_text(
        "Private agentckpt shadow git store. Do not commit this directory.\n"
        "Managed by https://github.com/Blackman99/agentckpt\n",
        encoding="utf-8",
    )
    return root, created


def _file_count_for(root: Path, full_id: str) -> int:
    out = _run(root, ["ls-tree", "-r", "--name-only", full_id], check=True)
    return len([ln for ln in (out.stdout or "").splitlines() if ln.strip()])


def _parse_snapshot_line(line: str) -> Optional[Snapshot]:
    line = (line or "").strip()
    if not line:
        return None
    parts = line.split("\0")
    if len(parts) < 4:
        return None
    full, short, ts, msg = parts[0], parts[1], parts[2], parts[3]
    return Snapshot(id=short, full_id=full, timestamp=ts, message=msg, file_count=0)


def current_tip(root: Path) -> Optional[Snapshot]:
    if not is_initialized(root):
        return None
    out = _run(root, ["log", "-1", "--format=%H%x00%h%x00%cI%x00%s"], check=True)
    s = _parse_snapshot_line(out.stdout)
    if s:
        s.file_count = _file_count_for(root, s.full_id)
    return s


def _unstaged_large(root: Path, max_bytes: int) -> List[str]:
    """After git add -A, remove files larger than max_bytes from the index."""
    skipped: List[str] = []
    out = _run(root, ["diff", "--cached", "--name-only", "-z"], check=True)
    for part in (out.stdout or "").split("\0"):
        if not part:
            continue
        fp = root / part
        try:
            if fp.is_file() and fp.stat().st_size > max_bytes:
                _run(root, ["rm", "--cached", "-q", "--ignore-unmatch", "--", part], check=False)
                skipped.append(part)
        except OSError:
            continue
    return skipped


def snap(
    root: Path,
    message: str = "",
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Tuple[Snapshot, List[str]]:
    """Take a snapshot. Returns (snapshot, skipped_large_paths)."""
    if not is_initialized(root):
        raise AgentckptError("Not initialized. Run `agentckpt init` first.")
    _write_info_exclude(root)
    ensure_gitignore(root)

    _run(root, ["add", "-A"], check=True)
    skipped = _unstaged_large(root, max_bytes)

    cached = _run(root, ["diff", "--cached", "--name-only"], check=True)
    if not (cached.stdout or "").strip():
        tip = current_tip(root)
        if tip:
            return tip, skipped
        raise AgentckptError("Nothing to snapshot (empty store).")

    msg = message.strip() if message else "snap"
    names = [n for n in (cached.stdout or "").splitlines() if n.strip()]
    _run(
        root,
        ["commit", "-m", msg, "-m", f"agentckpt-files: {len(names)}", "--quiet"],
        check=True,
    )
    snap_obj = current_tip(root)
    assert snap_obj is not None
    return snap_obj, skipped


def list_snapshots(root: Path, *, skip_init: bool = True) -> List[Snapshot]:
    if not is_initialized(root):
        raise AgentckptError("Not initialized. Run `agentckpt init` first.")
    out = _run(
        root,
        ["log", "--format=%H%x00%h%x00%cI%x00%s"],
        check=True,
    )
    snaps: List[Snapshot] = []
    for line in (out.stdout or "").splitlines():
        s = _parse_snapshot_line(line)
        if not s:
            continue
        if skip_init and s.message == "agentckpt: init":
            continue
        s.file_count = _file_count_for(root, s.full_id)
        snaps.append(s)
    return snaps  # newest first (git log default)


def resolve_id(root: Path, sid: str) -> Snapshot:
    snaps = list_snapshots(root, skip_init=False)
    sid = sid.strip()
    matches = [
        s
        for s in snaps
        if s.id == sid or s.full_id.startswith(sid) or s.id.startswith(sid)
    ]
    if not matches:
        raise AgentckptError(f"Unknown snapshot id: {sid!r}. Run `agentckpt ls`.")
    s = matches[0]
    if s.message == "agentckpt: init":
        raise AgentckptError(
            f"Snapshot {sid!r} is the empty init marker; pick a real snap."
        )
    s.file_count = _file_count_for(root, s.full_id)
    return s


def diff_snapshot(
    root: Path,
    sid: str,
    path: Optional[str] = None,
    *,
    to_id: Optional[str] = None,
) -> str:
    a = resolve_id(root, sid)
    args: List[str] = ["diff", "--no-ext-diff"]
    if to_id:
        b = resolve_id(root, to_id)
        args += [a.full_id, b.full_id]
    else:
        args += [a.full_id]
    if path:
        args += ["--", path]
    out = _run(root, args, check=False)
    return out.stdout or ""


def _files_in_tree(root: Path, full_id: str, path: Optional[str] = None) -> List[str]:
    args = ["ls-tree", "-r", "--name-only", full_id]
    out = _run(root, args, check=True)
    files = [ln for ln in (out.stdout or "").splitlines() if ln.strip()]
    if path:
        path = path.lstrip("./")
        files = [f for f in files if f == path or f.startswith(path.rstrip("/") + "/")]
    return files


def _blob_bytes(root: Path, full_id: str, rel: str) -> bytes:
    out = subprocess.run(
        [
            _require_git(),
            f"--git-dir={git_dir(root)}",
            f"--work-tree={root}",
            "show",
            f"{full_id}:{rel}",
        ],
        check=True,
        capture_output=True,
        cwd=str(root),
    )
    return out.stdout


def restore(
    root: Path,
    sid: str,
    *,
    path: Optional[str] = None,
    force: bool = False,
) -> dict:
    """
    Restore files from a snapshot into the working tree.
    Never touches the user's real .git index/branches.
    Conflict = working file exists and content differs from snapshot.
    Without --force, conflicting files are skipped (reported).
    """
    snap_obj = resolve_id(root, sid)
    files = _files_in_tree(root, snap_obj.full_id, path)
    if path and not files:
        raise AgentckptError(f"Path {path!r} not found in snapshot {snap_obj.id}.")

    restored: List[str] = []
    skipped_conflict: List[str] = []
    skipped_protected: List[str] = []

    root_resolved = root.resolve()
    git_resolved = (root / ".git").resolve()
    store_resolved = store_path(root).resolve()

    for rel in files:
        if rel == ".git" or rel.startswith(".git/") or rel.startswith(STORE_DIRNAME):
            skipped_protected.append(rel)
            continue
        dest = (root / rel).resolve()
        try:
            dest.relative_to(root_resolved)
        except ValueError:
            skipped_protected.append(rel)
            continue
        # Block writes into .git or .agentckpt
        for blocked in (git_resolved, store_resolved):
            try:
                dest.relative_to(blocked)
                skipped_protected.append(rel)
                break
            except (ValueError, FileNotFoundError):
                continue
        else:
            data = _blob_bytes(root, snap_obj.full_id, rel)
            if dest.exists() and dest.is_file():
                current = dest.read_bytes()
                if current != data and not force:
                    skipped_conflict.append(rel)
                    continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            restored.append(rel)
            continue
        # broke from protected

    return {
        "snapshot": snap_obj.id,
        "restored": restored,
        "skipped_conflict": skipped_conflict,
        "skipped_protected": skipped_protected,
    }


def prune(root: Path, keep: int = DEFAULT_KEEP) -> List[str]:
    """Keep the newest `keep` snapshots; rewrite history to drop older ones."""
    if keep < 1:
        raise AgentckptError("--keep must be >= 1")
    snaps = list_snapshots(root, skip_init=True)
    if len(snaps) <= keep:
        return []

    dropped_ids = [s.id for s in snaps[keep:]]
    kept = list(reversed(snaps[:keep]))  # oldest → newest among kept

    env_base = {
        "GIT_AUTHOR_NAME": "agentckpt",
        "GIT_AUTHOR_EMAIL": "agentckpt@local",
        "GIT_COMMITTER_NAME": "agentckpt",
        "GIT_COMMITTER_EMAIL": "agentckpt@local",
    }

    _run(root, ["checkout", "--orphan", "agentckpt-prune-tmp"], check=True)
    _run(root, ["reset", "-q"], check=False)
    _run(root, ["commit", "--allow-empty", "-m", "agentckpt: init", "--quiet"], check=True)

    for s in kept:
        _run(root, ["read-tree", s.full_id], check=True)
        env = {
            **env_base,
            "GIT_AUTHOR_DATE": s.timestamp,
            "GIT_COMMITTER_DATE": s.timestamp,
        }
        _run(
            root,
            [
                "commit",
                "-m",
                s.message,
                "-m",
                f"agentckpt-files: {s.file_count}",
                "--quiet",
                "--allow-empty",
            ],
            check=True,
            env_extra=env,
        )

    tip = _run(root, ["rev-parse", "HEAD"], check=True).stdout.strip()
    # Prefer existing default branch name (orphan checkout left HEAD on prune-tmp)
    default = "main"
    for name in ("main", "master"):
        if (git_dir(root) / "refs" / "heads" / name).exists():
            default = name
            break
    _run(root, ["branch", "-f", default, tip], check=True)
    _run(root, ["symbolic-ref", "HEAD", f"refs/heads/{default}"], check=True)
    _run(root, ["branch", "-D", "agentckpt-prune-tmp"], check=False)
    _run(root, ["reflog", "expire", "--expire=now", "--all"], check=False)
    _run(root, ["gc", "--prune=now", "--quiet"], check=False)
    return dropped_ids


def doctor(root: Path) -> dict:
    report: dict = {
        "root": str(root),
        "store": str(store_path(root)),
        "initialized": is_initialized(root),
        "git_on_path": bool(shutil.which("git")),
        "gitignore_ok": False,
        "snap_count": 0,
        "issues": [],
    }
    if not report["git_on_path"]:
        report["issues"].append("git not found on PATH")
    gi = root / ".gitignore"
    if gi.exists():
        text = gi.read_text(encoding="utf-8")
        report["gitignore_ok"] = any(
            ln.strip() in (".agentckpt/", ".agentckpt", "**/.agentckpt/")
            for ln in text.splitlines()
        )
    if not report["gitignore_ok"]:
        report["issues"].append(".agentckpt/ is not listed in .gitignore")
    if report["initialized"]:
        try:
            snaps = list_snapshots(root)
            report["snap_count"] = len(snaps)
            _run(root, ["status"], check=True)
        except AgentckptError as e:
            report["issues"].append(str(e))
    else:
        report["issues"].append("store not initialized (run agentckpt init)")
    report["ok"] = len(report["issues"]) == 0
    return report


def fingerprint_tree(root: Path) -> dict:
    """Return {relpath: (mtime_ns, size)} for watch polling (respects ignore)."""
    if not is_initialized(root):
        raise AgentckptError("Not initialized. Run `agentckpt init` first.")
    _write_info_exclude(root)
    out = _run(
        root,
        ["ls-files", "-c", "-o", "--exclude-standard", "-z"],
        check=True,
    )
    result: dict = {}
    for part in (out.stdout or "").split("\0"):
        if not part:
            continue
        if part.startswith(STORE_DIRNAME) or part.startswith(".git"):
            continue
        fp = root / part
        try:
            st = fp.stat()
            if fp.is_file():
                result[part] = (st.st_mtime_ns, st.st_size)
        except OSError:
            continue
    return result
