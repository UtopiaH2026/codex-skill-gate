from __future__ import annotations

import argparse
import json
from pathlib import Path
from skill_gate.classifier import classify
from skill_gate.config import load_config
from skill_gate.hook import main as hook_main
from skill_gate.hook import run_hook
from skill_gate.indexer import build_index, load_index
from skill_gate.installer import doctor as doctor_impl
from skill_gate.installer import install as install_impl
from skill_gate.installer import uninstall as uninstall_impl
from skill_gate.paths import RuntimePaths
from skill_gate.state import load_state, reset_state


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _scope_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-root", default=str(Path.cwd()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill-gate",
        description="Binary coding/non-coding gate for Codex skill metadata.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", aliases=["init"], help="Install the hook and config")
    _scope_args(install_parser)
    install_parser.add_argument("--dry-run", action="store_true", help="Print the plan without writing")

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove Skill Gate configuration")
    _scope_args(uninstall_parser)

    doctor_parser = subparsers.add_parser("doctor", help="Check installation health")
    _scope_args(doctor_parser)
    doctor_parser.add_argument("--json", action="store_true")

    index_parser = subparsers.add_parser("index", help="Build or refresh the skill index")
    index_parser.add_argument("--project-root", default=str(Path.cwd()))
    index_parser.add_argument("--json", action="store_true")

    hook_parser = subparsers.add_parser("hook", help="Run the UserPromptSubmit hook")
    hook_parser.add_argument("--prompt", help="Test payload prompt instead of reading stdin")
    hook_parser.add_argument("--session-id", default="test-session")
    hook_parser.add_argument("--transcript-path", default="")
    hook_parser.add_argument("--cwd", default=str(Path.cwd()))

    classify_parser = subparsers.add_parser("classify", help="Classify a prompt without running the hook")
    classify_parser.add_argument("prompt")
    classify_parser.add_argument("--cwd", default=str(Path.cwd()))
    classify_parser.add_argument("--history", action="append", default=[])

    status_parser = subparsers.add_parser("status", help="Show state for one session")
    status_parser.add_argument("--session-id", default="test-session")
    status_parser.add_argument("--transcript-path", default="")

    reset_parser = subparsers.add_parser("reset", help="Reset one session to non-coding")
    reset_parser.add_argument("--session-id", required=True)
    reset_parser.add_argument("--transcript-path", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve() if hasattr(args, "project_root") else Path.cwd()
    runtime_paths = RuntimePaths.discover()

    if args.command in {"install", "init"}:
        result = install_impl(
            scope=args.scope,
            project_root=project_root,
            package_dir=Path(__file__).resolve().parent,
            dry_run=args.dry_run,
        )
        print(_json(result))
        return 0

    if args.command == "uninstall":
        print(_json(uninstall_impl(scope=args.scope, project_root=project_root)))
        return 0

    if args.command == "doctor":
        result = doctor_impl(scope=args.scope, project_root=project_root)
        if args.json:
            print(_json(result))
        else:
            print(f"Codex Skill Gate: {'OK' if result['ok'] else 'NOT READY'}")
            for key, value in result.items():
                if key != "ok":
                    print(f"  {key}: {value}")
        return 0 if result["ok"] else 1

    if args.command == "index":
        config = load_config(runtime_paths.config_file, create=True)
        index = build_index(cwd=project_root, runtime_paths=runtime_paths, config=config)
        if args.json:
            print(_json({"skills": len(index.get("skills", [])), "index": str(runtime_paths.index_file)}))
        else:
            print(f"Indexed {len(index.get('skills', []))} skills -> {runtime_paths.index_file}")
        return 0

    if args.command == "hook":
        if args.prompt is None:
            return hook_main()
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": args.prompt,
            "session_id": args.session_id,
            "transcript_path": args.transcript_path,
            "cwd": args.cwd,
        }
        print(_json(run_hook(payload, runtime_paths=runtime_paths)))
        return 0

    if args.command == "classify":
        config = load_config(runtime_paths.config_file, create=True)
        result = classify(
            args.prompt,
            recent_messages=args.history,
            cwd=Path(args.cwd),
            classifier_config=config.get("classifier", {}),
        )
        print(_json({"mode": result.mode, "score": result.score, "evidence": result.evidence}))
        return 0

    if args.command == "status":
        print(_json(load_state(runtime_paths, args.session_id, args.transcript_path)))
        return 0

    if args.command == "reset":
        reset_state(runtime_paths, args.session_id, args.transcript_path)
        print(_json({"session_id": args.session_id, "mode": "non_coding"}))
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
