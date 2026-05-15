# 重构计划：消灭 Unit / ExecutionBody，收敛为 Contract + Strategy + Tag

## 当前问题

1. `AbstractUnit` / `RealUnit` / `SyntheticUnit` 分层复杂，框架引入太多概念
2. `SyntheticUnit` 把价差等组合行为做成框架概念，不应该
3. `instrument_id` 同时用作策略 unit id、合约标识、订阅 key，语义混在一起
4. 订单和成交按 `instrument_id` 路由，多 unit 共享合约时归属错误
5. 合约模型不完整，缺少 `from_ctp`、`year_month` 等 CTP 映射接口
6. 文档和代码不一致（文档写了 `Contract.from_ctp`，实际没有）

## 目标设计

只保留三个公开核心概念：

```text
Contract   — 真实 CTP 合约元数据
Strategy   — 既是交易模型，也是执行单元
Tag        — 策略实例的分组控制维度
```

### Contract

```python
@dataclass(frozen=True)
class Contract:
    instrument_id: str
    exchange: Exchange
    product_id: str
    multiplier: int
    price_tick: Decimal
    year: int | None = None
    month: int | None = None
    name: str = ""
    product_class: str = ""
    is_trading: bool = True

    @property
    def year_month(self) -> str: ...

    @classmethod
    def from_ctp(cls, instrument_id, exchange, multiplier, price_tick, ...) -> Contract: ...

    @classmethod
    def from_ctp_dict(cls, data: dict) -> Contract: ...
```

### Strategy

策略实例 = 执行单元。每个实例自己订阅合约、收 tick、维护仓位、下单、处理回报。

```python
class BaseStrategy:
    name: str
    tags: set[str]
    contracts: dict[str, Contract]
    positions: dict[str, Position]
    latest_ticks: dict[str, dict]
    orders: dict[str, dict]
    trades: dict[str, dict]
    enabled: bool

    def subscribed_instrument_ids(self) -> set[str]: ...
    def on_tick(self, tick: dict): ...
    def on_order(self, order: dict): ...
    def on_trade(self, trade: dict): ...
    def on_start(self): ...
    def on_stop(self): ...
    def enable(self): ...
    def disable(self): ...
```

单合约策略：

```python
class MacdStrategy(BaseStrategy):
    def on_tick(self, tick):
        price = tick["last_price"]
        signal = self.macd.update(price)
        if signal.cross_up:
            self.buy(self.contracts[tick["instrument_id"]], volume=1)
        if signal.cross_down:
            self.sell(self.contracts[tick["instrument_id"]], volume=1)
```

价差策略（多合约，不用合成合约概念）：

```python
class SpreadMacdStrategy(BaseStrategy):
    def on_tick(self, tick):
        self.latest_ticks[tick["instrument_id"]] = tick
        if not self.has_all_ticks("A2605", "B2701"):
            return
        spread = self.price("A2605") - self.price("B2701")
        signal = self.macd.update(spread)
        if signal.cross_up:
            self.buy("A2605", 1)
            self.sell("B2701", 1)
        if signal.cross_down:
            self.sell("A2605", 1)
            self.buy("B2701", 1)
```

价差 / 篮子 / 套利都是策略内部逻辑，框架不需要知道。

### Tag

批量控制和聚合查询维度：

```python
runtime.start_by_tag("macd")
runtime.stop_by_tag("arbitrage")
runtime.flatten_by_tag("trend")
runtime.positions_by_tag("black")
runtime.trades_by_tag("spread")
```

### StrategyRuntime

```text
- 注册/注销策略实例
- 按策略实例订阅合约行情（去重）
- tick → 路由到订阅该合约的策略
- send_order_for_strategy(strategy, ...)
- 维护 order_ref → strategy
- ORDER / TRADE 按 order_ref 路由
- 按 name / tag 控制、查询
```

### 订单和成交路由原则

tick：按 `instrument_id` 路由。

订单和成交：**不能按 `instrument_id`**，按 `order_ref` 路由。

```text
strategy.buy/sell
→ runtime.send_order_for_strategy(strategy, ...)
→ td_gateway.send_order(...)
→ 得到 CTP order_ref
→ runtime 记录 order_ref → strategy.name
→ ORDER / TRADE 回报
→ runtime 按 order_ref 找 strategy
→ strategy.on_order / strategy.on_trade
```

### 仓位原则

- `BaseStrategy.positions` 按合约区分，每个实例独立维护
- 成交回报按 order_ref 更新仓位
- CTP query position 作为账户级对账，不强行分摊给策略
- 如果一个合约只有一个策略实例在用，可同步 CTP position 给该策略

### 不要引入

- `AbstractUnit`
- `RealUnit`
- `SyntheticUnit`
- `ExecutionBody`
- `ContractManager`（runtime 内部 `_contracts` 即可）
- `Portfolio`（短期用 tag 替代）

---

## 实施步骤

### Step 1：重写 Contract

文件：`src/common/contract.py`

- 增加 `Contract.from_ctp(instrument_id, exchange, multiplier, price_tick, ...)`
- 增加 `Contract.from_ctp_dict(data: dict)`（从 CTP `OnRspQryInstrument` 构建）
- 增加 `year_month` 属性（4 位字符串，CZCE 正确处理 `YMM` 补 `2` 前缀）
- 保留 CTP 原生 `instrument_id`，不做格式转换
- 基础字段校验（month 1~12, product_id 非空等）
- 对齐 `docs/contract_code_rules.md` 和实际代码

### Step 2：更新 Position

文件：`src/common/position.py`

- 保留 `update_from_ctp()`
- 增加 `apply_trade(direction, offset, volume, price)` 方法
- 成交回报直接用 `apply_trade` 更新，不依赖 CTP query

### Step 3：重写 BaseStrategy

文件：`src/strategy/base.py`

- 删除 `units`、`_component_unit_map`、`list_synthetic_units`、`get_positions_for`
- 改为 `bodies` → 直接叫 `contracts` + `positions` + `latest_ticks`
- 策略实例自带 tick 缓存
- 提供 `price(instrument_id)` / `has_all_ticks(...)` 辅助方法
- `on_tick` 不再分 unit → unit 级别，策略自己决定怎么处理
- `on_order` / `on_trade` 直接接收原始 data dict
- 增加 `buy(contract_or_instrument_id, volume, ...)` / `sell(...)` 辅助方法（委托到 runtime）

### Step 4：重写 StrategyRuntime

文件：`src/strategy/runtime.py`

- 按策略实例注册
- 策略级别 `subscribe_market()` → 汇总所有 `subscribed_instrument_ids()` 去重后订阅
- tick 回调 → 遍历所有订阅该合约的策略实例
- order/trade 按 `order_ref` 路由
- 增加 `send_order_for_strategy(strategy, ...)`
- 增加 `start_by_tag(tag)` / `stop_by_tag(tag)` / `flatten_by_tag(tag)`
- 增加 `positions_by_tag(tag)` / `trades_by_tag(tag)` 聚合查询

### Step 5：重写网关回调（不需要大改）

文件：`src/gateway/td_gateway.py`

- `OnRtnOrder` / `OnRtnTrade` 保留现有 Event 格式
- 增加 `query_instruments()` 方法
- 增加 `OnRspQryInstrument` 回调，发布 `EventType.QRV_INSTRUMENT`
- runtime 收到后更新内部 `_contracts` 缓存

### Step 6：删除旧 Unit

- 删除 `src/strategy/unit.py`
- 删除 `src/tests/strategy/test_unit.py`
- 删除 `src/tests/strategy/test_synthetic.py`

### Step 7：重写测试

- `src/tests/common/test_contract.py` — 补齐 `from_ctp`、`from_ctp_dict`、`year_month`、校验
- `src/tests/strategy/test_base.py` — strategy 生命周期、tick 缓存、下单辅助、order/trade 路由
- `src/tests/strategy/test_runtime.py` — 注册、启动、停止、tag 控制、聚合查询
- `src/tests/strategy/test_strategies.py` — 单合约策略 + 价差策略的完整行为测试
- `src/tests/gateway/` — 保持现有 mock 测试，补充 `query_instruments` 测试

### Step 8：最终清理

- 修改 `docs/strategy_design.md` 对齐新设计
- 修改 `docs/contract_code_rules.md` 对齐新 API
- 修改 `README.md` 项目布局
- 确保 `AGENTS.md` 中的 TDD 工作流说明仍有效
- `python -m pytest` 全量通过

---

## 文件变更清单

### 新增

- `TODO.md`

### 修改

- `src/common/contract.py` — 增加 `from_ctp`、`year_month`、CTP 字段映射
- `src/common/position.py` — 增加 `apply_trade` 方法
- `src/strategy/base.py` — 重写为策略即执行体
- `src/strategy/runtime.py` — 重写为策略实例管理 + tag 控制
- `src/gateway/td_gateway.py` — 增加 CTP 合约查询
- `src/event_bus/event.py` — 确认 `QRV_INSTRUMENT` 存在
- `src/tests/common/test_contract.py` — 补齐测试
- `src/tests/strategy/test_base.py` — 重写
- `src/tests/strategy/test_runtime.py` — 重写
- `docs/strategy_design.md` — 对齐新设计
- `docs/contract_code_rules.md` — 对齐新 API
- `README.md` — 对齐项目布局

### 删除

- `src/strategy/unit.py`
- `src/tests/strategy/test_unit.py`
- `src/tests/strategy/test_synthetic.py`

---

## 实施顺序

1. `Contract`（含测试）
2. `Position` 新增 `apply_trade`（含测试）
3. `BaseStrategy`（含测试）
4. `StrategyRuntime`（含测试）
5. 删除旧 `Unit` 文件
6. `TdGateway.query_instruments`（含测试）
7. 补 full test pass
8. 更新文档
