from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from .store import parse_timestamp


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "…"


def _format_number(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _record_row(record: Dict[str, Any]) -> List[str]:
    return [
        record.get("timestamp", "-"),
        record.get("model") or "-",
        record.get("path") or "-",
        f"{record.get('prompt_tokens', 0)}->{record.get('completion_tokens', 0)}",
        _format_number(record.get("total_ms")),
        _format_number(record.get("tps")),
        record.get("done_reason") or "-",
        f"{record.get('status_code', '-')}/{('ok' if record.get('success') else 'err')}",
    ]


def render_records(records: List[Dict[str, Any]]) -> str:
    if not records:
        return "No matching records."

    headers = ["timestamp", "model", "path", "tokens(in->out)", "total_ms", "tps", "finish", "status"]
    rows = [_record_row(record) for record in records]
    widths = []
    max_widths = [25, 28, 14, 16, 10, 10, 10, 12]

    for index, header in enumerate(headers):
        content_width = max(len(header), *(len(row[index]) for row in rows))
        widths.append(min(content_width, max_widths[index]))

    def format_row(values: List[str]) -> str:
        parts = []
        for index, value in enumerate(values):
            parts.append(_truncate(value, widths[index]).ljust(widths[index]))
        return " | ".join(parts)

    separator = "-+-".join("-" * width for width in widths)
    lines = [format_row(headers), separator]
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)


def _bucketize(records: List[Dict[str, Any]], since_dt: datetime, until_dt: datetime) -> List[str]:
    if not records:
        return []

    bucket_by_day = (until_dt - since_dt) > timedelta(hours=48)
    buckets = defaultdict(int)
    for record in records:
        stamp = parse_timestamp(record["timestamp"]).astimezone()
        if bucket_by_day:
            key = stamp.strftime("%m-%d")
        else:
            key = stamp.strftime("%m-%d %H:00")
        buckets[key] += 1

    if not buckets:
        return []

    max_count = max(buckets.values())
    scale = 28 / max_count if max_count else 1
    lines = []
    for key in sorted(buckets):
        count = buckets[key]
        bar = "#" * max(1, int(round(count * scale)))
        lines.append(f"{key:>11} | {bar:<28} {count}")
    return lines


def render_stats(records: List[Dict[str, Any]], since_dt: datetime) -> str:
    if not records:
        return "No matching records."

    now = datetime.now().astimezone()
    success_count = sum(1 for record in records if record.get("success"))
    total_tokens = sum(int(record.get("total_tokens") or 0) for record in records)
    total_ms_values = [float(record["total_ms"]) for record in records if record.get("total_ms") is not None]
    tps_values = [float(record["tps"]) for record in records if record.get("tps") is not None]

    summary_lines = [
        f"Window      : {since_dt.isoformat()} -> {now.isoformat()}",
        f"Requests    : {len(records)}",
        f"Success rate: {(success_count / len(records)) * 100:.1f}%",
        f"Total tokens: {total_tokens}",
        f"Avg total ms: {mean(total_ms_values):.2f}" if total_ms_values else "Avg total ms: -",
        f"Avg tps     : {mean(tps_values):.2f}" if tps_values else "Avg tps     : -",
    ]

    by_model = defaultdict(lambda: {"count": 0, "tokens": 0, "total_ms": [], "tps": []})
    for record in records:
        model = record.get("model") or "-"
        bucket = by_model[model]
        bucket["count"] += 1
        bucket["tokens"] += int(record.get("total_tokens") or 0)
        if record.get("total_ms") is not None:
            bucket["total_ms"].append(float(record["total_ms"]))
        if record.get("tps") is not None:
            bucket["tps"].append(float(record["tps"]))

    model_lines = ["", "By model"]
    model_lines.append("model                        | count | tokens | avg_ms  | avg_tps")
    model_lines.append("-----------------------------+-------+--------+---------+--------")
    for model, stats in sorted(
        by_model.items(),
        key=lambda item: (item[1]["count"], item[1]["tokens"]),
        reverse=True,
    ):
        avg_ms = mean(stats["total_ms"]) if stats["total_ms"] else None
        avg_tps = mean(stats["tps"]) if stats["tps"] else None
        model_lines.append(
            f"{_truncate(model, 28).ljust(28)} | "
            f"{str(stats['count']).rjust(5)} | "
            f"{str(stats['tokens']).rjust(6)} | "
            f"{_format_number(avg_ms).rjust(7)} | "
            f"{_format_number(avg_tps).rjust(6)}"
        )

    bucket_lines = ["", "Requests over time"]
    bucket_lines.extend(_bucketize(records, since_dt=since_dt, until_dt=now))

    return "\n".join(summary_lines + model_lines + bucket_lines)


def format_tail_record(record: Dict[str, Any]) -> str:
    return " | ".join(_record_row(record))


def tail_records(store: Any, model: Optional[str], poll_interval: float) -> None:
    print("timestamp | model | path | tokens(in->out) | total_ms | tps | finish | status")
    print("-" * 96)
    for record in store.follow(model=model, poll_interval=poll_interval):
        print(format_tail_record(record), flush=True)
