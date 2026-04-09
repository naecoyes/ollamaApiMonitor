from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional


_SINCE_RE = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)


def parse_since_expression(value: str, now: Optional[datetime] = None) -> datetime:
    match = _SINCE_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid --since value: {value!r}. Use values like 30m, 24h, or 7d.")

    amount = int(match.group(1))
    unit = match.group(2).lower()
    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    reference = now or datetime.now().astimezone()
    return reference - timedelta(seconds=amount * multiplier)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


class JsonlStore:
    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self._write_lock = asyncio.Lock()

    def ensure_dir(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _daily_log_path(self, current_time: datetime) -> Path:
        return self.log_dir / f"{current_time.date().isoformat()}.jsonl"

    def _append_sync(self, record: Dict[str, Any]) -> None:
        self.ensure_dir()
        timestamp = parse_timestamp(record["timestamp"])
        path = self._daily_log_path(timestamp.astimezone())
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def append(self, record: Dict[str, Any]) -> None:
        async with self._write_lock:
            await asyncio.to_thread(self._append_sync, record)

    def iter_records(
        self,
        since: Optional[datetime] = None,
        model: Optional[str] = None,
    ) -> Iterable[Dict[str, Any]]:
        self.ensure_dir()
        paths = sorted(self.log_dir.glob("*.jsonl"))
        for path in paths:
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if model and record.get("model") != model:
                            continue
                        timestamp_raw = record.get("timestamp")
                        if not timestamp_raw:
                            continue
                        try:
                            record_time = parse_timestamp(timestamp_raw)
                        except ValueError:
                            continue
                        if since and record_time < since:
                            continue
                        yield record
            except FileNotFoundError:
                continue

    def query_records(
        self,
        since: Optional[datetime] = None,
        model: Optional[str] = None,
        newest_first: bool = False,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        records = list(self.iter_records(since=since, model=model))
        records.sort(key=lambda record: record.get("timestamp", ""))
        if newest_first:
            records.reverse()
        if limit is not None:
            records = records[:limit]
        return records

    def list_models(self) -> List[str]:
        models = set()
        for record in self.iter_records():
            model = record.get("model")
            if model:
                models.add(model)
        return sorted(models)

    def follow(
        self,
        model: Optional[str] = None,
        poll_interval: float = 1.0,
    ) -> Generator[Dict[str, Any], None, None]:
        self.ensure_dir()
        offsets = {path: path.stat().st_size for path in self.log_dir.glob("*.jsonl")}

        while True:
            current_files = sorted(self.log_dir.glob("*.jsonl"))
            for path in current_files:
                if path not in offsets:
                    offsets[path] = 0
                try:
                    size = path.stat().st_size
                except FileNotFoundError:
                    continue
                if offsets[path] > size:
                    offsets[path] = 0
                if size == offsets[path]:
                    continue

                try:
                    with path.open("r", encoding="utf-8") as handle:
                        handle.seek(offsets[path])
                        while True:
                            line = handle.readline()
                            if not line:
                                break
                            offsets[path] = handle.tell()
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                record = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if model and record.get("model") != model:
                                continue
                            yield record
                        offsets[path] = handle.tell()
                except FileNotFoundError:
                    continue

            time.sleep(poll_interval)
