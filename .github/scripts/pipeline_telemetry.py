#!/usr/bin/env python3
"""Record durable telemetry for Tableau-to-Power-BI pipeline stages.

The recorder uses only the Python standard library and writes atomically to
`.specify/memory/<WorkbookName>/pipeline-state.json` by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
TERMINAL_STAGE_STATUSES = {"completed", "failed", "skipped"}
COMMAND_STATUSES = {"complete": "completed", "fail": "failed", "skip": "skipped"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def duration_ms(started_at: str, ended_at: str) -> int:
    elapsed = parse_timestamp(ended_at) - parse_timestamp(started_at)
    return max(0, round(elapsed.total_seconds() * 1000))


def default_state(workbook: str) -> dict[str, Any]:
    timestamp = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "workbook": workbook,
        "run": {
            "id": str(uuid.uuid4()),
            "status": "not_started",
            "started_at": None,
            "ended_at": None,
            "duration_ms": None,
        },
        "stages": {},
        "validation_results": [],
        "run_history": [],
        "totals": {
            "stage_attempts": 0,
            "retries": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "known_token_attempts": 0,
            "unknown_token_attempts": 0,
            "duration_ms": 0,
        },
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def state_path(args: argparse.Namespace) -> Path:
    if args.state:
        return Path(args.state).resolve()
    return (
        Path(args.workspace).resolve()
        / ".specify"
        / "memory"
        / args.workbook
        / "pipeline-state.json"
    )


def read_state(path: Path, workbook: str) -> dict[str, Any]:
    if not path.exists():
        return default_state(workbook)
    with path.open("r", encoding="utf-8") as state_file:
        state = json.load(state_file)
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported telemetry schema: {state.get('schema_version')}")
    if state.get("workbook") != workbook:
        raise ValueError(
            f"State belongs to workbook '{state.get('workbook')}', not '{workbook}'"
        )
    return state


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now()
    payload = json.dumps(state, indent=2, ensure_ascii=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as state_file:
            state_file.write(payload)
            state_file.flush()
            os.fsync(state_file.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def display_path(path: Path, workspace: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return str(path)


def describe_artifact(raw_path: str, workspace: Path) -> dict[str, Any]:
    path = Path(raw_path)
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Artifact does not exist: {path}")

    if path.is_file():
        digest, size = sha256_file(path)
        return {
            "path": display_path(path, workspace),
            "type": "file",
            "sha256": digest,
            "size_bytes": size,
        }

    digest = hashlib.sha256()
    total_size = 0
    file_count = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        child_digest, child_size = sha256_file(child)
        relative_path = child.relative_to(path).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(child_digest.encode("ascii"))
        digest.update(b"\n")
        total_size += child_size
        file_count += 1
    return {
        "path": display_path(path, workspace),
        "type": "directory",
        "sha256": digest.hexdigest(),
        "size_bytes": total_size,
        "file_count": file_count,
    }


def active_attempt(state: dict[str, Any], stage_id: str) -> dict[str, Any]:
    stage = state.get("stages", {}).get(stage_id)
    if not stage or not stage.get("attempts"):
        raise ValueError(f"Stage '{stage_id}' has not been started")
    attempt = stage["attempts"][-1]
    if attempt["status"] != "running":
        raise ValueError(
            f"Latest attempt for stage '{stage_id}' is '{attempt['status']}', not running"
        )
    return attempt


def recalculate_totals(state: dict[str, Any]) -> None:
    attempts = [
        attempt
        for stage in state.get("stages", {}).values()
        for attempt in stage.get("attempts", [])
    ]
    known_usage = [attempt["usage"] for attempt in attempts if attempt.get("usage")]
    state["totals"] = {
        "stage_attempts": len(attempts),
        "retries": sum(max(0, len(stage.get("attempts", [])) - 1) for stage in state.get("stages", {}).values()),
        "input_tokens": sum(usage["input_tokens"] for usage in known_usage),
        "output_tokens": sum(usage["output_tokens"] for usage in known_usage),
        "total_tokens": sum(usage["total_tokens"] for usage in known_usage),
        "known_token_attempts": len(known_usage),
        "unknown_token_attempts": len(attempts) - len(known_usage),
        "duration_ms": sum(attempt.get("duration_ms") or 0 for attempt in attempts),
    }


def command_init(args: argparse.Namespace, path: Path) -> dict[str, Any]:
    if path.exists() and not args.reset:
        state = read_state(path, args.workbook)
        if args.new_run:
            if state["run"]["status"] == "running":
                raise ValueError("Cannot start a new run while the current run is running")
            history = state.get("run_history", [])
            history.append(
                {
                    "run": state["run"],
                    "stages": state["stages"],
                    "validation_results": state["validation_results"],
                    "totals": state["totals"],
                    "archived_at": utc_now(),
                }
            )
            state = default_state(args.workbook)
            state["run_history"] = history
    else:
        state = default_state(args.workbook)
    write_state(path, state)
    return state


def command_start(args: argparse.Namespace, path: Path) -> dict[str, Any]:
    state = read_state(path, args.workbook)
    stage = state["stages"].setdefault(
        args.stage, {"name": args.name or args.stage, "status": "not_started", "attempts": []}
    )
    if stage["attempts"] and stage["attempts"][-1]["status"] == "running":
        raise ValueError(f"Stage '{args.stage}' already has a running attempt")

    timestamp = utc_now()
    if state["run"]["started_at"] is None:
        state["run"].update({"status": "running", "started_at": timestamp, "ended_at": None, "duration_ms": None})
    stage["name"] = args.name or stage["name"]
    stage["status"] = "running"
    stage["attempts"].append(
        {
            "attempt": len(stage["attempts"]) + 1,
            "status": "running",
            "agent": args.agent,
            "model": args.model,
            "started_at": timestamp,
            "ended_at": None,
            "duration_ms": None,
            "usage": None,
            "artifacts": [],
            "error": None,
        }
    )
    recalculate_totals(state)
    write_state(path, state)
    return state


def usage_from_args(args: argparse.Namespace) -> dict[str, int] | None:
    values = (args.input_tokens, args.output_tokens, args.total_tokens)
    if all(value is None for value in values):
        return None
    input_tokens = args.input_tokens or 0
    output_tokens = args.output_tokens or 0
    total_tokens = args.total_tokens
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens
    if min(input_tokens, output_tokens, total_tokens) < 0:
        raise ValueError("Token counts cannot be negative")
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "source": getattr(args, "source", None) or "runtime",
    }


def finish_attempt(
    args: argparse.Namespace, path: Path, status: str, error: str | None = None
) -> dict[str, Any]:
    state = read_state(path, args.workbook)
    attempt = active_attempt(state, args.stage)
    timestamp = utc_now()
    attempt.update(
        {
            "status": status,
            "ended_at": timestamp,
            "duration_ms": duration_ms(attempt["started_at"], timestamp),
            "usage": usage_from_args(args),
            "artifacts": [
                describe_artifact(artifact, Path(args.workspace).resolve())
                for artifact in args.artifact
            ],
            "error": error,
        }
    )
    state["stages"][args.stage]["status"] = status
    recalculate_totals(state)
    write_state(path, state)
    return state


def command_validation(args: argparse.Namespace, path: Path) -> dict[str, Any]:
    state = read_state(path, args.workbook)
    output_artifact = None
    if args.output:
        output_artifact = describe_artifact(args.output, Path(args.workspace).resolve())
    state["validation_results"].append(
        {
            "stage": args.stage,
            "validator": args.validator,
            "status": args.status,
            "exit_code": args.exit_code,
            "summary": args.summary,
            "output": output_artifact,
            "recorded_at": utc_now(),
        }
    )
    write_state(path, state)
    return state


def command_update_usage(args: argparse.Namespace, path: Path) -> dict[str, Any]:
    """Attach reconciled real token usage to an already-terminal stage attempt.

    No caller has real usage at record time, so `complete`/`fail` always leave
    usage unknown. This lets it be backfilled later from an actual source
    (e.g. cloud session-store event data) without ever estimating.
    """
    state = read_state(path, args.workbook)
    stage = state.get("stages", {}).get(args.stage)
    if not stage or not stage.get("attempts"):
        raise ValueError(f"Stage '{args.stage}' has no attempts")
    attempts = stage["attempts"]
    if args.attempt is not None:
        matches = [attempt for attempt in attempts if attempt["attempt"] == args.attempt]
        if not matches:
            raise ValueError(f"Attempt {args.attempt} not found for stage '{args.stage}'")
        attempt = matches[0]
    else:
        attempt = attempts[-1]
    if attempt["status"] == "running":
        raise ValueError("Cannot reconcile usage on a running attempt; complete/fail it first")
    usage = usage_from_args(args)
    if usage is None:
        raise ValueError("Provide at least one of --input-tokens/--output-tokens/--total-tokens")
    if not args.source:
        raise ValueError("--source is required to record where reconciled usage came from")
    attempt["usage"] = usage
    recalculate_totals(state)
    write_state(path, state)
    return state


def command_run_finish(args: argparse.Namespace, path: Path) -> dict[str, Any]:
    state = read_state(path, args.workbook)
    timestamp = utc_now()
    unfinished = [
        stage_id
        for stage_id, stage in state["stages"].items()
        if stage["status"] not in TERMINAL_STAGE_STATUSES
    ]
    if unfinished and args.status == "completed":
        raise ValueError(f"Cannot complete run; unfinished stages: {', '.join(unfinished)}")
    state["run"].update(
        {
            "status": args.status,
            "ended_at": timestamp,
            "duration_ms": duration_ms(state["run"]["started_at"], timestamp)
            if state["run"]["started_at"]
            else 0,
        }
    )
    write_state(path, state)
    return state


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workbook", required=True, help="PascalCase workbook scope name")
    parser.add_argument("--workspace", default=".", help="Workspace root (default: current directory)")
    parser.add_argument("--state", help="Override pipeline-state.json path")


def add_token_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--output-tokens", type=int)
    parser.add_argument("--total-tokens", type=int)
    parser.add_argument("--source", help="Where usage came from, e.g. runtime, session-store-reconciliation")


def add_usage_arguments(parser: argparse.ArgumentParser) -> None:
    add_token_arguments(parser)
    parser.add_argument("--artifact", action="append", default=[], help="Artifact path to hash; repeatable")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create or inspect pipeline state")
    add_common_arguments(init_parser)
    init_mode = init_parser.add_mutually_exclusive_group()
    init_mode.add_argument("--reset", action="store_true", help="Start a new run and discard prior state")
    init_mode.add_argument("--new-run", action="store_true", help="Archive the finished run and start another")

    start_parser = subparsers.add_parser("start", help="Start a stage attempt")
    add_common_arguments(start_parser)
    start_parser.add_argument("--stage", required=True)
    start_parser.add_argument("--name")
    start_parser.add_argument("--agent")
    start_parser.add_argument("--model")

    for command in ("complete", "fail", "skip"):
        finish_parser = subparsers.add_parser(command, help=f"Mark a stage attempt {command}")
        add_common_arguments(finish_parser)
        finish_parser.add_argument("--stage", required=True)
        add_usage_arguments(finish_parser)
        if command == "fail":
            finish_parser.add_argument("--error", required=True)

    validation_parser = subparsers.add_parser("validation", help="Append a validation result")
    add_common_arguments(validation_parser)
    validation_parser.add_argument("--stage", required=True)
    validation_parser.add_argument("--validator", required=True)
    validation_parser.add_argument("--status", required=True, choices=("passed", "warning", "failed"))
    validation_parser.add_argument("--exit-code", required=True, type=int)
    validation_parser.add_argument("--summary")
    validation_parser.add_argument("--output", help="Validator output file to hash")

    update_usage_parser = subparsers.add_parser(
        "update-usage", help="Attach reconciled real token usage to a completed/failed stage attempt"
    )
    add_common_arguments(update_usage_parser)
    update_usage_parser.add_argument("--stage", required=True)
    update_usage_parser.add_argument("--attempt", type=int, help="Attempt number (default: latest)")
    add_token_arguments(update_usage_parser)

    run_parser = subparsers.add_parser("run-finish", help="Mark the full pipeline run complete or failed")
    add_common_arguments(run_parser)
    run_parser.add_argument("--status", required=True, choices=("completed", "failed", "cancelled"))

    show_parser = subparsers.add_parser("show", help="Print the current state")
    add_common_arguments(show_parser)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    path = state_path(args)
    try:
        if args.command == "init":
            state = command_init(args, path)
        elif args.command == "start":
            state = command_start(args, path)
        elif args.command in COMMAND_STATUSES:
            error = args.error if args.command == "fail" else None
            state = finish_attempt(args, path, COMMAND_STATUSES[args.command], error)
        elif args.command == "validation":
            state = command_validation(args, path)
        elif args.command == "update-usage":
            state = command_update_usage(args, path)
        elif args.command == "run-finish":
            state = command_run_finish(args, path)
        else:
            state = read_state(path, args.workbook)
        print(json.dumps({"state_path": str(path), "state": state}, indent=2))
        return 0
    except (FileNotFoundError, json.JSONDecodeError, OSError, ValueError) as error:
        print(f"pipeline_telemetry: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())