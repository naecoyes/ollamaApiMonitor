# Ollama API Monitor

Chinese version: [README.zh-CN.md](./README.zh-CN.md)

A lightweight local monitoring proxy for Ollama.

It provides:

- A local reverse proxy in front of Ollama
- Daily JSONL request logs
- CLI views for stats, listing, and live tailing
- A local web dashboard

This project currently targets native Ollama endpoints only. It does not implement an OpenAI-compatible layer, and it does not store prompt or response content.

## Project Layout

```text
llmMonitor/
├── main.py
├── requirements.txt
├── README.md
├── README.en.md
├── README.zh-CN.md
├── logs/
└── monitor/
    ├── __init__.py
    ├── cli_views.py
    ├── dashboard.py
    ├── proxy.py
    └── store.py
```

## Requirements

- Python 3.9+
- A running local Ollama service, defaulting to `http://127.0.0.1:11434`

## Installation

```bash
cd /Users/Mac/Downloads/llmMonitor
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Start The Proxy

```bash
cd /Users/Mac/Downloads/llmMonitor
python3 main.py serve \
  --listen 127.0.0.1 \
  --port 11435 \
  --upstream http://127.0.0.1:11434 \
  --log-dir ./logs
```

After startup, point any Ollama client that previously used `http://127.0.0.1:11434` to `http://127.0.0.1:11435`.

Dashboard URL:

```text
http://127.0.0.1:11435/dashboard
```

## Tracked API Paths

Tracked and logged:

- `POST /api/chat`
- `POST /api/generate`
- `POST /api/embed`

Passed through without monitoring records:

- `GET /api/tags`
- `GET /api/ps`
- `GET /api/version`
- Other native Ollama paths that are not part of the tracked set

## Log Format

Log files are split by day:

```text
logs/YYYY-MM-DD.jsonl
```

Each request is written as one JSON line with fields such as:

- `request_id`
- `timestamp`
- `path`
- `method`
- `model`
- `stream`
- `status_code`
- `success`
- `client_ip`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `total_ms`
- `load_ms`
- `prompt_eval_ms`
- `eval_ms`
- `tps`
- `done_reason`
- `error`

## CLI Queries

### Stats

```bash
python3 main.py stats --since 24h
python3 main.py stats --since 7d --model llama3.1:latest
```

### List

```bash
python3 main.py list --since 24h --limit 50
python3 main.py list --since 24h --model qwen3.5:35b-a3b-coding-nvfp4
```

### Live Tail

```bash
python3 main.py tail
python3 main.py tail --model llama3.1:latest
```

## Web Dashboard

After `serve` is running, open:

```text
http://127.0.0.1:11435/dashboard
```

The dashboard includes:

- A time range filter
- A request bar chart
- A primary request table
- Model filtering, keyword search, and CSV export
- A request detail dialog

The page refreshes every 30 seconds by default. If the previous refresh is still in progress, it waits instead of issuing overlapping requests.

## Metric Sources

Metrics come directly from Ollama response usage fields:

- `prompt_eval_count`
- `eval_count`
- `total_duration`
- `load_duration`
- `prompt_eval_duration`
- `eval_duration`
- `done_reason`

For streaming requests, the monitor extracts usage from the final response chunk where `done=true`.

## Examples

Non-streaming request:

```bash
curl http://127.0.0.1:11435/api/generate -d '{
  "model": "llama3.1:latest",
  "prompt": "Say hello in one sentence",
  "stream": false
}'
```

Streaming request:

```bash
curl http://127.0.0.1:11435/api/chat -d '{
  "model": "llama3.1:latest",
  "messages": [{"role": "user", "content": "Give me 3 short tips"}],
  "stream": true
}'
```

Then inspect the results:

```bash
python3 main.py stats --since 24h
python3 main.py list --since 24h
```
