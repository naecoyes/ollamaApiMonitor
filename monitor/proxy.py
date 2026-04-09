from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import ClientConnectionError, ClientResponse, ClientSession, ClientTimeout, web

from .dashboard import DashboardService
from .store import JsonlStore


TRACKED_PATHS = {"/api/chat", "/api/generate", "/api/embed"}
STREAMABLE_PATHS = {"/api/chat", "/api/generate"}
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _safe_json_loads(raw_bytes: bytes) -> Optional[Dict[str, Any]]:
    if not raw_bytes:
        return None
    try:
        value = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _duration_ms(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value) / 1_000_000, 2)
    except (TypeError, ValueError):
        return None


def _extract_request_meta(path: str, body: bytes) -> Dict[str, Any]:
    data = _safe_json_loads(body) or {}
    stream = bool(data.get("stream")) if path in STREAMABLE_PATHS else False
    return {
        "model": data.get("model"),
        "stream": stream,
    }


def _extract_usage(path: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = payload or {}
    prompt_tokens = int(payload.get("prompt_eval_count") or 0)
    completion_tokens = 0 if path == "/api/embed" else int(payload.get("eval_count") or 0)
    eval_duration = payload.get("eval_duration")
    tps: Optional[float] = None
    try:
        if completion_tokens > 0 and eval_duration and float(eval_duration) > 0:
            tps = round(completion_tokens / (float(eval_duration) / 1_000_000_000), 2)
    except (TypeError, ValueError, ZeroDivisionError):
        tps = None

    return {
        "model": payload.get("model"),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "total_ms": _duration_ms(payload.get("total_duration")),
        "load_ms": _duration_ms(payload.get("load_duration")),
        "prompt_eval_ms": _duration_ms(payload.get("prompt_eval_duration")),
        "eval_ms": _duration_ms(eval_duration),
        "tps": tps,
        "done_reason": payload.get("done_reason"),
    }


def _client_ip(request: web.Request) -> Optional[str]:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote


def _filter_request_headers(headers: "aiohttp.typedefs.LooseHeaders") -> Dict[str, str]:
    filtered = {}
    for key, value in headers.items():
        if key.lower() in HOP_BY_HOP_HEADERS or key.lower() == "host":
            continue
        filtered[key] = value
    return filtered


def _filter_response_headers(headers: "aiohttp.typedefs.LooseHeaders", streamed: bool) -> Dict[str, str]:
    filtered = {}
    for key, value in headers.items():
        lowered = key.lower()
        if lowered in HOP_BY_HOP_HEADERS:
            continue
        if streamed and lowered == "content-length":
            continue
        filtered[key] = value
    return filtered


class StreamUsageParser:
    def __init__(self) -> None:
        self._buffer = b""
        self._final_payload: Optional[Dict[str, Any]] = None

    def feed(self, chunk: bytes) -> None:
        self._buffer += chunk
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            self._process_line(line)

    def finalize(self) -> Optional[Dict[str, Any]]:
        if self._buffer.strip():
            self._process_line(self._buffer)
        self._buffer = b""
        return self._final_payload

    def _process_line(self, line: bytes) -> None:
        line = line.strip()
        if not line:
            return
        payload = _safe_json_loads(line)
        if isinstance(payload, dict) and payload.get("done") is True:
            self._final_payload = payload


class OllamaProxy:
    def __init__(self, upstream: str, log_dir: Path) -> None:
        self.upstream = upstream.rstrip("/")
        self.store = JsonlStore(log_dir)
        self.session: Optional[ClientSession] = None

    async def session_context(self, _app: web.Application):
        timeout = ClientTimeout(total=None, sock_connect=30, sock_read=None)
        self.session = ClientSession(timeout=timeout)
        yield
        if self.session:
            await self.session.close()

    def _build_record(
        self,
        request: web.Request,
        request_meta: Dict[str, Any],
        status_code: int,
        payload: Optional[Dict[str, Any]],
        error: Optional[str],
    ) -> Dict[str, Any]:
        usage = _extract_usage(request.path, payload)
        model = request_meta.get("model") or usage.get("model")
        success = error is None and 200 <= status_code < 300
        return {
            "request_id": uuid.uuid4().hex,
            "timestamp": datetime.now().astimezone().isoformat(),
            "path": request.path,
            "method": request.method,
            "model": model,
            "stream": bool(request_meta.get("stream")),
            "status_code": status_code,
            "success": success,
            "client_ip": _client_ip(request),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "total_ms": usage.get("total_ms"),
            "load_ms": usage.get("load_ms"),
            "prompt_eval_ms": usage.get("prompt_eval_ms"),
            "eval_ms": usage.get("eval_ms"),
            "tps": usage.get("tps"),
            "done_reason": usage.get("done_reason"),
            "error": error,
        }

    async def handle(self, request: web.Request) -> web.StreamResponse:
        if self.session is None:
            raise web.HTTPServiceUnavailable(text="Proxy session is not ready.")

        tracked = request.method.upper() == "POST" and request.path in TRACKED_PATHS
        request_body = await request.read()
        request_meta = _extract_request_meta(request.path, request_body) if tracked else {}
        upstream_url = f"{self.upstream}{request.rel_url}"
        request_headers = _filter_request_headers(request.headers)

        try:
            async with self.session.request(
                method=request.method,
                url=upstream_url,
                headers=request_headers,
                data=request_body,
                allow_redirects=False,
            ) as upstream_response:
                if tracked and request.path in STREAMABLE_PATHS and request_meta.get("stream"):
                    return await self._stream_response(
                        request=request,
                        upstream_response=upstream_response,
                        request_meta=request_meta,
                    )
                return await self._buffered_response(
                    request=request,
                    upstream_response=upstream_response,
                    request_meta=request_meta,
                    tracked=tracked,
                )
        except (asyncio.TimeoutError, ClientConnectionError, aiohttp.ClientError) as exc:
            if tracked:
                record = self._build_record(
                    request=request,
                    request_meta=request_meta,
                    status_code=502,
                    payload=None,
                    error=str(exc),
                )
                await self.store.append(record)
            return web.json_response(
                {"error": "Upstream request failed", "detail": str(exc)},
                status=502,
            )

    async def _buffered_response(
        self,
        request: web.Request,
        upstream_response: ClientResponse,
        request_meta: Dict[str, Any],
        tracked: bool,
    ) -> web.Response:
        response_body = await upstream_response.read()
        response_headers = _filter_response_headers(upstream_response.headers, streamed=False)
        payload = _safe_json_loads(response_body) if tracked else None
        if tracked:
            error = None if 200 <= upstream_response.status < 300 else f"upstream_status_{upstream_response.status}"
            record = self._build_record(
                request=request,
                request_meta=request_meta,
                status_code=upstream_response.status,
                payload=payload,
                error=error,
            )
            await self.store.append(record)

        return web.Response(
            status=upstream_response.status,
            reason=upstream_response.reason,
            headers=response_headers,
            body=response_body,
        )

    async def _stream_response(
        self,
        request: web.Request,
        upstream_response: ClientResponse,
        request_meta: Dict[str, Any],
    ) -> web.StreamResponse:
        response_headers = _filter_response_headers(upstream_response.headers, streamed=True)
        downstream = web.StreamResponse(
            status=upstream_response.status,
            reason=upstream_response.reason,
            headers=response_headers,
        )
        await downstream.prepare(request)

        parser = StreamUsageParser()
        stream_error: Optional[str] = None

        try:
            async for chunk in upstream_response.content.iter_any():
                if not chunk:
                    continue
                parser.feed(chunk)
                try:
                    await downstream.write(chunk)
                except (ConnectionResetError, RuntimeError) as exc:
                    stream_error = str(exc)
                    break
        except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
            stream_error = str(exc)
        finally:
            payload = parser.finalize()
            try:
                await downstream.write_eof()
            except (ConnectionResetError, RuntimeError):
                pass

            error = stream_error
            if error is None and not 200 <= upstream_response.status < 300:
                error = f"upstream_status_{upstream_response.status}"
            record = self._build_record(
                request=request,
                request_meta=request_meta,
                status_code=upstream_response.status,
                payload=payload,
                error=error,
            )
            await self.store.append(record)

        return downstream


def create_app(upstream: str, log_dir: Path, listen: str, port: int) -> web.Application:
    proxy = OllamaProxy(upstream=upstream, log_dir=log_dir)
    dashboard = DashboardService(log_dir=log_dir, proxy_label=f"{listen}:{port}", upstream_label=upstream)
    app = web.Application(client_max_size=1024**3)
    app.cleanup_ctx.append(proxy.session_context)
    app.router.add_get("/", dashboard.handle_page)
    app.router.add_get("/dashboard", dashboard.handle_page)
    app.router.add_get("/favicon.ico", dashboard.handle_favicon)
    app.router.add_get("/ui/api/overview", dashboard.handle_overview)
    app.router.add_get("/ui/api/export.csv", dashboard.handle_export_csv)
    app.router.add_route("*", "/{tail:.*}", proxy.handle)
    return app


async def run_proxy(listen: str, port: int, upstream: str, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(upstream=upstream, log_dir=log_dir, listen=listen, port=port)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, host=listen, port=port)
        await site.start()

        print(f"Ollama monitor proxy listening on http://{listen}:{port}")
        print(f"Dashboard available at http://{listen}:{port}/dashboard")
        print(f"Forwarding requests to {upstream}")
        print(f"Writing JSONL logs to {Path(log_dir).resolve()}")

        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
