# TeleCodex

Telegram Bot bridge for Codex CLI — 通过 Telegram 异步调用 Codex 并获取结果。

## 架构

```
Telegram --> [Webhook] --> FastAPI API
                            |
                            v
                      Redis Queue (RQ)
                            |
                            v
                      Worker (subprocess -> codex)
                            |
                            v
                      Telegram Bot API (回发结果)
```

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 Bot Token 和白名单 user_id
```

### 2. Docker Compose 启动

```bash
docker compose up --build
```

这会启动 3 个服务：
- **api** — FastAPI webhook 服务（端口 8080）
- **worker** — RQ worker（消费任务并调用 codex）
- **redis** — 消息队列

### 3. 设置 Webhook

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook" \
  -d "url=https://your-domain.com/telegram/webhook" \
  -d "secret_token=<YOUR_WEBHOOK_SECRET>"
```

### 4. 本地开发（不用 Docker）

```bash
pip install -e ".[dev]"

# 启动 API
uvicorn app.main:app --reload --port 8080

# 启动 Worker（另一个终端）
python -m app.worker.runner
```

## 命令

| 命令 | 说明 |
|------|------|
| `/start` | 欢迎信息 |
| `/help` | 使用帮助 |
| `/ask <问题>` | 向 Codex 提问 |

## 测试

```bash
pytest -v
```

## 项目结构

```
app/
├── main.py              # FastAPI 入口
├── config.py            # 环境变量配置
├── api/
│   ├── health.py        # /healthz /readyz
│   └── webhook.py       # /telegram/webhook
├── bot/
│   └── telegram_client.py  # Telegram 消息发送
├── core/
│   ├── acl.py           # 白名单权限
│   └── chunker.py       # 4096 字符分片
└── worker/
    ├── runner.py         # Worker 启动
    ├── jobs.py           # RQ 任务定义
    └── codex_exec.py     # codex 子进程调用
```

## License

MIT
