# Ollama API Monitor

Language:

- English: [README.en.md](/Users/Mac/Downloads/llmMonitor/README.en.md)
- 中文: [README.zh-CN.md](/Users/Mac/Downloads/llmMonitor/README.zh-CN.md)

Ollama API Monitor is a local monitoring proxy for Ollama. It records request metadata into daily JSONL logs, exposes CLI views for stats and tailing, and serves a lightweight dashboard at `/dashboard`.

Ollama API Monitor 是一个面向 Ollama 的本地监控代理。它会将请求元数据写入按天切分的 JSONL 日志，提供命令行统计与实时 tail，并内置一个 `/dashboard` Web 仪表盘。

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 main.py serve --listen 127.0.0.1 --port 11435 --upstream http://127.0.0.1:11434
```

After startup, point your Ollama client to `http://127.0.0.1:11435`.

启动后，把原来访问 `http://127.0.0.1:11434` 的客户端改为访问 `http://127.0.0.1:11435`。
