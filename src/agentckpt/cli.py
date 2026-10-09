"""agentckpt CLI."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

from agentckpt import __version__
from agentckpt import store as S


def _err(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)


def _out_json(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else S.find_root()
    root, created = S.init_store(root)
    if created:
        print(f"Initialized agentckpt store at {S.store_path(root)}")
    else:
        print(f"Store already exists at {S.store_path(root)}")
    print(f"Root: {root}")
    return 0


def cmd_snap(args: argparse.Namespace) -> int:
    root = S.find_root()
    try:
        snap, skipped = S.snap(root, message=args.message or "", max_bytes=args.max_bytes)
    except S.AgentckptError as e:
        _err(str(e))
        return 2
    if args.json:
        _out_json({"snapshot": snap.to_dict(), "skipped_large": skipped})
    else:
        print(f"{snap.id}  {snap.timestamp}  {snap.file_count} files  {snap.message}")
        for p in skipped:
            print(f"  skipped (>{args.max_bytes} bytes): {p}", file=sys.stderr)
    return 0


def cmd_ls(args: argparse.Namespace) -> int:
    root = S.find_root()
    try:
        snaps = S.list_snapshots(root)
    except S.AgentckptError as e:
        _err(str(e))
        return 2
    if args.json:
        _out_json([s.to_dict() for s in snaps])
    else:
        if not snaps:
            print("(no snapshots yet — run `agentckpt snap`)")
            return 0
        print(f"{'ID':<10}  {'TIME':<25}  {'FILES':>6}  MESSAGE")
        for s in snaps:
            print(f"{s.id:<10}  {s.timestamp:<25}  {s.file_count:>6}  {s.message}")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    root = S.find_root()
    try:
        text = S.diff_snapshot(root, args.id, args.path, to_id=args.to)
    except S.AgentckptError as e:
        _err(str(e))
        return 2
    if args.json:
        _out_json({"diff": text})
    else:
        if text:
            print(text, end="" if text.endswith("\n") else "\n")
        else:
            print("(no differences)")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    root = S.find_root()
    try:
        result = S.restore(root, args.id, path=args.path, force=args.force)
    except S.AgentckptError as e:
        _err(str(e))
        return 2
    if args.json:
        _out_json(result)
    else:
        print(f"Restored {len(result['restored'])} file(s) from {result['snapshot']}")
        for p in result["restored"]:
            print(f"  + {p}")
        if result["skipped_conflict"]:
            print(
                f"Skipped {len(result['skipped_conflict'])} conflict(s) "
                "(working tree differs; re-run with --force to overwrite):",
                file=sys.stderr,
            )
            for p in result["skipped_conflict"]:
                print(f"  ! {p}", file=sys.stderr)
            return 1
        if result["skipped_protected"]:
            for p in result["skipped_protected"]:
                print(f"  x protected: {p}", file=sys.stderr)
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    root = S.find_root()
    try:
        dropped = S.prune(root, keep=args.keep)
    except S.AgentckptError as e:
        _err(str(e))
        return 2
    if args.json:
        _out_json({"dropped": dropped, "kept": args.keep})
    else:
        if not dropped:
            print(f"Nothing to prune (already ≤ {args.keep}).")
        else:
            print(f"Pruned {len(dropped)} snapshot(s); kept {args.keep}.")
            for d in dropped:
                print(f"  - {d}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = S.find_root()
    report = S.doctor(root)
    if args.json:
        _out_json(report)
    else:
        status = "OK" if report["ok"] else "ISSUES"
        print(f"agentckpt doctor — {status}")
        print(f"  root:        {report['root']}")
        print(f"  store:       {report['store']}")
        print(f"  initialized: {report['initialized']}")
        print(f"  git on PATH: {report['git_on_path']}")
        print(f"  gitignore:   {'ok' if report['gitignore_ok'] else 'MISSING .agentckpt/'}")
        print(f"  snapshots:   {report['snap_count']}")
        for issue in report["issues"]:
            print(f"  ! {issue}")
    return 0 if report["ok"] else 1


def cmd_watch(args: argparse.Namespace) -> int:
    root = S.find_root()
    if not S.is_initialized(root):
        _err("Not initialized. Run `agentckpt init` first.")
        return 2
    debounce = max(100, args.debounce) / 1000.0
    print(f"Watching {root} (poll every {debounce:.2f}s). Ctrl-C to stop.")
    try:
        prev = S.fingerprint_tree(root)
    except S.AgentckptError as e:
        _err(str(e))
        return 2
    # Baseline snap so first restore point exists
    try:
        S.snap(root, message="watch: baseline")
    except S.AgentckptError:
        pass
    try:
        while True:
            time.sleep(debounce)
            try:
                cur = S.fingerprint_tree(root)
            except S.AgentckptError as e:
                _err(str(e))
                return 2
            if cur != prev:
                snap, skipped = S.snap(root, message="watch: auto")
                print(f"auto-snap {snap.id}  {snap.file_count} files  {snap.message}")
                for p in skipped:
                    print(f"  skipped large: {p}", file=sys.stderr)
                prev = cur
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Self-contained demo for CI and README — temp dir, snap, modify, restore."""
    with tempfile.TemporaryDirectory(prefix="agentckpt-demo-") as td:
        root = Path(td)
        (root / "hello.txt").write_text("hello agent\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
        (root / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        (root / "noise.pyc").write_text("ignored\n", encoding="utf-8")

        S.init_store(root)
        snap1, _ = S.snap(root, message="demo: initial")
        print(f"[ok] snap {snap1.id}  ({snap1.file_count} files)")

        (root / "hello.txt").write_text("hello agent — corrupted by agent\n", encoding="utf-8")
        (root / "src" / "app.py").write_text("print('v2 broken')\n", encoding="utf-8")
        (root / "src" / "new.py").write_text("# accidental\n", encoding="utf-8")

        snap2, _ = S.snap(root, message="demo: after agent edit")
        print(f"[ok] snap {snap2.id}  ({snap2.file_count} files)")

        diff = S.diff_snapshot(root, snap1.id)
        assert "hello agent" in diff or "corrupted" in diff or diff
        print("[ok] diff shows agent edits")

        result = S.restore(root, snap1.id, force=True)
        assert (root / "hello.txt").read_text(encoding="utf-8") == "hello agent\n"
        assert (root / "src" / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
        print(f"[ok] restore {snap1.id} → {len(result['restored'])} files")

        # Conflict path
        (root / "hello.txt").write_text("local edit\n", encoding="utf-8")
        conflicted = S.restore(root, snap1.id, force=False)
        assert "hello.txt" in conflicted["skipped_conflict"]
        print("[ok] conflict refused without --force")

        snaps = S.list_snapshots(root)
        assert len(snaps) >= 2
        print(f"[ok] ls → {len(snaps)} snapshots")

        dropped = S.prune(root, keep=1)
        assert len(S.list_snapshots(root)) == 1
        print(f"[ok] prune kept 1 (dropped {len(dropped)})")

        rep = S.doctor(root)
        assert rep["ok"], rep
        print("[ok] doctor OK")

        # gitignore respected: noise.pyc never in tree
        tip = S.current_tip(root)
        assert tip is not None
        names = S._files_in_tree(root, tip.full_id)
        assert "noise.pyc" not in names
        print("[ok] .gitignore respected")

        print("PASS: agentckpt demo passed")
        return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentckpt",
        description=(
            "Checkpoint a working tree (including untracked files) while coding agents run, "
            "and restore any snapshot without touching your git branches or index."
        ),
    )
    p.add_argument("--version", action="version", version=f"agentckpt {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="Create .agentckpt/ shadow store")
    sp.add_argument("--root", help="Project root (default: walk up for .git / cwd)")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("snap", help="Take a snapshot of the working tree")
    sp.add_argument("-m", "--message", default="", help="Snapshot message")
    sp.add_argument(
        "--max-bytes",
        type=int,
        default=S.DEFAULT_MAX_BYTES,
        help=f"Skip files larger than this (default {S.DEFAULT_MAX_BYTES})",
    )
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_snap)

    sp = sub.add_parser("ls", help="List snapshots")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_ls)

    sp = sub.add_parser("diff", help="Diff a snapshot against the working tree (or --to)")
    sp.add_argument("id", help="Snapshot id")
    sp.add_argument("path", nargs="?", help="Optional path filter")
    sp.add_argument("--to", dest="to", help="Compare to another snapshot id")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_diff)

    sp = sub.add_parser("restore", help="Restore files from a snapshot")
    sp.add_argument("id", help="Snapshot id")
    sp.add_argument("--path", "-p", help="Restore only this path")
    sp.add_argument(
        "--force",
        action="store_true",
        help="Overwrite working-tree files that differ from the snapshot",
    )
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_restore)

    sp = sub.add_parser("prune", help="Keep only the newest N snapshots")
    sp.add_argument("--keep", type=int, default=S.DEFAULT_KEEP, help=f"Default {S.DEFAULT_KEEP}")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_prune)

    sp = sub.add_parser("doctor", help="Sanity-check the store")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("watch", help="Auto-snap on filesystem changes (stdlib polling)")
    sp.add_argument(
        "--debounce",
        type=int,
        default=800,
        help="Milliseconds between polls (default 800)",
    )
    sp.set_defaults(func=cmd_watch)

    sp = sub.add_parser("demo", help="Run a self-contained snap/restore demo (for CI)")
    sp.set_defaults(func=cmd_demo)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except S.AgentckptError as e:
        _err(str(e))
        return 2
    except BrokenPipeError:
        return 0
