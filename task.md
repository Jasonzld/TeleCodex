# TeleCodex 开发任务书（task.md）

## 1. 目标与范围

### 1.1 产品目标
在 Telegram 中提供可用的 Codex CLI 机器人桥接服务，实现：
- 用户通过 `/ask` 指令提交问题
- 系统异步调用 `codex` 执行任务
- 执行结果安全、稳定地回传到 Telegram

### 1.2 MVP 范围（P0）
- [x] Telegram Webhook 接入
- [x] `/ask` 命令解析与参数校验
- [x] Redis 队列异步处理（RQ）
- [x] Worker 调用 `codex` CLI（subprocess）
- [x] 回传结果分片（适配 Telegram 4096 字符限制）
- [x] 白名单权限控制（按 user_id / chat_id）
- [x] 执行超时控制与错误提示
- [x] 基础健康检查（`/healthz`）与结构化日志
- [x] Docker Compose 一键启动

### 1.3 非目标（Not In Scope）
- 后台管理 UI
- 复杂会话记忆 / 多轮对话
- 多模型路由（仅支持 codex）
- 完整运营报表系统

---

## 2. 里程碑计划

### M1：需求冻结与验收标准（0.5 天）
- 明确 P0 / P1 边界
- 确认验收清单（见第 7 节）

### M2：架构骨架搭建（1 天）
- FastAPI API 服务（webhook 接收）
- Redis + RQ 队列
- Worker 进程
- Docker Compose 编排
- 健康检查端点

### M3：核心链路实现（1 天）
- `/telegram/webhook` 接收 Telegram Update
- `/ask` 命令解析与入队
- Worker 消费任务并调用 `codex`
- 结果回传 Telegram（含分片）
- 白名单 / 超时 / 错误处理

### M4：测试与稳定性（1 天）
- 单元测试（ACL、分片、配置）
- 集成测试（webhook -> queue -> worker mock）
- 冒烟测试（端到端本地验证）

### M5：交付与 PR（0.5 天）
- 分支提交（feat/bootstrap-mvp）
- PR 描述（架构、测试结果、风险）
- README 与运行说明

---

## 3. 技术架构设计（软件架构师视角）

### 3.1 架构选型
| 组件 | 选型 | 理由 |
|------|------|------|
| API 框架 | FastAPI | 异步、高性能、类型安全 |
| 任务队列 | Redis + RQ | 轻量、部署简单、Python 原生 |
| 执行器 | subprocess | 调用 codex CLI，隔离性好 |
| 外部通道 | Telegram Bot API | httpx 异步请求 |
| 部署 | Docker Compose | 一键启动 API + Worker + Redis |

### 3.2 核心时序
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

### 3.3 设计原则
- Webhook 处理必须"快返回"（仅入队，不做耗时操作）
- Worker 异步执行，可独立扩容
- API 与 Worker 解耦，互不拖垮
- 单用户并发限制，全局并发上限

### 3.4 主要风险与措施
| 风险 | 措施 |
|------|------|
| codex 执行超时 | 任务超时（默认 90s）+ 失败文案 + 限流 |
| 重复投递导致重复回复 | 按 `update_id` 短期幂等去重 |
| 输出过长导致发送失败 | 按 4096 字符分片 + `[1/N]` 标记 |
| 命令注入 | 固定命令模板，禁止参数透传 |

---

## 4. 产品规划（产品经理视角）

### 4.1 用户价值
- 在 Telegram 中直接发 `/ask` 获得 AI 编程助手回答
- 无需登录额外平台，交互门槛低
- 异步执行 + 状态提示减少"卡住感"

### 4.2 功能优先级
**P0（本次必须）：**
- `/ask <问题>` — 提交并获取结果
- `/start` — 欢迎与使用说明
- `/help` — 帮助信息与示例
- 白名单权限控制
- 错误提示（超时 / 未授权 / 系统忙）
- 超时处理与分片回传

**P1（后续迭代）：**
- `/status` — 查看当前任务状态
- `/cancel` — 取消排队中的任务
- 简单会话上下文（按 chat_id）
- 更细粒度限流

### 4.3 关键指标（MVP）
- 指令成功率（成功回传 / 总请求）
- 首响时延（收到"已受理"提示）
- 完成时延（从发送到收到结果）
- 失败率（按错误类别拆分）

---

## 5. 用户体验设计（用户使用视角）

### 5.1 基本流程
1. 用户发送 `/start` → 收到欢迎消息与使用说明
2. 用户发送 `/ask 如何用 Python 读取 CSV？`
3. 收到 "✅ 已受理，正在处理..."
4. 收到结果（若过长则分段 `[1/N]`）
5. 若超时，收到 "⏰ 执行超时，请稍后重试"

### 5.2 体验要求
- 首条反馈快速（< 2s）
- 错误文案可理解，不暴露堆栈
- 长文本可读，按段分片不刷屏
- Markdown 格式在 Telegram 中正确渲染

### 5.3 失败提示模板
| 场景 | 提示 |
|------|------|
| 未授权 | "🚫 你没有使用权限，请联系管理员" |
| 空指令 | "请提供问题内容，例如：`/ask 如何排序列表？`" |
| 超时 | "⏰ 执行超时（90s），请缩短问题或稍后重试" |
| 系统错误 | "❌ 系统异常，请稍后重试" |
| 队列已满 | "⏳ 当前排队较多，请稍后再试" |

---

## 6. 任务拆解（工程执行清单）

- [ ] 1. 初始化项目结构与配置文件（pyproject.toml / .env.example / .gitignore）
- [ ] 2. 实现配置加载与环境变量校验（app/config.py）
- [ ] 3. 实现 FastAPI 入口与健康检查（app/main.py / app/api/health.py）
- [ ] 4. 实现 webhook 鉴权与 `/ask` 解析（app/api/webhook.py）
- [ ] 5. 实现 Redis 队列入队（app/worker/jobs.py）
- [ ] 6. 实现 Worker 消费与 `codex` 调用（app/worker/codex_exec.py / runner.py）
- [ ] 7. 实现 Telegram 消息回发封装（app/bot/telegram_client.py）
- [ ] 8. 实现输出分片（app/core/chunker.py）
- [ ] 9. 实现白名单权限控制（app/core/acl.py）
- [ ] 10. 编写 Docker Compose 与 Dockerfile
- [ ] 11. 编写单元测试（tests/unit/）
- [ ] 12. 编写集成测试（tests/integration/）
- [ ] 13. 补齐 README.md 与运行说明
- [ ] 14. 推送分支并创建 PR

---

## 7. 验收标准（Definition of Done）

1. `docker compose up` 可启动 API、Worker、Redis
2. 健康检查 `/healthz` 返回 `{"status": "ok"}`
3. Telegram 发 `/ask` 后可入队并返回结果
4. 超时时返回明确提示，不阻塞主服务
5. 超长输出自动分片发送（`[1/N]` 标记）
6. 白名单外用户无法调用
7. 单元测试与集成测试通过
8. 有完整 PR（包含测试结果与变更说明）

---

## 8. 安全与合规

- 白名单机制：仅允许指定 user_id / chat_id
- Webhook secret token 校验
- 不在日志中打印完整 Bot Token
- 固定命令模板，禁止用户直接拼接 shell 参数
- 对输入长度与频率做限制
- 错误信息脱敏，避免泄漏内部路径与命令

---

## 9. 回滚与应急策略

- 回滚方式：Git revert + 重新部署
- 降级策略：临时关闭 Worker，仅保留"系统维护中"自动回复
- 应急排障顺序：
  1. 检查 Redis 连接（`redis-cli ping`）
  2. 检查 Worker 存活（`rq info`）
  3. 检查 Telegram Webhook 状态（`getWebhookInfo`）
  4. 检查 `codex` 命令可执行性（`codex --version`）

---

## 10. 版本计划

| 版本 | 内容 |
|------|------|
| v0.1.0（本次） | P0 全量可用：/ask、白名单、分片、超时、Docker |
| v0.2.0 | /status、/cancel、更细粒度限流 |
| v0.3.0 | 会话上下文、任务审计、可观测性增强 |

---

## 11. 当前执行决定

已确认执行策略：
1. 先完成本地代码落地
2. 本地测试通过后再推送
3. 使用 `gh` 创建 PR 到 `Jasonzld/TeleCodex`
