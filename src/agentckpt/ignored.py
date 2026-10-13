"""Gitignored working-tree state: config, manifest (metadata only), and opt-in capture (#4).

The manifest stores path, size, mtime and a sha256 for each gitignored file. It never
stores contents. Restore compares it with the current tree and warns about drift.
Files are only *captured* (stored in the snapshot) when listed under
``include_ignored`` in the project config. Secret-looking paths are refused unless
``allow_secrets = true``.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CONFIG_FILENAME = "agentckpt.toml"
MANIFEST_DIRNAME = "manifests"

# Not walked when building the manifest (big, regenerable, rarely "state the run leaned on").
DEFAULT_SKIP_DIRS = [
    "node_modules", ".venv", "venv", "env", "__pycache__", ".tox", ".nox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".gradle", ".next", ".cache",
    "target", "site-packages", ".eggs",
]
DEFAULT_MAX_FILES = 2000

# Basename patterns that look like credentials. Matched case-insensitively.
SECRET_PATTERNS = [
    ".env", ".env.*", "*.env", ".envrc", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks",
    "*.keystore", "*.kdbx", "*.gpg", "*.asc", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*",
    ".netrc", ".npmrc", ".pypirc", ".pgpass", ".htpasswd", "credentials*", "*secret*",
    "service-account*.json",
]


@dataclass
class Config:
    include_ignored: List[str] = field(default_factory=list)
    allow_secrets: bool = False
    ignored_manifest: bool = True
    manifest_skip_dirs: List[str] = field(default_factory=lambda: list(DEFAULT_SKIP_DIRS))
    manifest_max_files: int = DEFAULT_MAX_FILES
    source: Optional[str] = None


# ---------------------------------------------------------------- config

def _parse_toml(text: str) -> dict:
    try:
        import tomllib  # type: ignore[import-not-found]  # 3.11+
        return tomllib.loads(text)
    except ImportError:
        return _mini_toml(text)


_KV = re.compile(r"^([A-Za-z0-9_.\-]+)\s*=\s*(.*)$")


def _mini_toml(text: str) -> dict:
    """Tiny TOML subset for Python < 3.11: [tables], strings, bools, ints, string arrays."""
    out: dict = {}
    cur = out
    buf = ""
    key = None
    for raw in text.splitlines():
        line = _strip_comment(raw).strip()
        if key is not None:
            buf += " " + line
            if "]" in line:
                cur[key] = _mini_value(buf)
                key = None
            continue
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = out
            for part in line.strip("[]").strip().split("."):
                cur = cur.setdefault(part.strip().strip('"'), {})
            continue
        m = _KV.match(line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v.startswith("[") and "]" not in v:
            key, buf = k, v
            continue
        cur[k] = _mini_value(v)
    return out


_STR = re.compile(r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\'')


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return line[:i]
    return line


def _mini_value(v: str):
    v = v.strip()
    if v.startswith("["):
        return [a or b for a, b in _STR.findall(v)]
    if v in ("true", "false"):
        return v == "true"
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    try:
        return int(v)
    except ValueError:
        return v


def load_config(root: Path) -> Config:
    """Read ``agentckpt.toml`` (top-level keys) or ``[tool.agentckpt]`` in pyproject.toml."""
    data: dict = {}
    source = None
    own = root / CONFIG_FILENAME
    py = root / "pyproject.toml"
    try:
        if own.is_file():
            parsed = _parse_toml(own.read_text(encoding="utf-8"))
            data = parsed.get("tool", {}).get("agentckpt", parsed) if "tool" in parsed else parsed
            source = CONFIG_FILENAME
        elif py.is_file():
            data = _parse_toml(py.read_text(encoding="utf-8")).get("tool", {}).get("agentckpt", {})
            source = "pyproject.toml [tool.agentckpt]" if data else None
    except Exception as e:  # malformed config must never break a snapshot
        from .store import AgentckptError

        raise AgentckptError(f"Could not parse agentckpt config: {e}") from e
    cfg = Config(source=source)
    if isinstance(data.get("include_ignored"), list):
        cfg.include_ignored = [str(x) for x in data["include_ignored"] if str(x).strip()]
    if isinstance(data.get("allow_secrets"), bool):
        cfg.allow_secrets = data["allow_secrets"]
    if isinstance(data.get("ignored_manifest"), bool):
        cfg.ignored_manifest = data["ignored_manifest"]
    if isinstance(data.get("manifest_skip_dirs"), list):
        cfg.manifest_skip_dirs = [str(x) for x in data["manifest_skip_dirs"]]
    if isinstance(data.get("manifest_max_files"), int) and data["manifest_max_files"] >= 0:
        cfg.manifest_max_files = data["manifest_max_files"]
    return cfg


def is_secret_path(rel: str) -> bool:
    for part in rel.replace("\\", "/").split("/"):
        low = part.lower()
        if any(fnmatch.fnmatchcase(low, p) for p in SECRET_PATTERNS):
            return True
    return False


# ---------------------------------------------------------------- listing

def _is_internal(rel: str) -> bool:
    first = rel.replace("\\", "/").split("/", 1)[0]
    return first in (".git", ".agentckpt")


def ignored_entries(root: Path, run) -> List[str]:
    """Ignored paths as git reports them; fully ignored dirs come back as ``dir/`` (not walked)."""
    out = run(root, ["ls-files", "-z", "-o", "-i", "--exclude-standard", "--directory"], check=True)
    return [p for p in (out.stdout or "").split("\0") if p and not _is_internal(p)]


def _walk_files(root: Path, entries: List[str], skip_dirs: List[str], limit: int) -> Tuple[List[str], bool]:
    """Expand entries to files, pruning skip_dirs. Returns (files, truncated)."""
    skip = set(skip_dirs)
    files: List[str] = []
    for ent in entries:
        rel = ent.rstrip("/")
        if any(part in skip for part in rel.split("/")):
            continue
        p = root / rel
        if ent.endswith("/") or p.is_dir():
            for dp, dns, fns in os.walk(p):
                dns[:] = sorted(d for d in dns if d not in skip)
                for fn in sorted(fns):
                    files.append(Path(dp, fn).relative_to(root).as_posix())
                    if len(files) >= limit:
                        return files, True
        elif p.is_file() or p.is_symlink():
            files.append(rel)
            if len(files) >= limit:
                return files, True
    return files, False


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root: Path, run, cfg: Config, previous: Optional[dict] = None, max_hash_bytes: int = 0) -> dict:
    """Manifest of ignored files: {path: {size, mtime_ns, sha256}} (metadata only).

    Hashing is lazy: if size+mtime match ``previous``, its hash is reused. Files larger
    than ``max_hash_bytes`` (when > 0) are compared by size+mtime only.
    """
    prev_files = (previous or {}).get("files", {})
    files, truncated = _walk_files(
        root, ignored_entries(root, run), cfg.manifest_skip_dirs, max(cfg.manifest_max_files, 0) or 1
    ) if cfg.manifest_max_files else ([], False)
    rec: Dict[str, dict] = {}
    for rel in files:
        p = root / rel
        try:
            st = p.lstat()
        except OSError:
            continue
        if not os.path.isfile(p) or os.path.islink(p):
            continue
        entry = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": None}
        old = prev_files.get(rel)
        if old and old.get("size") == st.st_size and old.get("mtime_ns") == st.st_mtime_ns:
            entry["sha256"] = old.get("sha256")
        elif not max_hash_bytes or st.st_size <= max_hash_bytes:
            try:
                entry["sha256"] = _sha256(p)
            except OSError:
                pass
        rec[rel] = entry
    return {"version": 1, "truncated": truncated, "skip_dirs": cfg.manifest_skip_dirs, "files": rec}


def compare(old: dict, new: dict, prefix: Optional[str] = None, exclude: Optional[set] = None) -> dict:
    a, b = old.get("files", {}), new.get("files", {})
    exclude = exclude or set()

    def keep(p: str) -> bool:
        if p in exclude:
            return False
        return not prefix or p == prefix.rstrip("/") or p.startswith(prefix.rstrip("/") + "/")

    added = sorted(p for p in b if p not in a and keep(p))
    removed = sorted(p for p in a if p not in b and keep(p))
    changed = []
    for p in sorted(set(a) & set(b)):
        if not keep(p):
            continue
        x, y = a[p], b[p]
        if x.get("sha256") and y.get("sha256"):
            if x["sha256"] != y["sha256"]:
                changed.append(p)
        elif x.get("size") != y.get("size") or x.get("mtime_ns") != y.get("mtime_ns"):
            changed.append(p)
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "truncated": bool(old.get("truncated") or new.get("truncated")),
    }


# ---------------------------------------------------------------- capture

def resolve_includes(root: Path, cfg: Config, ignored_files: List[str]) -> Tuple[List[str], List[str]]:
    """Return (capture, refused_secrets) for include_ignored patterns.

    A pattern matches a path exactly, any file under it (directory), or as an fnmatch glob.
    Only gitignored files are considered; ordinary files are captured anyway.
    """
    if not cfg.include_ignored:
        return [], []
    pats = [p.strip().strip("/").replace("\\", "/") for p in cfg.include_ignored]
    capture: List[str] = []
    refused: List[str] = []
    for rel in ignored_files:
        if _is_internal(rel):
            continue
        hit = any(
            rel == p or rel.startswith(p + "/") or fnmatch.fnmatchcase(rel, p) for p in pats if p
        )
        if not hit:
            continue
        if not cfg.allow_secrets and is_secret_path(rel):
            refused.append(rel)
        else:
            capture.append(rel)
    return sorted(set(capture)), sorted(set(refused))


def list_ignored_files_for_capture(root: Path, run, cfg: Config) -> List[str]:
    """All ignored files under include patterns (not limited by the manifest cap or skip dirs)."""
    if not cfg.include_ignored:
        return []
    out = run(root, ["ls-files", "-z", "-o", "-i", "--exclude-standard"], check=True)
    cached = run(root, ["ls-files", "-z", "-c", "-i", "--exclude-standard"], check=True)
    names = set((out.stdout or "").split("\0")) | set((cached.stdout or "").split("\0"))
    return sorted(n for n in names if n and not _is_internal(n) and (root / n).is_file())


# ---------------------------------------------------------------- manifest files

def manifest_dir(store: Path) -> Path:
    return store / MANIFEST_DIRNAME


def write_manifest(store: Path, full_id: str, manifest: dict) -> None:
    d = manifest_dir(store)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{full_id}.tmp"
    tmp.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    os.replace(tmp, d / f"{full_id}.json")


def read_manifest(store: Path, full_id: str) -> Optional[dict]:
    p = manifest_dir(store) / f"{full_id}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
