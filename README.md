# CNFuturesTradeSystem

期货内盘量化交易系统，基于 [openctp-ctp](https://github.com/openctp/openctp) 的事件驱动架构。

## 项目架构

```
┌──────────────────────────────────────────┐
│             Frontend (规划中)              │
├──────────────────────────────────────────┤
│       Server / FastAPI (待实现)            │
│   api / bridge / models / schemas / ws    │
├──────────────────────────────────────────┤
│         Strategy / 策略引擎 (规划中)        │
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
├── strategy/             [规划中] 策略引擎
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

### trader/ — 核心交易框架

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

### main.py — RuntimeGuard

连接守护模块，功能：
- 按交易时间窗口（日盘 08:56–15:01、夜盘 20:56–02:45）控制网关连接
- CONNECTING 状态超时重试
- 显式关闭后停止自动连接

### server/ — FastAPI 后台服务（待实现）

- `api/` — REST API 路由
- `bridge/` — 桥接 trader 与 server
- `models/` — 数据模型
- `schemas/` — Pydantic 序列化
- `ws/` — WebSocket 行情/交易推送

### 规划中的模块

- **strategy/** — 策略引擎
- **风控模块**
- **换月模块**
- **套利模块**
- **数据库层**
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

完整任务清单见 [todo.md](todo.md)。已完成的核心功能：

- EventEngine 事件引擎
- MdGateway / TdGateway（含认证、结算确认、超时回退）
- RuntimeGuard 连接守护
- 合约编码转换（CTP ↔ 标准）
- LogHandler 日志模块
- 实盘集成测试（连接/认证/登录/行情/交易/结算）
- 撤单测试覆盖