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
├── strategy/             [dev 进行中] 策略引擎 — 见下方路线图
├── server/               [待实现] FastAPI 后台
│   ├── api/
│   ├── bridge/
│   ├── models/
│   ├── schemas/
│   └── ws/
├── main.py               RuntimeGuard 连接守护
├── tests/                测试
│   ├── trader/
│   │   ├── test_td_gateway.py      交易网关单元测试
│   │   ├── test_md_gateway.py      行情网关单元测试
│   │   ├── test_live_trade.py      实盘集成测试
│   │   ├── test_event_engine.py    事件引擎测试
│   │   ├── test_contract.py        合约编码测试
│   │   ├── test_logger.py          日志模块测试
│   │   └── test_trading_time.py    交易时间测试
│   ├── test_main.py                RuntimeGuard 测试
│   └── cleanup_positions.py        持仓清理工具
├── docs/
│   ├── connection_runtime.md       连接运行规则
│   └── contract_code_rules.md      合约编码规则
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

> **开发原则：测试驱动开发 (TDD)，小步迭代。每个 Step 写完代码 + 测试并通过后才进入下一步。**

### Step 1 — `Bar` 数据结构

| 文件 | 内容 |
|------|------|
| `strategy/bar.py` | `Bar` dataclass: OHLCV + `from_tick()` + `update()` |
| `tests/strategy/test_bar.py` | 从 tick 创建 Bar / 更新 Bar / OHLCV 边界值 |

**验证：** `python -m pytest tests/strategy/ -v` 全绿

### Step 2 — `BarBuilder` K线聚合

| 文件 | 内容 |
|------|------|
| `strategy/bar_builder.py` | `BarBuilder(interval_minutes)`: tick → K线聚合 |
| `tests/strategy/test_bar_builder.py` | 1分钟/5分钟聚合、跨周期触发、多标的并行 |

**依赖：** Step 1

### Step 3 — `IndicatorEngine` 指标引擎

| 文件 | 内容 |
|------|------|
| `strategy/indicator.py` | 指标注册 + `on_bar()` 增量更新（首版不做 dirty 全量重算） |
| `tests/strategy/test_indicator.py` | 注册 SMA / 验证计算结果 / 多指标并行 |

**依赖：** Step 1

### Step 4 — `StrategyContext` + DB 层

| 文件 | 内容 |
|------|------|
| `strategy/db/ddl.py` | 建表语句（signals / position_snapshots / trade_records） |
| `strategy/db/queries.py` | CRUD 函数 |
| `strategy/context.py` | `StrategyContext` sqlite3 封装 |
| `tests/strategy/test_context.py` | 建表 / 创建信号 / 仓位读写 / 成交记录 |

**依赖：** 无（独立模块）

### Step 5 — `BaseStrategy` 最小骨架

| 文件 | 内容 |
|------|------|
| `strategy/base.py` | ABC + `on_tick → BarBuilder → _on_bar → _check_signal` 管线 |
| `tests/strategy/test_base.py` | mock EventEngine+Gateway，验证 tick 到信号整条链路 |

**依赖：** Step 2 + Step 3 + Step 4

### Step 6 — `OrderManager`

| 文件 | 内容 |
|------|------|
| `strategy/order_manager.py` | 下单 / 持仓跟踪 / PnL 计算 |
| `tests/strategy/test_order_manager.py` | 开仓/平仓后持仓正确性、PnL 计算 |

**依赖：** Step 4

### Step 7 — `StrategyEngine`

| 文件 | 内容 |
|------|------|
| `strategy/engine.py` | 策略注册 / 生命周期 / cmd_ / query_ / 事件分派 |
| `tests/strategy/test_engine.py` | 启动/暂停/恢复/停止 / cmd/query 接口 |

**依赖：** Step 5 + Step 6

### Step 8 — 示例策略 + 全链路集成

| 文件 | 内容 |
|------|------|
| `strategy/examples/ma_cross.py` | 双均线策略（示例） |
| `tests/strategy/test_ma_cross_integration.py` | mock 全链路：tick → K线 → 指标 → 信号 → 模拟成交 |

**依赖：** Step 1-7 全部

### Step 9 — 实盘集成测试（小仓位）

| 测试内容 |
|---------|
| 真实 CTP 环境：连接 → 策略接收 tick → K线 → 下单（1手） → 平仓 → 验证 DB 信号记录 |

---

## 暂缓事项（不碰，待框架核心验证后再说）

| 模块 | 原因 |
|------|------|
| `FactorLoader` 因子加载 | Step 8 之前用不到 |
| `InstrumentConfig` 热修改 + dirty 标记 | 单策略稳定后再加 |
| IndicatorEngine dirty / 全量重算 | 增量模式验证后再做 |
| `server/` FastAPI 后台 | 等策略链路跑通 |
| 断线重连 | 独立任务，不阻塞策略开发 |
| 风控 / 换月 / 套利 | 远期待办 |

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

```bash
# 全部测试（含单元测试 + 实盘集成）
python -m pytest

# 仅运行单元测试（跳过实盘）
python -m pytest -m "not live"

# 跳过需要交易时段的测试
python -m pytest -m "not live_trade_window"
```

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

- [ ] Step 1 — Bar 数据结构
- [ ] Step 2 — BarBuilder K线聚合
- [ ] Step 3 — IndicatorEngine 指标引擎
- [ ] Step 4 — StrategyContext + DB 层
- [ ] Step 5 — BaseStrategy 最小骨架
- [ ] Step 6 — OrderManager
- [ ] Step 7 — StrategyEngine
- [ ] Step 8 — 示例策略 + 全链路集成
- [ ] Step 9 — 实盘集成测试

---
*最后更新：2026-04-29 · dev 分支*