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
│   │   ├── runtime.py
│   │   ├── unit.py
│   │   └── examples/
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
- [contract.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/contract.py): 合约模型，保留 CTP 原生 `instrument_id`
- [position.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/position.py): 单合约持仓，多空分列
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

- [unit.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/unit.py): `AbstractUnit` / `RealUnit` / `SyntheticUnit`
- [base.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/base.py): 策略基类，负责 unit 管理与事件路由
- [runtime.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/runtime.py): `StrategyRuntime` 策略注册、启动、停止与事件接入

## Strategy Status

当前已经落地：

- `Position`
- `AbstractUnit` / `RealUnit` / `SyntheticUnit`
- `BaseStrategy`
- `StrategyRuntime`
- synthetic tick 经腿合约驱动
- strategy 级 `on_order` / `on_trade` 回调

尚未完成：

- Bar / BarBuilder / BarCache
- IndicatorService
- OrderManager
- 示例策略和全链路策略集成

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

如果本地没有 `openctp_tts`，代码会回退到 `openctp_ctp`，但默认开发流程不建议依赖这个回退。

## Runtime Guard

[src/main.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/main.py) 中的 `RuntimeGuard` 负责：

- 仅在连接窗口内主动连接
- `CONNECTING` 卡住超时后重试
- 显式 `stop()` 后停止自动连接

连接窗口与职责边界见 [connection_runtime.md](C:/Users/suoni/Desktop/CNFuturesTradeSystem/docs/connection_runtime.md)。
