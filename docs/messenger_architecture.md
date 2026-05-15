# Messenger 层架构设计

> 状态：设计文档，尚未实现

## 动机

通过即时通讯平台作为人机交互的主要界面，替代传统的前端（网页/移动端 Dashboard）。飞书、钉钉、企业微信和 Telegram 均作为可互换的后端接入统一的适配器抽象。

## 设计目标

1. **平台无关的命令路由** — 一套交易命令（`/position`、`/order`、`/cancel`、`/account` 等）在所有 IM 平台上一致工作
2. **可插拔适配器** — 接入新平台只需写一个适配器类，其余代码不变
3. **EventBus 集成** — 交易事件（成交、订单变更、断线）自动推送到所有已配置平台
4. **零前端** — 所有人机交互通过 IM 卡片、Markdown 和按钮回调完成

## 架构总览

```
                          ┌──────────────────────┐
                          │      EventBus         │
                          │   （系统核心总线）    │
                          └──────┬───────────────┘
                                 │ 注册事件监听
                          ┌──────▼───────────────┐
                          │   MessengerBridge     │
                          │  (EventBus → 推送)    │
                          └──────┬───────────────┘
                                 │
                 ┌───────────────┼───────────────────┐
                 │               │                   │
          ┌──────▼──────┐ ┌──────▼──────┐  ┌──────▼──────┐
          │  飞书        │ │  钉钉       │  │  Telegram   │
          │  Adapter    │ │  Adapter    │  │  Adapter    │
          └──────┬──────┘ └──────┬──────┘  └──────┬──────┘
                 │               │                 │
                 └───────┬───────┴─────────┬───────┘
                         │                 │
                  ┌──────▼──────┐  ┌──────▼──────┐
                  │ CommandRouter│  │ BotContext  │
                  │ (解析 → 执行) │  │ (系统引用)  │
                  └──────┬──────┘  └──────┬──────┘
                         │                 │
                  ┌──────▼─────────────────▼──────┐
                  │          交易系统              │
                  │  (TdGateway/MdGateway/Runtime) │
                  └───────────────────────────────┘
```

### 入站数据流（用户命令）

```
用户发送 "/position rb2410"
       │
       ▼
IM 平台 webhook POST → /webhook/{platform}
       │
       ▼
Adapter.verify_webhook()     ← 平台签名校验
Adapter.parse_webhook()      ← 平台负载 → Message
       │
       ▼
CommandRouter.route(msg, ctx)  ← 正则匹配命令
       │
       ▼
命令 handler                   ← 调用 ctx.td_gateway.query_positions()
       │
       ▼
Adapter.send_markdown()       ← 格式化并返回结果
```

### 出站数据流（系统通知）

```
TdGateway → EventBus 推送 ORDER / TRADE / POSITION / ACCOUNT 事件
       │
       ▼
MessengerBridge._on_trade(event)
       │
       ▼
格式化通知文本（如 "✅ rb2410 买入开仓 2手 @3800"）
       │
       ▼
遍历所有 (平台, chat_id) 配置:
    adapter.send_text(chat_id, 格式化文本)
```

## 模块布局

```
src/messenger/
├── __init__.py
├── base.py                  # BotAdapter 抽象基类, Message 数据类
├── router.py                # CommandRouter（正则命令分发）
├── context.py               # BotContext（持有 TdGateway/MdGateway/Runtime）
├── bridge.py                # MessengerBridge（EventBus → IM 推送）
├── webhook_server.py        # 极简 FastAPI 实例（单路由 /webhook/{platform}）
├── adapters/
│   ├── __init__.py
│   ├── feishu.py            # 飞书适配器
│   ├── dingtalk.py          # 钉钉适配器
│   └── telegram.py          # Telegram 适配器
└── commands/
    ├── __init__.py
    ├── query.py             # /position, /account, /status, /help
    ├── trading.py           # /order, /cancel
    └── system.py            # /start, /stop（策略生命周期管理）
```

## 核心组件

### `base.Message`

与平台解耦的通用消息中间表示。

```python
@dataclass
class Message:
    text: str                 # 原始消息文本
    user_id: str              # 平台用户标识
    chat_id: str              # 平台会话标识
    platform: str             # "feishu" | "dingtalk" | "telegram"
    raw: Any = None           # 原始平台负载（调试用）
```

### `base.BotAdapter`（抽象基类）

所有平台适配器实现此接口。

| 方法 | 用途 |
|---|---|
| `send_text(chat_id, text)` | 发送纯文本 |
| `send_markdown(chat_id, text)` | 发送格式化/Markdown 文本 |
| `send_card(chat_id, title, body, buttons)` | 发送交互卡片（富 UI） |
| `parse_webhook(body, headers)` | 解析 HTTP 回调 → `Message` 或 `None` |
| `verify_webhook(body, headers)` | 校验签名/令牌 |
| `webhook_response(msg, reply)` | 构建同步 HTTP 响应 |

```python
class BotAdapter(ABC):
    @abstractmethod
    def send_text(self, chat_id: str, text: str) -> bool: ...

    @abstractmethod
    def send_markdown(self, chat_id: str, text: str) -> bool: ...

    @abstractmethod
    def send_card(self, chat_id: str, title: str, body: str,
                  buttons: list[dict] | None = None) -> bool: ...

    @abstractmethod
    def parse_webhook(self, body: dict, headers: dict) -> Message | None: ...

    @abstractmethod
    def verify_webhook(self, body: dict, headers: dict) -> bool: ...

    @abstractmethod
    def webhook_response(self, msg: Message, reply: str) -> dict: ...
```

### `router.CommandRouter`

通过正则表达式将文本命令映射到处理函数。命令与平台无关——同一个 `/order` handler 在飞书、钉钉、Telegram 上同样工作。

```python
router = CommandRouter()

@router.register(
    r"/position\s*(\w*)",
    "/position [品种] — 查询持仓"
)
async def cmd_position(msg: Message, ctx: BotContext, instrument: str):
    ...
```

| 方法 | 用途 |
|---|---|
| `register(pattern, help_text)` | 装饰器：注册命令及其正则模式 |
| `route(msg, ctx)` | 匹配消息 → 执行 handler → 返回回复 |
| `set_fallback(handler)` | 未匹配命令的兜底处理 |
| `help_text()` | 生成所有已注册命令的帮助文本 |

### `context.BotContext`

命令 handler 访问交易系统的统一入口。

```python
@dataclass
class BotContext:
    td_gateway: TdGateway
    md_gateway: MdGateway
    runtime: StrategyRuntime
    event_bus: EventBus
```

### `bridge.MessengerBridge`

订阅 EventBus 事件，将格式化后的通知推送到所有已配置平台。

| 事件类型 | 通知内容 |
|---|---|
| `ORDER` | 订单状态变更（已提交/部分成交/已撤单/拒单） |
| `TRADE` | 成交通知（品种、方向、手数、价格） |
| `POSITION` | 持仓汇总（净多/净空、盈亏） |
| `ACCOUNT` | 账户快照（余额、可用、保证金、冻结） |
| `TD_DISCONNECTED` | 告警：交易网关断开 |
| `MD_DISCONNECTED` | 告警：行情网关断开 |

每种事件类型有独立的格式化器。格式字符串为包含品种、方向、手数、价格、盈亏的简单模板，不涉及任何 IM 特定的卡片 schema。

### `webhook_server`

极简 FastAPI 应用，只有一个动态路由：

```
POST /webhook/{platform}
```

处理逻辑：

1. 按平台名查找适配器
2. `adapter.verify_webhook(body, headers)` → 失败返回 403
3. `adapter.parse_webhook(body, headers)` → 无法解析返回 400
4. `router.route(message, bot_context)`
5. `adapter.webhook_response(message, reply_text)`

注意：Telegram 除 webhook 外也支持长轮询（`getUpdates`）。路由层共享，仅传递机制不同。

## 平台适配器设计

### 飞书适配器

- **认证**：app_id + app_secret → tenant_access_token（通过飞书 API）
- **校验**：Verify Token + 时间戳 + 签名头
- **入站**：飞书开放平台事件回调（事件订阅）
- **出站**：SendMessage API（文本/交互卡片/Markdown）
- **卡片支持**：飞书交互卡片，含确认/取消按钮

环境变量：
```
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_VERIFY_TOKEN=xxx
FEISHU_NOTIFY_CHATS=chat_xxx,chat_yyy
```

### 钉钉适配器

- **认证**：client_id + client_secret → access_token
- **校验**：时间戳 + 签名头
- **入站**：钉钉开放平台事件回调
- **出站**：SendMessage API（文本/Markdown/ActionCard）
- **卡片支持**：钉钉 ActionCard，含按钮

环境变量：
```
DINGTALK_CLIENT_ID=xxx
DINGTALK_CLIENT_SECRET=xxx
DINGTALK_NOTIFY_CHATS=xxx
```

### Telegram 适配器

- **认证**：BotFather 申请的 Bot Token（无需密钥管理）
- **校验**：无需签名——webhook URL 本身保密
- **入站**：Update 对象的 Message.text
- **出站**：`sendMessage` API（parse_mode=MarkdownV2）
- **卡片支持**：Inline Keyboard，用于简单确认/取消
- **替代方案**：长轮询 `getUpdates`（无需 webhook 服务）

环境变量：
```
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_NOTIFY_CHATS=123456
```

## 命令参考

| 命令 | 正则模式 | 说明 |
|---|---|---|
| `/position` | `/position\s*(\w*)` | 查询持仓（全部或指定品种） |
| `/account` | `/account\s*` | 查询账户余额和保证金 |
| `/order` | `/order (buy\|sell) (\w+) (\d+) (\d+(?:\.\d+)?)` | 提交限价单 |
| `/cancel` | `/cancel\s+(\S+)` | 按单号撤单 |
| `/start` | `/start\s+(\S+)` | 启动策略 |
| `/stop` | `/stop\s+(\S+)` | 停止策略 |
| `/status` | `/status\s*` | 系统健康状态（连接/运行中策略） |
| `/help` | `/help\s*` | 列出可用命令 |

## 配置

所有 Messenger 相关凭证存放在 `.env` 中，与已有的 `TTS_*` / `CTP_*` 变量并列。

```ini
# Messenger 平台（按需配置，不用的平台可留空）

# 飞书
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFY_TOKEN=
FEISHU_NOTIFY_CHATS=

# 钉钉
DINGTALK_CLIENT_ID=
DINGTALK_CLIENT_SECRET=
DINGTALK_NOTIFY_CHATS=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_NOTIFY_CHATS=
```

## 实施顺序

| 步骤 | 内容 | 优先原因 |
|---|---|---|
| 1 | `base.py` + `router.py` + `context.py` | 纯抽象层，无外部依赖，可立即单元测试 |
| 2 | Telegram 适配器 | API 最简单（无 OAuth SDK、无卡片复杂度），最快验证闭环 |
| 3 | `commands/query.py` | `/position` + `/account` 只读操作，可安全联调 |
| 4 | `bridge.py` | 将 EventBus 事件推送到 Telegram |
| 5 | `commands/trading.py` | `/order` + `/cancel`（真实交易动作） |
| 6 | `webhook_server.py` | 极简 FastAPI 服务器 |
| 7 | 飞书适配器 | 需注册飞书开放平台应用 |
| 8 | 钉钉适配器 | 需注册钉钉应用 |

## 测试策略

- **单元测试**：模拟 `BotAdapter` → 测试 `CommandRouter` 路由逻辑（使用伪造 `Message` 对象）
- **单元测试**：模拟 `BotAdapter.send_*` → 测试 `MessengerBridge` 格式化每种事件类型
- **适配器测试**：用各平台示例回调 payload 测试 `parse_webhook` / `verify_webhook`
- **集成测试**：Telegram 长轮询模式对接本地 TTS 后端（无需 webhook 服务器）

## 设计决策

### 为什么用正则路由而非 NLP？
交易命令有精确语法（`/order buy rb2410 2 3800`）。正则提供精确的参数捕获，无歧义、无误报。NLP 会引入延迟和幻觉风险。

### 为什么把 send_text/send_markdown/send_card 分为三个方法？
各平台渲染格式不同。飞书的 `send_markdown` 是 Lark 风格 Markdown；Telegram 是 MarkdownV2。抽象这三种原语覆盖了 95% 的通知场景，又不泄露平台特定的卡片 schema。

### 为什么 MessengerBridge 中同步发送？
EventBus handler 运行在总线的守护线程中——它们天然是同步的。改为异步需要线程协调。同步 HTTP 请求（短超时）在推送通知场景下简单且足够。

### 为什么 Telegram 不默认用 webhook？
Webhook 需要公网 HTTPS 端点。本地开发时 Telegram 的 `getUpdates` 轮询更方便。路由层共享，只有轮询循环与 webhook handler 的区别。
