# CNFuturesTradeSystem

事件驱动的国内期货量化交易系统。

当前阶段默认使用 `TTS` 作为测试交易后端，`CTP` 作为最终实盘后端。两者通过同一套 `gateway` 抽象和同一套集成测试骨架接入，项目整体完成后再切换到 `CTP` 为主。

## Branches

- `main`: 稳定核心交易框架
- `dev`: 策略运行时开发分支，按 TDD 推进

## Current Backend Model

- `TRADE_MODE=test` 时，网关优先走 `openctp_tts`
- `TRADE_MODE=live` 时，网关走 `openctp_ctp`
- 代码入口统一通过 [src/gateway/_ctp_backend.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/gateway/_ctp_backend.py)
- 测试默认以 `TTS` 为主，后续切换到 `CTP` 不应重写测试流程，只切换环境和期望

## Project Layout

```text
CNFuturesTradeSystem/
├── src/
│   ├── common/
│   │   ├── config.py
│   │   ├── contract.py
│   │   ├── exchange.py
│   │   ├── position.py
│   │   └── trading_time.py
│   ├── event_bus/
│   │   ├── event.py
│   │   ├── event_bus.py
│   │   └── logger.py
│   ├── gateway/
│   │   ├── _ctp_backend.py
│   │   ├── base.py
│   │   ├── md_gateway.py
│   │   └── td_gateway.py
│   ├── strategy/
│   │   ├── base.py
│   │   └── runtime.py
│   ├── messenger/                   ← IM 交互层
│   │   ├── base.py
│   │   ├── router.py
│   │   ├── context.py
│   │   ├── bridge.py
│   │   ├── webhook_server.py
│   │   ├── adapters/
│   │   └── commands/
│   ├── tests/
│   │   ├── common/
│   │   ├── event_bus/
│   │   ├── gateway/
│   │   │   ├── market/
│   │   │   └── trade/
│   │   ├── strategy/
│   │   └── test_main.py
│   └── main.py
├── docs/
├── flow/
├── logs/
├── .env.example
├── AGENTS.md
└── pytest.ini
```

## Core Modules

### `src/common`

- [config.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/config.py): 统一读取 `.env`，根据 `TRADE_MODE` 选择 `TTS_*` 或 `CTP_*`
- [contract.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/contract.py): 合约模型，保留 CTP 原生 `instrument_id`，不做解析
- [position.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/position.py): 单合约持仓，多空分列，支持 `update_from_ctp` 和 `apply_trade`
- [trading_time.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/trading_time.py): 连接时间窗口判断

### `src/event_bus`

- [event.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/event_bus/event.py): `Event` / `EventType`
- [event_bus.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/event_bus/event_bus.py): `EventBus` 发布订阅总线
- [logger.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/event_bus/logger.py): 日志事件落盘

### `src/gateway`

- [base.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/gateway/base.py): 网关基础状态
- [md_gateway.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/gateway/md_gateway.py): 行情网关
- [td_gateway.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/gateway/td_gateway.py): 交易网关
- [_ctp_backend.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/gateway/_ctp_backend.py): `TTS` / `CTP` 后端切换

### `src/strategy`

- [base.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/base.py): `BaseStrategy` 策略基类，直接管理合约、仓位、tick 缓存，提供下单辅助方法（`buy`/`sell`/`close_long`/`close_short`）
- [runtime.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/runtime.py): `StrategyRuntime` 策略注册/启动/停止、tick 按合约路由、order/trade 按 order_ref 路由、tag 批量控制

### `src/messenger`

> 设计阶段，尚未实现。架构细节见 [messenger_architecture.md](C:/Users/suoni/Desktop/CNFuturesTradeSystem/docs/messenger_architecture.md)。

- [base.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/messenger/base.py): `BotAdapter` 抽象基类 + `Message` 通用消息结构
- [router.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/messenger/router.py): `CommandRouter` 命令路由（正则匹配 → handler）
- [context.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/messenger/context.py): `BotContext` 持有 TdGateway / MdGateway / Runtime 引用
- [bridge.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/messenger/bridge.py): `MessengerBridge` 将 EventBus 事件推送到 IM 平台
- [webhook_server.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/messenger/webhook_server.py): 极简 FastAPI 实例（单路由 `/webhook/{platform}`）
- [adapters/](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/messenger/adapters/): 飞书 / 钉钉 / Telegram 平台适配器
- [commands/](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/messenger/commands/): 交易命令实现（`/position`, `/order`, `/account` 等）

## 策略模块状态

当前已落地：

- `Position` — 多空分列持仓模型，支持 CTP query 和成交回报更新
- `Contract` — CTP 原生合约元数据，不做解析
- `BaseStrategy` — 策略即执行体，内置 tick 缓存、仓位管理、下单辅助
- `StrategyRuntime` — 按策略注册管理，tick/instrument_id 路由，order/trade 按 order_ref 路由，tag 批量控制

尚未完成：

- Bar / BarBuilder / BarCache
- IndicatorService
- OrderManager

## Messenger 层状态

设计阶段，尚未实现。详见 [docs/messenger_architecture.md](C:/Users/suoni/Desktop/CNFuturesTradeSystem/docs/messenger_architecture.md)。

后续路线：

1. 抽象层 (base / router / context) — 与平台无关，可立即测试
2. Telegram 适配器 — API 最简单，最快验证闭环
3. 查询命令 (/position, /account) — 只读，安全
4. MessengerBridge — EventBus → IM 推送
5. 交易命令 (/order, /cancel)
6. webhook_server — 最小 FastAPI
7. 飞书 / 钉钉 适配器

## Test Layout

```text
src/tests/
├── common/
├── event_bus/
├── gateway/
│   ├── market/test_md_gateway.py
│   └── trade/
│       ├── _integration_support.py
│       ├── cleanup_positions.py
│       ├── test_live_trade.py
│       ├── test_td_gateway.py
│       └── test_tts_integration.py
├── strategy/
└── test_main.py
```

说明：

- [test_live_trade.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/tests/gateway/trade/test_live_trade.py): `TTS` / `CTP` 共用主流程集成测试
- [test_tts_integration.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/tests/gateway/trade/test_tts_integration.py): `TTS` 专属补充覆盖
- [_integration_support.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/tests/gateway/trade/_integration_support.py): 共享连接、事件等待、发单和清仓骨架

## Test Markers

- `gateway`: 所有 gateway 相关测试
- `live`: 会连接真实柜台环境。这里既可能是 `TTS`，也可能是 `CTP`
- `live_trade_window`: 会真实发单，要求在可交易时段运行

`pytest` 默认使用 `-m "not gateway"`，即默认不跑网关测试。

常用命令：

```powershell
python -m pytest
python -m pytest src/tests
python -m pytest -m "gateway and not live"
python -m pytest -m "gateway and live"
python -m pytest -m "gateway and live_trade_window"
```

## Environment

使用 `.env`，参考 [.env.example](C:/Users/suoni/Desktop/CNFuturesTradeSystem/.env.example)。

关键变量：

- `TRADE_MODE=test|live`
- `TTS_USER_ID`, `TTS_PASSWORD`, `TTS_BROKER_ID`, `TTS_TD_FRONT`, `TTS_MD_FRONT`
- `CTP_USER_ID`, `CTP_PASSWORD`, `CTP_BROKER_ID`, `CTP_TD_FRONT`, `CTP_MD_FRONT`, `CTP_APP_ID`, `CTP_AUTH_CODE`

默认建议：

- 日常开发与策略联调：`TRADE_MODE=test`
- 最终切到实盘：`TRADE_MODE=live`

## Dependencies

```powershell
pip install openctp-ctp openctp-tts python-dotenv pytest
```

Messenger 层额外依赖：

```powershell
pip install fastapi uvicorn httpx
```

- `fastapi` + `uvicorn`: webhook server（仅使用 IM 长轮询模式时不需要）
- `httpx`: 调用各 IM 平台的 SendMessage API

如果本地没有 `openctp_tts`，代码会回退到 `openctp_ctp`，但默认开发流程不建议依赖这个回退。

## Runtime Guard

[src/main.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/main.py) 中的 `RuntimeGuard` 负责：

- 仅在连接窗口内主动连接
- `CONNECTING` 卡住超时后重试
- 显式 `stop()` 后停止自动连接

连接窗口与职责边界见 [connection_runtime.md](C:/Users/suoni/Desktop/CNFuturesTradeSystem/docs/connection_runtime.md)。
