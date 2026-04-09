from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from monitor.cli_views import render_records, render_stats, tail_records
from monitor.store import JsonlStore, parse_since_expression


DEFAULT_LISTEN = "127.0.0.1"
DEFAULT_PORT = 11435
DEFAULT_UPSTREAM = "http://127.0.0.1:11434"
DEFAULT_LOG_DIR = Path(__file__).resolve().parent / "logs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Lightweight Ollama API monitor with local reverse proxy and JSONL logs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Start the local monitoring proxy.")
    serve_parser.add_argument("--listen", default=DEFAULT_LISTEN, help="Proxy listen host.")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Proxy listen port.")
    serve_parser.add_argument(
        "--upstream",
        default=DEFAULT_UPSTREAM,
        help="Upstream Ollama base URL.",
    )
    serve_parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory for daily JSONL logs.",
    )

    stats_parser = subparsers.add_parser("stats", help="Show aggregate metrics from JSONL logs.")
    stats_parser.add_argument("--since", default="24h", help="Time window such as 30m, 24h, or 7d.")
    stats_parser.add_argument("--model", help="Filter by model name.")
    stats_parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory containing daily JSONL logs.",
    )

    list_parser = subparsers.add_parser("list", help="List recent tracked requests.")
    list_parser.add_argument("--since", default="24h", help="Time window such as 30m, 24h, or 7d.")
    list_parser.add_argument("--model", help="Filter by model name.")
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum number of records to show.")
    list_parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory containing daily JSONL logs.",
    )

    tail_parser = subparsers.add_parser("tail", help="Stream new tracked requests as they arrive.")
    tail_parser.add_argument("--model", help="Filter by model name.")
    tail_parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory containing daily JSONL logs.",
    )
    tail_parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds for tail mode.",
    )

    return parser


def handle_stats(args: argparse.Namespace) -> int:
    since_dt = parse_since_expression(args.since)
    store = JsonlStore(args.log_dir)
    records = store.query_records(since=since_dt, model=args.model, newest_first=False)
    print(render_stats(records, since_dt=since_dt))
    return 0


def handle_list(args: argparse.Namespace) -> int:
    since_dt = parse_since_expression(args.since)
    store = JsonlStore(args.log_dir)
    records = store.query_records(
        since=since_dt,
        model=args.model,
        newest_first=True,
        limit=args.limit,
    )
    print(render_records(records))
    return 0


def handle_tail(args: argparse.Namespace) -> int:
    store = JsonlStore(args.log_dir)
    tail_records(store=store, model=args.model, poll_interval=args.poll_interval)
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "serve":
            try:
                from monitor.proxy import run_proxy
            except ModuleNotFoundError as exc:
                if exc.name == "aiohttp":
                    print(
                        "Error: missing dependency 'aiohttp'. Run "
                        "'python3 -m pip install -r requirements.txt' first.",
                        file=sys.stderr,
                    )
                    return 2
                raise
            asyncio.run(
                run_proxy(
                    listen=args.listen,
                    port=args.port,
                    upstream=args.upstream,
                    log_dir=args.log_dir,
                )
            )
            return 0
        if args.command == "stats":
            return handle_stats(args)
        if args.command == "list":
            return handle_list(args)
        if args.command == "tail":
            return handle_tail(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
