# 策略架构设计

## 核心概念

只保留三个公开核心概念：

```
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
    multiplier: int
    tick_size: float
```

CTP 原生 `instrument_id` 不做任何格式转换或解析。直接使用 CTP 回调中的字段。

### Account

`Account` 是仓位管理中心，持有所有合约的 `Position`，由 `StrategyRuntime` 统一管理。

```python
class Account:
    positions: dict[str, Position]          # instrument_id → Position
    get_or_create(contract) -> Position
    apply_trade(contract, direction, offset, volume, price)
    update_from_ctp(instrument_id, contract, posi_direction, yd, today, frozen, avg_price)
```

数据流：

```
CTP OnRtnTrade → Runtime (归一化枚举) → Account.apply_trade()    ← 成交回报增量更新
CTP OnRspQryInvestorPosition → Account.update_from_ctp()        ← 查询全量对账
CTP OnRtnDepthMarketData → Runtime → Account 的 Position 更新 last_price  ← tick 更新最新价
```

### Position

```python
@dataclass
class Position:
    contract: Contract

    long_yd: int
    long_today: int
    long_avg_price: float
    long_frozen: int

    short_yd: int
    short_today: int
    short_avg_price: float
    short_frozen: int

    last_price: float
    realized_pnl: float

    @property
    def unrealized_pnl(self) -> float     # 实时计算: (多-均价)+(均价-空) × 乘数 × 手数

    def apply_trade(direction, offset, volume, price): ...
    def update_last_price(price): ...
```

Position 是一个纯策略模型：
- 不知道 CTP 的存在（CTP 枚举在 Runtime 层归一化）
- 通过 `contract.multiplier` 计算 P&L
- `unrealized_pnl` 是只读 property，按需计算
- `realized_pnl` 在平仓时累加

### Strategy

策略实例 = 执行单元。每个实例自己订阅合约、收 tick、下单、处理回报。**不再管理仓位**，通过 `runtime.account` 查询。

```python
class BaseStrategy:
    name: str
    tags: set[str]
    contracts: dict[str, Contract]
    latest_ticks: dict[str, dict]
    orders: dict[str, dict]
    trades: dict[str, dict]
    enabled: bool

    def subscribed_instrument_ids(self) -> set[str]: ...
    def add_contract(self, contract: Contract): ...
    def price(self, instrument_id) -> float | None: ...
    def has_all_ticks(self, *instrument_ids) -> bool: ...
    def buy(self, instrument_id, volume, price=None): ...
    def sell(self, instrument_id, volume, price=None): ...
    def close_long(self, instrument_id, volume, price=None): ...
    def close_short(self, instrument_id, volume, price=None): ...
    def on_tick(self, tick: dict): ...
    def on_order(self, order: dict): ...
    def on_trade(self, trade: dict): ...
    def on_init(self): ...
    def on_start(self): ...
    def on_stop(self): ...
```

单合约策略：

```python
class MacdStrategy(BaseStrategy):
    def on_init(self):
        self.add_contract(rb2510_contract)

    def on_tick(self, tick):
        price = tick["last_price"]
        signal = self.macd.update(price)
        if signal.cross_up:
            self.buy("rb2510", 1)
        if signal.cross_down:
            self.sell("rb2510", 1)
```

价差策略（多合约，不用合成合约概念）：

```python
class SpreadMacdStrategy(BaseStrategy):
    def on_init(self):
        self.add_contract(a2605_contract)
        self.add_contract(b2701_contract)

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
runtime.positions_by_tag("trend")
runtime.trades_by_tag("spread")
```

## StrategyRuntime

```
- 注册/注销策略实例
- 持有 Account（仓位管理中心）
- 按策略实例订阅合约行情（去重）
- tick → 更新 Account 的 Position.last_price + 路由到策略
- send_order_for_strategy(strategy, ...)
- 维护 order_ref → strategy
- ORDER / TRADE 按 order_ref 路由，CTP 枚举归一化后更新 Account
- 按 name / tag 控制、查询
```

## 订单和成交路由原则

tick：按 `instrument_id` 路由。

订单和成交：**不能按 `instrument_id`**，按 `order_ref` 路由。

```
strategy.buy/sell
→ runtime.send_order_for_strategy(strategy, ...)
→ td_gateway.send_order(...)
→ 得到 CTP order_ref
→ runtime 记录 order_ref → strategy.name
→ ORDER / TRADE 回报
→ runtime 按 order_ref 找 strategy
→ strategy.on_order / strategy.on_trade
```

## 仓位原则

- `Account` 是唯一的仓位管理中心，由 `StrategyRuntime` 持有
- `Account` 内部的 `Position` 持有 `Contract` 引用，通过 `contract.multiplier` 计算 P&L
- `Position.unrealized_pnl` 是只读 property，实时计算，不缓存
- `Position` 是纯策略模型，不知道 CTP 的存在（CTP 枚举在 Runtime 层归一化）
- 成交回报按 `order_ref` 路由，`Runtime._on_trade()` 归一化枚举后调用 `Account.apply_trade()`
- CTP query position 通过 `Account.update_from_ctp()` 入 Account，作为对账手段
- 策略通过 `runtime.account.positions` 查询实时仓位，不自行管理仓位

## 不要引入

- `AbstractUnit`
- `RealUnit`
- `SyntheticUnit`
- `ExecutionBody`
- `ContractManager`（runtime 内部 `_contracts` 即可）
