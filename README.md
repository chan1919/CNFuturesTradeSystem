# CNFuturesTradeSystem

期货内盘量化交易系统，基于 [openctp-ctp](https://github.com/openctp/openctp) 的事件驱动架构。

> **分支说明：** `main` 为稳定分支（核心交易框架），`dev` 为策略引擎开发分支。本文档标注了 dev 分支的增量开发规划。

## 项目架构

```
┌──────────────────────────────────────────┐
│             Frontend (规划中)              │
├──────────────────────────────────────────┤
│       Server / FastAPI (待实现)            │
│   api / bridge / models / schemas / ws    │
├──────────────────────────────────────────┤
│         Strategy / 策略引擎 (dev 进行中)    │
├──────────────────────────────────────────┤
│       trader/ — 核心交易框架               │
│   engine / event / gateway / common /      │
│   logger / handler                        │
├──────────────────────────────────────────┤
│     main.py — RuntimeGuard 连接守护        │
│     DB / 风控 / 换月 / 套利 (规划中)       │
└──────────────────────────────────────────┘
```

## 目录结构

```
CNFuturesTradeSystem/
├── trader/               核心交易框架
│   ├── engine.py         事件驱动引擎
│   ├── event.py          事件类型定义
│   ├── logger.py         日志模块
│   ├── common/
│   │   ├── contract.py   合约编码转换（CTP ↔ 标准）
│   │   ├── exchange.py   交易所枚举
│   │   └── trading_time.py  交易时间窗口
│   ├── gateway/
│   │   ├── base.py       GatewayStatus / BaseGateway
│   │   ├── md_gateway.py 行情网关
│   │   └── td_gateway.py 交易网关（认证/登录/下单/结算）
│   └── handler/          策略 Handler（待实现）
├── strategy/             [设计阶段] 策略引擎 — 设计文档见 docs/strategy_design.md
│   ├── base.py           策略基类（待实现）
│   ├── engine.py         策略引擎（待实现）
│   ├── unit.py           执行单元 / 合成合约（待实现）
│   ├── position.py       持仓模型（待实现）
│   ├── bar.py            Bar 数据结构（钩子）
│   ├── bar_builder.py    K线合成（钩子）
│   ├── bar_cache.py      内存K线缓存（钩子）
│   ├── indicator.py      指标引擎（钩子）
│   ├── order_manager.py  订单管理（钩子）
│   └── examples/         示例策略
├── server/               [待实现] FastAPI 后台
│   ├── api/
│   ├── bridge/
│   ├── models/
│   ├── schemas/
│   └── ws/
├── main.py               RuntimeGuard 连接守护
├── tests/                测试
│   ├── gateway/
│   │   ├── market/
│   │   │   └── test_md_gateway.py       行情网关单元测试（mock）
│   │   └── trade/
│   │       ├── test_td_gateway.py       交易网关单元测试（mock）
│   │       ├── test_live_trade.py       实盘集成测试（live）
│   │       └── cleanup_positions.py     持仓清理工具
│   ├── trader/
│   │   ├── test_event_engine.py         事件引擎测试
│   │   ├── test_contract.py             合约编码测试
│   │   ├── test_logger.py               日志模块测试
│   │   └── test_trading_time.py         交易时间测试
│   ├── strategy/                        ｜策略模块测试（规划）
│   └── test_main.py                     RuntimeGuard 测试
├── docs/
│   ├── strategy_design.md              策略模块设计文档
│   ├── connection_runtime.md           连接运行规则
│   └── contract_code_rules.md          合约编码规则
├── AGENTS.md              AI 助手指令
├── flow/                  CTP 流文件
├── logs/                  日志输出
├── .env.local             本地配置
└── pytest.ini             测试配置
```

## 核心模块

### trader/ — 核心交易框架 （✅ 已完成）

| 模块 | 说明 |
|------|------|
| **事件引擎** (`engine.py`) | 基于 Queue 的发布/订阅引擎，支持异步线程 |
| **事件类型** (`event.py`) | EventType 枚举：连接、登录、行情、交易、查询、结算 |
| **行情网关** (`gateway/md_gateway.py`) | CTP MdApi 封装，行情订阅、断线事件 |
| **交易网关** (`gateway/td_gateway.py`) | CTP TraderApi 封装，含认证超时回退、结算确认、撤单 |
| **网关基类** (`gateway/base.py`) | GatewayStatus 状态管理 |
| **合约编码** (`common/contract.py`) | CTP ↔ 标准格式互转，支持 CZCE 3/4 位兼容 |
| **交易所** (`common/exchange.py`) | 中金所/上期所/大商所/郑商所/能源中心/广期所 枚举 |
| **交易时间** (`common/trading_time.py`) | 日盘/夜盘连接窗口判断 |
| **日志** (`logger.py`) | 按月分目录、按日分文件、错误日志分离 |
| **策略 Handler** (`handler/`) | 策略开发框架（待实现） |

### main.py — RuntimeGuard （✅ 已完成）

连接守护模块，功能：
- 按交易时间窗口（日盘 08:56–15:01、夜盘 20:56–02:45）控制网关连接
- CONNECTING 状态超时重试
- 显式关闭后停止自动连接

---

## dev 分支开发路线图 — 策略引擎

> **开发原则：测试驱动开发 (TDD)，小步迭代。先写测试，再实现。**
> 完整设计见 [`docs/strategy_design.md`](docs/strategy_design.md)。

### Step 1 — `Position` 持仓模型

| 文件 | 内容 |
|------|------|
| `strategy/position.py` | `Position` dataclass：多空分列（long/short）、计算属性 |
| `tests/strategy/test_position.py` | 多空数据、net/is_flat/is_long_only 等计算属性 |

**验证：** `python -m pytest tests/strategy/ -v` 全绿

### Step 2 — `AbstractUnit` + `RealUnit` 执行单元

| 文件 | 内容 |
|------|------|
| `strategy/unit.py` | `AbstractUnit`(ABC) + `RealUnit`：订阅行情、开关、参数更新、重启、清仓 |
| `tests/strategy/test_unit.py` | enable/disable、update_params+restart、clear_position 行为 |

**依赖：** Step 1

### Step 3 — `SyntheticUnit` 合成合约单元

| 文件 | 内容 |
|------|------|
| `strategy/unit.py` | `SyntheticUnit(AbstractUnit)`：线性公式、成分合约价格缓存、合成价计算 |
| `tests/strategy/test_synthetic.py` | 多组件价格缓存、合成价计算、任一组件未就绪不触发 |

**依赖：** Step 2

### Step 4 — `BaseStrategy` 策略基类

| 文件 | 内容 |
|------|------|
| `strategy/base.py` | `BaseStrategy`(ABC)：unit 增删查、事件路由、聚合持仓查询 |
| `tests/strategy/test_base.py` | unit 管理、tick 路由到正确 unit、stop 关闭所有 unit |

**依赖：** Step 2

### Step 5 — `StrategyEngine` 策略引擎

| 文件 | 内容 |
|------|------|
| `strategy/engine.py` | 策略注册/启停、EventEngine 事件绑定/解绑、生命周期管理 |
| `tests/strategy/test_engine.py` | 注册→启动→tick分发→停止 全流程、多策略并行 |

**依赖：** Step 4

### Step 6 — `Bar` + `BarBuilder` + `BarCache` K线系统

| 文件 | 内容 |
|------|------|
| `strategy/bar.py` | `Bar` dataclass：OHLCV + `from_tick()` + `update()` |
| `strategy/bar_builder.py` | `BarBuilder`：tick → K线聚合 |
| `strategy/bar_cache.py` | `BarCache`：内存滑动窗口缓存 |
| `tests/strategy/test_bar.py` | Bar 创建/更新/OHLCV边界值 |
| `tests/strategy/test_bar_builder.py` | 1m/5m 聚合、跨周期触发 |
| `tests/strategy/test_bar_cache.py` | push/window/get/length/reset |

**依赖：** 无

### Step 7 — `IndicatorEngine` 指标引擎 + 外部数据

| 文件 | 内容 |
|------|------|
| `strategy/indicator.py` | 指标注册、`on_bar()` 增量计算、支持外部 DB 基本面数据过滤 |
| `tests/strategy/test_indicator.py` | SMA/EMA 计算、多指标并行、外部数据源接入 |

**依赖：** Step 6

### Step 8 — `OrderManager` 订单管理

| 文件 | 内容 |
|------|------|
| `strategy/order_manager.py` | 下单/撤单/订单追踪/PnL计算 |
| `tests/strategy/test_order_manager.py` | 开仓持仓正确性、平仓损益、订单状态跟踪 |

**依赖：** Step 1

### Step 9 — 示例策略 + 全链路集成

| 文件 | 内容 |
|------|------|
| `strategy/examples/ma_cross.py` | 双均线策略示例 |
| `tests/strategy/test_integration.py` | mock 全链路：tick → K线 → 指标 → 信号 → 模拟成交 |

**依赖：** Step 1-8

### Step 10 — 实盘集成测试（小仓位）

| 测试内容 |
|---------|
| 真实 CTP 环境：连接 → 策略接收 tick → K线 → 下单（1手）→ 平仓 → 验证持仓和信号 |

---

## 暂缓事项（不碰，待框架核心验证后再说）

| 模块 | 原因 |
|------|------|
| DB 持久化（sqlite3） | Step 5 策略引擎跑通后再加 |
| 风控模块 | 策略链路验证后再说 |
| 换月模块 | 远期待办 |
| 套利模块 | 远期待办 |
| `server/` FastAPI 后台 | 等策略链路跑通 |
| 断线重连 | 独立任务，不阻塞策略开发 |

---

### server/ — FastAPI 后台服务（待实现）

- `api/` — REST API 路由
- `bridge/` — 桥接 trader 与 server
- `models/` — 数据模型
- `schemas/` — Pydantic 序列化
- `ws/` — WebSocket 行情/交易推送

### 规划中的模块

- **风控模块**
- **换月模块**
- **套利模块**
- **前端**

## 快速开始

### 环境要求

- Python 3.10+
- openctp-ctp

### 配置

复制或编辑 `.env.local`，配置 BrokerID、UserID、Password、AppID、AuthCode 等。

### 运行测试

```powershell
python -m pytest                                        # 非 gateway 测试（默认跳过 CTP 相关）

python -m pytest -m gateway                             # 所有 gateway 测试（mock + 实盘）
python -m pytest -m "gateway and not live"              # 仅 gateway mock 单元测试
python -m pytest -m "gateway and live"                  # 仅实盘集成测试（需要 CTP 连接）
python -m pytest -m "gateway and live_trade_window"     # 仅实盘下单测试（需要开盘）
```

> 详细测试标记说明见 `AGENTS.md`。

## 实现状态

完整任务清单见 [todo.md](todo.md)。

### main 分支 （✅ 稳定）

- [x] EventEngine 事件引擎
- [x] MdGateway / TdGateway（含认证、结算确认、超时回退）
- [x] RuntimeGuard 连接守护
- [x] 合约编码转换（CTP ↔ 标准）
- [x] LogHandler 日志模块
- [x] 实盘集成测试（连接/认证/登录/行情/交易/结算）
- [x] 撤单测试覆盖

### dev 分支 （🔄 策略引擎 TDD 开发中）

- [ ] Step 1 — Position 持仓模型
- [ ] Step 2 — AbstractUnit + RealUnit 执行单元
- [ ] Step 3 — SyntheticUnit 合成合约单元
- [ ] Step 4 — BaseStrategy 策略基类
- [ ] Step 5 — StrategyEngine 策略引擎
- [ ] Step 6 — Bar + BarBuilder + BarCache K线系统
- [ ] Step 7 — IndicatorEngine 指标引擎
- [ ] Step 8 — OrderManager 订单管理
- [ ] Step 9 — 示例策略 + 全链路集成
- [ ] Step 10 — 实盘集成测试

---
*最后更新：2026-05-08 · dev 分支*