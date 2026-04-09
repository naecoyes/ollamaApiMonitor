# Ollama API Monitor

一个轻量的本地 Ollama 监控代理。

它提供：

- 本地反向代理
- 按天切分的 JSONL 请求日志
- 命令行统计、列表和实时 tail
- 本地 Web 仪表盘

当前版本只支持 Ollama 原生接口，不提供 OpenAI 兼容层，也不会保存 prompt 或 response 内容。

## 项目结构

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

## 环境要求

- Python 3.9 及以上
- 已启动的本地 Ollama 服务，默认地址为 `http://127.0.0.1:11434`

## 安装

```bash
cd /Users/Mac/Downloads/llmMonitor
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## 启动代理

```bash
cd /Users/Mac/Downloads/llmMonitor
python3 main.py serve \
  --listen 127.0.0.1 \
  --port 11435 \
  --upstream http://127.0.0.1:11434 \
  --log-dir ./logs
```

启动后，把原来访问 `http://127.0.0.1:11434` 的 Ollama 客户端改为访问 `http://127.0.0.1:11435`。

仪表盘地址：

```text
http://127.0.0.1:11435/dashboard
```

## 支持的统计路径

会记录监控日志的路径：

- `POST /api/chat`
- `POST /api/generate`
- `POST /api/embed`

仅透传、不写监控记录的路径：

- `GET /api/tags`
- `GET /api/ps`
- `GET /api/version`
- 其他未纳入统计范围的原生 Ollama 路径

## 日志格式

日志文件按天切分：

```text
logs/YYYY-MM-DD.jsonl
```

每次请求写入一行 JSON，常见字段包括：

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

## 命令行查询

### 统计

```bash
python3 main.py stats --since 24h
python3 main.py stats --since 7d --model llama3.1:latest
```

### 列表

```bash
python3 main.py list --since 24h --limit 50
python3 main.py list --since 24h --model qwen3.5:35b-a3b-coding-nvfp4
```

### 实时 tail

```bash
python3 main.py tail
python3 main.py tail --model llama3.1:latest
```

## Web 仪表盘

启动 `serve` 后，浏览器打开：

```text
http://127.0.0.1:11435/dashboard
```

页面包含：

- 时间范围筛选
- 请求柱状图
- 主请求表格
- 模型筛选、关键词查找与 CSV 导出
- 请求详情弹窗

页面默认每 30 秒自动刷新一次；如果前一次请求还没完成，会等待完成后再发起下一次刷新，避免重叠请求。

## 指标来源

指标直接来自 Ollama 响应中的 usage 字段：

- `prompt_eval_count`
- `eval_count`
- `total_duration`
- `load_duration`
- `prompt_eval_duration`
- `eval_duration`
- `done_reason`

对于流式请求，监控器会从最终 `done=true` 的响应块中提取 usage。

## 示例

非流式请求：

```bash
curl http://127.0.0.1:11435/api/generate -d '{
  "model": "llama3.1:latest",
  "prompt": "Say hello in one sentence",
  "stream": false
}'
```

流式请求：

```bash
curl http://127.0.0.1:11435/api/chat -d '{
  "model": "llama3.1:latest",
  "messages": [{"role": "user", "content": "Give me 3 short tips"}],
  "stream": true
}'
```

然后查看结果：

```bash
python3 main.py stats --since 24h
python3 main.py list --since 24h
```
