"""Agent hook adapter: turn Codex / Claude Code / Gemini CLI / OpenCode hook payloads into snaps.

Hooks must never break the agent that calls them, so everything here is best-effort:
`run_hook` swallows errors, never writes to stdout unless asked (`--json`), and the CLI
always exits 0. In particular a PreToolUse / BeforeTool hook never denies the tool call.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Any, Dict, Iterator, List, Optional, Tuple

from agentckpt import store as S

MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
STDIN_TIMEOUT_S = 3.0
LOCK_NAME = S.HOOK_LOCK_NAME
LOCK_WAIT_S = 20.0
LOCK_STALE_S = S.HOOK_LOCK_STALE_S
DETAIL_MAX = 60
MESSAGE_MAX = 120

# Gemini CLI uses different event names for the same lifecycle points.
EVENT_ALIASES = {
    "BeforeAgent": "UserPromptSubmit",
    "AfterAgent": "Stop",
    "BeforeTool": "PreToolUse",
    "AfterTool": "PostToolUse",
    "PreCompress": "PreCompact",
}
GEMINI_EVENTS = set(EVENT_ALIASES) | {"BeforeModel", "AfterModel", "BeforeToolSelection"}

_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)


# ---------------------------------------------------------------- payload parsing


def parse_payload(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse a JSON object; return None for empty / invalid / non-object input."""
    if not text or not text.strip():
        return None
    try:
        obj = json.loads(text)
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def read_stdin(stream: Optional[IO] = None, timeout: float = STDIN_TIMEOUT_S) -> Optional[str]:
    """Read hook JSON from stdin without ever hanging the agent.

    Skips TTYs. Reads in a daemon thread so a pipe that is never closed costs at most
    `timeout` seconds instead of blocking forever.
    """
    stream = stream if stream is not None else sys.stdin
    if stream is None:
        return None
    try:
        if stream.isatty():
            return None
    except (AttributeError, ValueError, OSError):
        return None

    box: Dict[str, Any] = {}

    def _reader() -> None:
        try:
            buf = getattr(stream, "buffer", None)
            if buf is not None:
                data = buf.read(MAX_PAYLOAD_BYTES)
                box["text"] = data.decode("utf-8", errors="replace") if data else ""
            else:
                box["text"] = stream.read(MAX_PAYLOAD_BYTES) or ""
        except Exception:  # noqa: BLE001 - stdin may be closed, a pytest stub, etc.
            box["text"] = None

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    t.join(timeout)
    return box.get("text")


def normalize_event(payload: Optional[Dict[str, Any]], override: Optional[str] = None) -> str:
    """Canonical event name (Claude Code / Codex spelling)."""
    if override:
        return EVENT_ALIASES.get(override, override)
    if not payload:
        return ""
    if payload.get("type") == "agent-turn-complete":
        return "agent-turn-complete"
    name = payload.get("hook_event_name") or payload.get("hookEventName") or payload.get("type")
    if not isinstance(name, str):
        return ""
    return EVENT_ALIASES.get(name, name)


def infer_source(payload: Optional[Dict[str, Any]], explicit: Optional[str] = None) -> str:
    if explicit:
        return _one_line(explicit, 24) or "agent"
    if payload:
        if payload.get("type") == "agent-turn-complete":
            return "codex"
        raw = payload.get("hook_event_name")
        if isinstance(raw, str) and raw in GEMINI_EVENTS:
            return "gemini"
    return "agent"


# ---------------------------------------------------------------- message building


def _one_line(text: Any, limit: int) -> str:
    if text is None:
        return ""
    s = " ".join(str(text).split())
    if len(s) > limit:
        s = s[: max(1, limit - 3)].rstrip() + "..."
    return s


def _quoted(text: Any, limit: int = DETAIL_MAX) -> str:
    s = _one_line(text, limit)
    return f'"{s}"' if s else ""


def _patch_files(patch: str) -> List[str]:
    return [m.strip() for m in _PATCH_FILE_RE.findall(patch or "")]


def _short_path(val: str, root: Optional[Path]) -> str:
    """Show paths under the project root relative to it (agents usually send absolute ones)."""
    if root is not None:
        try:
            p = Path(val)
            if p.is_absolute():
                rel = p.resolve().relative_to(root.resolve())
                return rel.as_posix() or "."
        except (ValueError, OSError):
            pass
    return val


def tool_detail(tool_name: str, tool_input: Any, root: Optional[Path] = None) -> str:
    """Short human hint for what a tool call touches (a path or a command)."""
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "filePath", "notebook_path", "path", "absolute_path", "dir_path"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            return _one_line(_short_path(val, root), DETAIL_MAX)
    cmd = tool_input.get("command") or tool_input.get("cmd")
    if isinstance(cmd, list):
        cmd = " ".join(str(c) for c in cmd)
    if isinstance(cmd, str) and cmd:
        if tool_name == "apply_patch" or cmd.lstrip().startswith("*** Begin Patch"):
            files = _patch_files(cmd)
            if files:
                more = f" +{len(files) - 1}" if len(files) > 1 else ""
                return _one_line(files[0], DETAIL_MAX) + more
        return f"`{_one_line(cmd, DETAIL_MAX - 2)}`"
    return ""


def build_message(
    payload: Optional[Dict[str, Any]],
    *,
    source: str,
    event: str,
    root: Optional[Path] = None,
) -> str:
    """Derive a one-line snapshot message from a hook payload."""
    p = payload or {}
    parts: List[str] = []
    tool = p.get("tool_name") or p.get("tool") or ""
    tool = tool if isinstance(tool, str) else ""

    if event == "agent-turn-complete":
        msgs = p.get("input-messages") or p.get("input_messages") or []
        last = msgs[-1] if isinstance(msgs, list) and msgs else ""
        parts = ["turn complete", _quoted(last)]
    elif event == "UserPromptSubmit":
        parts = ["before prompt", _quoted(p.get("prompt"))]
    elif event == "PreToolUse":
        parts = ["before", tool or "tool", tool_detail(tool, p.get("tool_input"), root)]
    elif event in ("PostToolUse", "PostToolUseFailure"):
        label = "after" if event == "PostToolUse" else "after failed"
        parts = [label, tool or "tool", tool_detail(tool, p.get("tool_input"), root)]
    elif event == "Stop":
        parts = ["turn end"]
    elif event == "SubagentStop":
        parts = ["subagent end", _one_line(p.get("agent_type"), 30)]
    elif event == "SessionStart":
        src = _one_line(p.get("source"), 20)
        parts = ["session start" + (f" ({src})" if src else "")]
    elif event == "SessionEnd":
        reason = _one_line(p.get("reason"), 20)
        parts = ["session end" + (f" ({reason})" if reason else "")]
    elif event == "Notification":
        parts = ["notification", _quoted(p.get("message"), 50)]
    elif event in ("PreCompact", "PostCompact"):
        trig = _one_line(p.get("trigger"), 20)
        parts = [("before" if event == "PreCompact" else "after") + " compact"
                 + (f" ({trig})" if trig else "")]
    elif event:
        parts = [_one_line(event, 40)]
    else:
        parts = ["hook"]

    body = " ".join(x for x in parts if x)
    return _one_line(f"{source}: {body}", MESSAGE_MAX)


# ---------------------------------------------------------------- root + locking


def resolve_root(payload: Optional[Dict[str, Any]], explicit_root: Optional[str] = None) -> Path:
    """--root, else payload `cwd` (walked up like the rest of the CLI), else process cwd."""
    if explicit_root:
        return Path(explicit_root).expanduser().resolve()
    cwd = (payload or {}).get("cwd") or (payload or {}).get("directory")
    if isinstance(cwd, str) and cwd:
        p = Path(cwd).expanduser()
        if p.is_dir():
            return S.find_root(p)
    return S.find_root()


@contextmanager
def store_lock(root: Path, wait: float = LOCK_WAIT_S) -> Iterator[bool]:
    """Cross-process lock under .agentckpt/ so parallel hooks don't race on the shadow index.

    Yields True if acquired, False on timeout (caller should skip the snap, not fail).
    """
    S.store_path(root).mkdir(parents=True, exist_ok=True)
    path = S.store_path(root) / LOCK_NAME
    deadline = time.monotonic() + wait
    fd = None
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > LOCK_STALE_S:
                    path.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                yield False
                return
            time.sleep(0.05)
    try:
        yield True
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            path.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------- main entry


def run_hook(
    *,
    payload: Optional[Dict[str, Any]],
    source: Optional[str] = None,
    event: Optional[str] = None,
    message: Optional[str] = None,
    root: Optional[str] = None,
    auto_init: bool = False,
    max_bytes: int = S.DEFAULT_MAX_BYTES,
) -> Dict[str, Any]:
    """Snap for one hook invocation. Never raises; returns a result dict."""
    ev = normalize_event(payload, event)
    src = infer_source(payload, source)
    result: Dict[str, Any] = {
        "ok": False,
        "event": ev,
        "source": src,
        "message": _one_line(message, 200) if message else "",
        "root": None,
        "snapshot": None,
        "created": False,
        "skipped": None,
        "skipped_large": [],
    }
    try:
        r = resolve_root(payload, root)
        result["root"] = str(r)
        if not result["message"]:
            result["message"] = build_message(payload, source=src, event=ev, root=r)
        msg = result["message"]
        if not S.is_initialized(r) and not auto_init:
            result["skipped"] = "not initialized (run `agentckpt init` here, or pass --init)"
            return result
        with store_lock(r) as got:
            if not got:
                result["skipped"] = "another agentckpt hook is snapping; skipped"
                return result
            if not S.is_initialized(r):
                S.init_store(r)
            before = S.current_tip(r)
            snap, skipped_large = S.snap(r, message=msg, max_bytes=max_bytes)
        result["ok"] = True
        result["snapshot"] = snap.to_dict()
        result["created"] = before is None or before.full_id != snap.full_id
        result["skipped_large"] = skipped_large
        if not result["created"]:
            result["skipped"] = "no changes since last snapshot"
    except S.AgentckptError as e:
        result["skipped"] = str(e)
    except Exception as e:  # noqa: BLE001 - a hook must never crash the agent
        result["skipped"] = f"{type(e).__name__}: {e}"
    return result


def payload_from_inputs(argv_payload: Optional[str], stdin: Optional[IO] = None) -> Tuple[
    Optional[Dict[str, Any]], str
]:
    """Codex `notify` passes JSON as the last argv; lifecycle hooks pipe it on stdin."""
    if argv_payload:
        obj = parse_payload(argv_payload)
        if obj is not None:
            return obj, "argv"
    obj = parse_payload(read_stdin(stdin))
    if obj is not None:
        return obj, "stdin"
    return None, "none"
