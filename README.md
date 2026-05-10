# CNFuturesTradeSystem

期货内盘量化交易系统，基于 [openctp-ctp](https://github.com/openctp/openctp) 的事件驱动架构。

> **分支说明：** `main` 为稳定分支（核心交易框架），`dev` 为策略引擎开发分支。本文档标注了 dev 分支的增量开发规划。

## 项目架构

```
┌──────────────────────────────────────────┐
│             Frontend (规划中)              │
├──────────────────────────────────────────┤
│       Server / FastAPI (待实现)            │
├──────────────────────────────────────────┤
│         Strategy / 策略引擎 (dev 进行中)    │
├──────────────────────────────────────────┤
│   event_engine/ — 事件系统                 │
│   gateway/ — CTP 网关层                   │
│   common/ — 共享数据类型                   │
├──────────────────────────────────────────┤
│     main.py — RuntimeGuard 连接守护        │
└──────────────────────────────────────────┘
```

## 目录结构

```
CNFuturesTradeSystem/
├── common/               共享数据类型
│   ├── contract.py       Contract 合约模型（CTP 原味）
│   ├── exchange.py       交易所枚举
│   ├── position.py       Position 持仓数据类
│   └── trading_time.py   交易时间窗口
├── event_engine/         事件系统
│   ├── event.py          Event + EventType（纯 Enum）
│   ├── event_engine.py   EventEngine 事件引擎
│   └── logger.py         LogHandler 日志模块
├── gateway/              CTP 网关层
│   ├── base.py           GatewayStatus / BaseGateway
│   ├── md_gateway.py     行情网关
│   └── td_gateway.py     交易网关（认证/登录/下单/结算）
├── strategy/             策略引擎
│   ├── base.py           策略基类
│   ├── engine.py         策略引擎
│   ├── unit.py           执行单元 / 合成合约
│   ├── db/
│   └── examples/         示例策略
├── main.py               RuntimeGuard 连接守护
├── tests/                测试
│   ├── gateway/
│   │   ├── market/
│   │   │   └── test_md_gateway.py       行情网关单元测试（mock）
│   │   └── trade/
│   │       ├── test_td_gateway.py       交易网关单元测试（ mock）
│   │       ├── test_live_trade.py       实盘集成测试（live）
│   │       └── cleanup_positions.py     持仓清理工具
│   ├── trader/  ← 旧目录已废弃
│   ├── strategy/                        策略模块测试
│   └── test_main.py                     RuntimeGuard 测试
├── docs/
│   ├── strategy_design.md              策略模块设计文档
│   ├── connection_runtime.md           连接运行规则
│   └── contract_code_rules.md          合约编码规则（已废弃）
├── AGENTS.md              AI 助手指令
├── flow/                  CTP 流文件
├── logs/                  日志输出
├── .env.local             本地配置
└── pytest.ini             测试配置
```

## 核心模块

### common/ — 共享数据类型

| 模块 | 说明 |
|------|------|
| **合约** (`contract.py`) | `Contract` 合约模型，CTP 原生 `instrument_id`，通过 `from_ctp()` 工厂构造时自动解析 `product_id`、`year_month` 等字段 |
| **交易所** (`exchange.py`) | 上期所/大商所/郑商所/中金所/能源中心/广期所 枚举 |
| **持仓** (`position.py`) | `Position` 数据类，多空分列、计算属性 |
| **交易时间** (`trading_time.py`) | 日盘/夜盘连接窗口判断 |

### event_engine/ — 事件系统

| 模块 | 说明 |
|------|------|
| **事件类型** (`event.py`) | `EventType` 纯 `Enum`：连接、登录、行情、交易、查询、结算 |
| **事件引擎** (`event_engine.py`) | 基于 Queue 的发布/订阅引擎，支持异步线程 |
| **日志** (`logger.py`) | 按月分目录、按日分文件、错误日志分离 |

### gateway/ — CTP 网关层

| 模块 | 说明 |
|------|------|
| **网关基类** (`base.py`) | GatewayStatus 状态管理 |
| **行情网关** (`md_gateway.py`) | CTP MdApi 封装，行情订阅、断线事件 |
| **交易网关** (`td_gateway.py`) | CTP TraderApi 封装，含认证超时回退、结算确认、撤单 |

### main.py — RuntimeGuard

连接守护模块，功能：
- 按交易时间窗口（日盘 08:56–15:01、夜盘 20:56–02:45）控制网关连接
- CONNECTING 状态超时重试
- 显式关闭后停止自动连接

### 实现状态

### main 分支 （✅ 稳定）

- [x] EventEngine 事件引擎
- [x] MdGateway / TdGateway（含认证、结算确认、超时回退）
- [x] RuntimeGuard 连接守护
- [x] Contract 合约模型
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