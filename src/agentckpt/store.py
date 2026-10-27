"""Shadow-git store under .agentckpt/ — never touches the user's real .git."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from . import ignored as I

STORE_DIRNAME = ".agentckpt"
GIT_DIRNAME = "git"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
DEFAULT_KEEP = 50
EXCLUDE_ALWAYS = [".agentckpt/", ".agentckpt", ".git/"]
IGNORE_FILENAME = I.IGNORE_FILENAME  # .agentckptignore: gitignore syntax, snapshot-only
# $GIT_DIR/info/attributes outranks the user's .gitattributes and core.autocrlf.
# Snapshots must hold the exact bytes on disk: no CRLF/LF conversion (Windows
# autocrlf, `eol=crlf`), no clean filters (git-lfs would store pointers), no $Id$.
SHADOW_ATTRIBUTES = "* -text -filter -ident -working-tree-encoding\n"
HOOK_LOCK_NAME = "hook.lock"  # transient; held by `agentckpt hook` while it snaps
HOOK_LOCK_STALE_S = 120.0


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


# Variables that would point git at a *different* repo or index than the shadow store.
# Hooks often run inside agent or git environments that export these; inheriting
# GIT_INDEX_FILE in particular would make the shadow `git add -A` write the user's index.
_GIT_ENV_SCRUB = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_PREFIX",
)


def _git_env(extra: Optional[dict] = None) -> dict:
    env = os.environ.copy()
    for k in _GIT_ENV_SCRUB:
        env.pop(k, None)
    env.setdefault("GIT_AUTHOR_NAME", "agentckpt")
    env.setdefault("GIT_AUTHOR_EMAIL", "agentckpt@local")
    env.setdefault("GIT_COMMITTER_NAME", "agentckpt")
    env.setdefault("GIT_COMMITTER_EMAIL", "agentckpt@local")
    if extra:
        env.update(extra)
    return env


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
    env = _git_env(env_extra)
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
    text = "\n".join(EXCLUDE_ALWAYS) + "\n"
    patterns = read_ignore_patterns(root)
    if patterns:
        # info/exclude is anchored at the work tree root and ranks below .gitignore,
        # so .agentckptignore can only add exclusions, never un-ignore a gitignored path.
        text += f"# from {IGNORE_FILENAME}\n" + "\n".join(patterns) + "\n"
        # Last match wins: repeat the hard excludes so `!.agentckpt/` can't re-include them.
        text += "# always\n" + "\n".join(EXCLUDE_ALWAYS) + "\n"
    (info / "exclude").write_text(text, encoding="utf-8")
    (info / "attributes").write_text(SHADOW_ATTRIBUTES, encoding="utf-8")


def read_ignore_patterns(root: Path) -> List[str]:
    """Non-empty, non-comment lines of .agentckptignore (gitignore syntax)."""
    f = root / IGNORE_FILENAME
    try:
        raw = f.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return []
    out = []
    for ln in raw.splitlines():
        ln = ln.rstrip("\r")
        if ln.strip() and not ln.lstrip().startswith("#"):
            out.append(ln)
    return out


def _norm_path_arg(path: str) -> str:
    """`./sub/`, `/sub` -> `sub`. Unlike str.lstrip("./"), keeps `.github` intact."""
    p = path.replace("\\", "/") if os.sep == "\\" else path
    while p.startswith("./") or p.startswith("/"):
        p = p[1:] if p.startswith("/") else p[2:]
    return p.rstrip("/")


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
            env=_git_env(),
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


def _oversize_candidates(root: Path, max_bytes: int) -> List[str]:
    """Untracked or modified (non-ignored) paths larger than max_bytes, found before staging."""
    out = _run(root, ["ls-files", "-z", "-o", "-m", "--exclude-standard"], check=True)
    found: List[str] = []
    for part in sorted(set((out.stdout or "").split("\0"))):
        if not part:
            continue
        fp = root / part
        try:
            if fp.is_file() and not fp.is_symlink() and fp.stat().st_size > max_bytes:
                found.append(part)
        except OSError:
            continue
    if found:
        # Drop any older (smaller) copy from the index so the snapshot doesn't keep a stale version.
        _run(root, ["rm", "--cached", "-q", "--ignore-unmatch", "--", *found], check=False)
    return found


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
    report: Optional[dict] = None,
) -> Tuple[Snapshot, List[str]]:
    """Take a snapshot. Returns (snapshot, skipped_large_paths).

    If ``report`` is a dict it is filled with ``captured_ignored``, ``refused_secrets``
    and ``ignored_manifest`` (file count, or None when disabled) — see #4.
    """
    if not is_initialized(root):
        raise AgentckptError("Not initialized. Run `agentckpt init` first.")
    _write_info_exclude(root)
    ensure_gitignore(root)
    cfg = I.load_config(root)
    prev_tip = current_tip(root)

    # Opt-in capture of named gitignored paths (never secrets unless allow_secrets).
    capture, refused = I.resolve_includes(root, cfg, I.list_ignored_files_for_capture(root, _run, cfg))
    big_captures = [p for p in capture if (root / p).stat().st_size > max_bytes]
    capture = [p for p in capture if p not in big_captures]
    # Stop tracking ignored files that are no longer configured for capture.
    tracked_ign = _run(root, ["ls-files", "-z", "-c", "-i", "--exclude-standard"], check=True)
    stale = [p for p in (tracked_ign.stdout or "").split("\0") if p and p not in set(capture)]
    if stale:
        _run(root, ["rm", "--cached", "-q", "--ignore-unmatch", "--", *stale], check=False)

    oversize = _oversize_candidates(root, max_bytes)
    add_args = ["add", "-A"]
    if oversize:
        # Exclude oversize paths up front so `git add` never writes their blobs (#2).
        add_args += ["--", "."] + [f":(exclude,literal){p}" for p in oversize]
    _run(root, add_args, check=True)
    if capture:
        _run(root, ["add", "-f", "--", *capture], check=True)
    skipped = sorted(set(oversize) | set(big_captures) | set(_unstaged_large(root, max_bytes)))

    manifest = None
    if cfg.ignored_manifest:
        prev = I.read_manifest(store_path(root), prev_tip.full_id) if prev_tip else None
        manifest = I.scan(root, _run, cfg, previous=prev, max_hash_bytes=max_bytes)
    if report is not None:
        report["captured_ignored"] = capture
        report["refused_secrets"] = refused
        report["ignored_manifest"] = len(manifest["files"]) if manifest else None
        report["ignored_manifest_truncated"] = bool(manifest and manifest["truncated"])

    cached = _run(root, ["diff", "--cached", "--name-only"], check=True)
    if not (cached.stdout or "").strip():
        tip = current_tip(root)
        if tip:
            if manifest and I.read_manifest(store_path(root), tip.full_id) is None:
                I.write_manifest(store_path(root), tip.full_id, manifest)
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
    if manifest:
        I.write_manifest(store_path(root), snap_obj.full_id, manifest)
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
        path = _norm_path_arg(path)
        files = [f for f in files if f == path or f.startswith(path + "/")]
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
        env=_git_env(),
    )
    return out.stdout


def _tree_entries(root: Path, full_id: str, path: Optional[str] = None) -> List[Tuple[str, str, str]]:
    """(mode, sha, relpath) for every blob/link in a snapshot tree."""
    out = _run(root, ["ls-tree", "-r", "-z", full_id], check=True)
    entries: List[Tuple[str, str, str]] = []
    for rec in (out.stdout or "").split("\0"):
        if not rec or "\t" not in rec:
            continue
        meta, rel = rec.split("\t", 1)
        mode, typ, sha = meta.split()
        if typ != "blob":
            continue  # submodule commits etc.
        entries.append((mode, sha, rel))
    if path:
        p = _norm_path_arg(path)
        entries = [e for e in entries if e[2] == p or e[2].startswith(p + "/")]
    return entries


def _read_blobs(root: Path, shas: Sequence[str]) -> dict:
    """Read many blobs with one `git cat-file --batch` call."""
    uniq = list(dict.fromkeys(shas))
    if not uniq:
        return {}
    proc = subprocess.run(
        [_require_git(), f"--git-dir={git_dir(root)}", "cat-file", "--batch"],
        input=("\n".join(uniq) + "\n").encode(),
        capture_output=True,
        check=True,
        cwd=str(root),
        env=_git_env(),
    )
    data, pos, blobs = proc.stdout, 0, {}
    for sha in uniq:
        nl = data.index(b"\n", pos)
        header = data[pos:nl].decode().split()
        if len(header) < 3 or header[1] == "missing":
            raise AgentckptError(f"Snapshot object {sha} is missing from the store.")
        size = int(header[2])
        blobs[sha] = data[nl + 1 : nl + 1 + size]
        pos = nl + 1 + size + 1
    return blobs


def _path_blocker(root: Path, rel: str) -> Optional[str]:
    """Reason a path can't be written safely, or None. Never follows the final component."""
    parts = rel.split("/")
    cur = root
    for part in parts[:-1]:
        cur = cur / part
        if os.path.islink(cur):
            return f"parent {cur.relative_to(root).as_posix()} is a symlink"
        if os.path.lexists(cur) and not cur.is_dir():
            return f"parent {cur.relative_to(root).as_posix()} is not a directory"
    dest = root / rel
    if dest.is_dir() and not os.path.islink(dest):
        return "a directory is in the way"
    return None


def restore(
    root: Path,
    sid: str,
    *,
    path: Optional[str] = None,
    force: bool = False,
) -> dict:
    """
    Restore files and symlinks from a snapshot into the working tree.
    Never touches the user's real .git index/branches, and never follows symlinks
    in the working tree (#6). Symlinks are restored as symlinks.

    Two phases: plan and validate everything, stage temp files next to each
    destination, then rename them all into place. An error while planning or
    staging leaves the working tree unchanged.

    Conflict = working path exists and differs from the snapshot (content, link
    target, or file vs link). Without --force, conflicts are skipped (reported).
    A real directory in the way is always skipped; it is never deleted.
    """
    snap_obj = resolve_id(root, sid)
    entries = _tree_entries(root, snap_obj.full_id, path)
    files = [e[2] for e in entries]
    if path and not files:
        raise AgentckptError(f"Path {path!r} not found in snapshot {snap_obj.id}.")

    restored: List[str] = []
    skipped_conflict: List[str] = []
    skipped_protected: List[str] = []
    skipped_unsupported: List[str] = []

    blobs = _read_blobs(root, [e[1] for e in entries])
    root_resolved = root.resolve()

    # ---- phase 1: plan (no writes)
    plan: List[Tuple[str, str, bytes]] = []  # (kind, rel, payload)
    for mode, sha, rel in entries:
        first = rel.split("/", 1)[0]
        if first in (".git", STORE_DIRNAME) or ".." in rel.split("/"):
            skipped_protected.append(rel)
            continue
        try:
            (root / rel).parent.resolve().relative_to(root_resolved)
        except ValueError:
            skipped_protected.append(rel)
            continue
        if _path_blocker(root, rel):
            skipped_conflict.append(rel)
            continue
        dest = root / rel
        data = blobs[sha]
        is_link = mode == "120000"
        if os.path.islink(dest):
            same = is_link and os.readlink(dest) == os.fsdecode(data)
        elif dest.is_file():
            same = (not is_link) and dest.read_bytes() == data
        else:
            same = False
        if same:
            restored.append(rel)
            if not is_link and mode == "100755":
                plan.append(("chmodx", rel, b""))
            continue
        if os.path.lexists(dest) and not force:
            skipped_conflict.append(rel)
            continue
        plan.append(("link" if is_link else ("exec" if mode == "100755" else "file"), rel, data))

    # ---- phase 2a: stage temp files (undo everything on failure)
    staged: List[Tuple[Path, Path, str]] = []
    made_dirs: List[Path] = []
    try:
        for kind, rel, data in plan:
            dest = root / rel
            if kind == "chmodx":
                continue
            parent = dest.parent
            missing = []
            q = parent
            while not q.exists():
                missing.append(q)
                q = q.parent
            for d in reversed(missing):
                d.mkdir()
                made_dirs.append(d)
            tmp = parent / f".{dest.name}.agentckpt-tmp-{os.getpid()}"
            if os.path.lexists(tmp):
                tmp.unlink()
            if kind == "link":
                try:
                    os.symlink(os.fsdecode(data), tmp)
                except (OSError, NotImplementedError):
                    skipped_unsupported.append(rel)
                    continue
            else:
                with open(tmp, "wb") as f:
                    f.write(data)
                base = dest.stat().st_mode & 0o7777 if dest.is_file() and not dest.is_symlink() else None
                if base is not None:
                    os.chmod(tmp, base)
                if kind == "exec":
                    os.chmod(tmp, os.stat(tmp).st_mode | 0o111)
            staged.append((tmp, dest, rel))
    except Exception as e:
        for tmp, _, _ in staged:
            try:
                tmp.unlink()
            except OSError:
                pass
        for d in reversed(made_dirs):
            try:
                d.rmdir()
            except OSError:
                pass
        raise AgentckptError(f"Restore aborted before changing any file: {e}") from e

    # ---- phase 2b: rename into place (os.replace never follows a symlink at dest)
    for kind, rel, _ in plan:
        if kind == "chmodx":
            dest = root / rel
            os.chmod(dest, dest.stat().st_mode | 0o111)
    for tmp, dest, rel in staged:
        os.replace(tmp, dest)
        restored.append(rel)
    restored.sort()

    ignored_changes = None
    cfg = I.load_config(root)
    old = I.read_manifest(store_path(root), snap_obj.full_id)
    if old is not None and cfg.ignored_manifest:
        now = I.scan(root, _run, cfg, previous=old)
        # Whole tree, even with --path: the state a run leaned on (.env etc.) is global.
        ignored_changes = I.compare(old, now, exclude=set(files))

    return {
        "snapshot": snap_obj.id,
        "ignored_changes": ignored_changes,
        "restored": restored,
        "skipped_conflict": skipped_conflict,
        "skipped_protected": skipped_protected,
        "skipped_unsupported": skipped_unsupported,
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

    id_map = {}
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
        id_map[s.full_id] = _run(root, ["rev-parse", "HEAD"], check=True).stdout.strip()

    tip = _run(root, ["rev-parse", "HEAD"], check=True).stdout.strip()
    # Carry ignored-file manifests over to the rewritten commit ids; drop the rest.
    mdir = I.manifest_dir(store_path(root))
    if mdir.is_dir():
        for old_id, new_id in id_map.items():
            m = I.read_manifest(store_path(root), old_id)
            if m is not None:
                I.write_manifest(store_path(root), new_id, m)
        keep_names = {f"{v}.json" for v in id_map.values()}
        for f in mdir.iterdir():
            if f.name not in keep_names:
                f.unlink()
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
        "ignore_file": None,
        "ignore_patterns": 0,
        "issues": [],
    }
    if (root / IGNORE_FILENAME).is_file():
        report["ignore_file"] = str(root / IGNORE_FILENAME)
        report["ignore_patterns"] = len(read_ignore_patterns(root))
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
    lock = store_path(root) / HOOK_LOCK_NAME
    try:
        if lock.exists() and time.time() - lock.stat().st_mtime > HOOK_LOCK_STALE_S:
            report["issues"].append(
                f"stale hook lock {lock} (a crashed `agentckpt hook`?); safe to delete"
            )
    except OSError:
        pass
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
