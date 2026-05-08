# 策略模块设计文档

> 状态：设计阶段 · 未实现 · 2026-05-08

## 一、概述

策略模块负责将市场行情转化为交易信号并执行交易。核心设计思想：

- **策略类定义行为模板，合约单元是最小执行单元**
- 每个策略实例管理多个合约单元，各自持有独立的参数和持仓
- 支持真实合约和合成合约两种执行单元
- K线合成、指标引擎、订单管理等模块暂留接口，后续实现

## 二、架构层次

```
┌─────────────────────────────────────────────────────────┐
│                    StrategyEngine                         │
│  管理所有策略实例，桥接 EventEngine，生命周期控制            │
│  cmd_* / query_* 统一命令接口                              │
├─────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────┐  │
│  │             BaseStrategy (ABC)                      │  │
│  │  · on_init / on_start / on_stop / on_tick          │  │
│  │  · 事件按 instrument_id 路由到对应 AbstractUnit       │  │
│  │  · 聚合所有 unit 的持仓查询                           │  │
│  ├───────────────────────────────────────────────────┤  │
│  │  ┌─────────────────┐  ┌─────────────────┐        │  │
│  │  │    RealUnit      │  │  SyntheticUnit  │  ...   │  │
│  │  │  (真实合约单元)    │  │  (合成合约单元)   │        │  │
│  │  │                  │  │                  │        │  │
│  │  │  · Contract      │  │  · formula       │        │  │
│  │  │  · params dict   │  │  · components[]  │        │  │
│  │  │  · Position      │  │  · weights[]     │        │  │
│  │  │  · enabled flag  │  │  · price_cache   │        │  │
│  │  │                  │  │  · Position      │        │  │
│  │  │  [AbstractUnit]  │  │  [AbstractUnit]  │        │  │
│  │  └─────────────────┘  └─────────────────┘        │  │
│  └───────────────────────────────────────────────────┘  │
│                                                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │               Strategy B ...                        │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 职责划分

| 层次 | 职责 | 不知道的事 |
|---|---|---|
| `StrategyEngine` | 策略注册/启停，事件分发 | 具体策略逻辑 |
| `BaseStrategy` | 定义行为模板，管理 unit 集合 | 合约的价格计算 |
| `AbstractUnit` | 最小执行单元，参数+持仓 | 上层策略组合 |
| `Position` | 多空持仓数据和盈亏 | 如何产生持仓 |
| `Contract` | (已有) 合约代码和交易所 | 策略逻辑 |

## 三、核心类接口

### 3.1 AbstractUnit — 执行单元基类

```python
# strategy/unit.py

from abc import ABC, abstractmethod
from trader.common.contract import Contract

class AbstractUnit(ABC):
    """最小执行单元 - 抽象基类
    绑定：合约定义 + 策略参数 + 独立持仓
    """

    def __init__(self, instrument_id: str, contract: Contract, params: dict):
        self.instrument_id = instrument_id
        self.contract = contract
        self.params = params
        self.enabled = False
        self.position = Position(instrument_id=instrument_id)

    # ── 订阅行情 ──

    @abstractmethod
    def subscribe_market(self, md_gateway):
        """向 MdGateway 订阅合约行情"""

    # ── 行情输入 ──

    @abstractmethod
    def on_tick(self, tick: dict):
        """接收 Tick 行情事件"""

    # ── 开关 ──

    def enable(self):
        """开启本单元的行情处理和信号计算"""
        self.enabled = True

    def disable(self):
        """暂停行情处理和信号计算（不主动清仓）"""
        self.enabled = False

    # ── 参数修改与重启 ──

    def update_params(self, params: dict):
        """更新策略参数，会触发内部重置标记，但需调用 restart() 才生效"""
        self.params.update(params)

    def restart(self):
        """重新初始化计算状态（清空 K线缓存、指标状态等），使用新参数重新开始"""
        self._reset_state()
        # 重新订阅（某些 gateway 可能需要）
        self.enable()

    # ── 清仓 ──

    def clear_position(self):
        """对当前合约发送反向平仓单，清除所有持仓（多+空全平）"""

    # ── 内部 ──

    def _reset_state(self):
        """清空所有运行时计算状态（K线缓存、指标中间值等）
        子类可重写以添加自己的状态清理
        """
```

### 3.2 RealUnit — 真实合约单元

```python
class RealUnit(AbstractUnit):
    """真实合约执行单元（单个 CTP 合约）"""

    def subscribe_market(self, md_gateway):
        md_gateway.subscribe(self.contract.ctp_id)

    def on_tick(self, tick: dict):
        if not self.enabled:
            return
        if tick.get("instrument_id") != self.contract.symbol:
            return
        self._process_tick(tick)

    def _process_tick(self, tick: dict):
        """策略子类通过策略的 on_tick 回调接收数据
        RealUnit 只负责匹配和转发
        """
```

### 3.3 SyntheticUnit — 合成合约单元

```python
class SyntheticUnit(AbstractUnit):
    """合成合约执行单元
    由多个真实合约通过线性公式组合，公式格式: "code1*weight1 + code2*weight2"
    """

    def __init__(self, name: str,
                 components: list[Contract],
                 weights: list[float],
                 params: dict):
        super().__init__(instrument_id=name, contract=None, params=params)  # 合成合约无 Contract
        self.formula = " + ".join(f"{c.symbol}*{w}" for c, w in zip(components, weights))
        self.components = components
        self.weights = weights
        self._price_cache: dict[str, float] = {}

    @property
    def is_synthetic(self) -> bool:
        return True

    def subscribe_market(self, md_gateway):
        for comp in self.components:
            md_gateway.subscribe(comp.ctp_id)

    def on_tick(self, tick: dict):
        if not self.enabled:
            return

        # 更新价格缓存
        for comp in self.components:
            if tick.get("instrument_id") == comp.symbol:
                self._price_cache[comp.symbol] = tick["last_price"]
                break

        # 所有成分合约都有数据后计算合成价
        if len(self._price_cache) == len(self.components):
            synthetic_price = self._compute_price()
            tick["instrument_id"] = self.instrument_id
            tick["synthetic_price"] = synthetic_price
            self._process_tick(tick)

    def _compute_price(self) -> float:
        return sum(w * self._price_cache[c.symbol]
                   for w, c in zip(self.weights, self.components))

    def clear_position(self):
        """合成合约清仓：对所有有持仓的成分合约发送反向单"""
        for comp in self.components:
            # 委托给上层策略处理每个成分合约的清仓
            pass

    def _reset_state(self):
        super()._reset_state()
        self._price_cache.clear()
```

### 3.4 Position — 持仓

```python
# strategy/position.py

from dataclasses import dataclass, field

@dataclass
class Position:
    """单合约持仓模型 — 多空分列（匹配 CTP 双向持仓）"""

    instrument_id: str

    # ═══ 多头 ═══
    long_yd: int = 0              # 昨仓
    long_today: int = 0           # 今仓
    long_avg_price: float = 0.0   # 开仓均价
    long_frozen: int = 0          # 挂单冻结量

    # ═══ 空头 ═══
    short_yd: int = 0
    short_today: int = 0
    short_avg_price: float = 0.0
    short_frozen: int = 0

    # ═══ 动态字段（行情驱动更新） ═══
    last_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # ── 计算属性 ──

    @property
    def long_volume(self) -> int:
        return self.long_yd + self.long_today

    @property
    def short_volume(self) -> int:
        return self.short_yd + self.short_today

    @property
    def net(self) -> int:
        """净持仓：多 - 空 (正=净多, 负=净空, 0=无敞口)"""
        return self.long_volume - self.short_volume

    @property
    def is_flat(self) -> bool:
        return self.long_volume == 0 and self.short_volume == 0

    @property
    def is_long_only(self) -> bool:
        return self.long_volume > 0 and self.short_volume == 0

    @property
    def is_short_only(self) -> bool:
        return self.short_volume > 0 and self.long_volume == 0
```

### 3.5 BaseStrategy — 策略模板

```python
# strategy/base.py

from abc import ABC, abstractmethod

class StrategyStatus:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"


class BaseStrategy(ABC):
    """策略抽象基类

    子类实现 on_init / on_tick 定义信号逻辑。
    StrategyEngine 负责调用生命周期方法。
    """

    def __init__(self, name: str, engine: "StrategyEngine" = None):
        self.name = name
        self.status = StrategyStatus.STOPPED
        self.engine = engine
        self.units: dict[str, AbstractUnit] = {}

    # ── 合约单元管理 ──

    def add_unit(self, unit: AbstractUnit):
        self.units[unit.instrument_id] = unit

    def remove_unit(self, instrument_id: str):
        unit = self.units.pop(instrument_id, None)
        if unit:
            unit.disable()

    def get_unit(self, instrument_id: str) -> AbstractUnit | None:
        return self.units.get(instrument_id)

    def list_unit_ids(self) -> list[str]:
        return list(self.units.keys())

    def list_synthetic_units(self) -> list[SyntheticUnit]:
        return [u for u in self.units.values() if isinstance(u, SyntheticUnit)]

    # ── 单元级操作委托 ──

    def enable(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u: u.enable()

    def disable(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u: u.disable()

    def update_params(self, instrument_id: str, params: dict):
        u = self.get_unit(instrument_id)
        if u: u.update_params(params)

    def restart(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u: u.restart()

    def clear_position(self, instrument_id: str):
        u = self.get_unit(instrument_id)
        if u: u.clear_position()

    # ── 聚合查询 ──

    def get_all_positions(self) -> list[Position]:
        return [u.position for u in self.units.values()]

    def get_positions_for(self, product_id: str) -> list[Position]:
        """对指定产品代码（如 'rb'）的所有合约返回持仓"""
        return [u.position for u in self.units.values()
                if u.contract and u.contract.product_id == product_id]

    # ── 生命周期 (子类重写) ──

    @abstractmethod
    def on_init(self):
        """策略初始化，注册参数校验、设置初始状态"""

    def on_start(self):
        """策略启动，开启所有 unit"""
        for unit in self.units.values():
            unit.enable()

    def on_stop(self):
        """策略停止，关闭所有 unit"""
        for unit in self.units.values():
            unit.disable()
        self.status = StrategyStatus.STOPPED

    def on_tick(self, tick: dict, unit: AbstractUnit):
        """Tick 行情回调 — 子类在此实现核心交易逻辑"""

    # ── 内部 ──

    def _route_tick(self, event):
        """接收 EventEngine 的 TICK 事件，按 instrument_id 路由到对应 unit
        然后 unit 做二次过滤，最终调用 self.on_tick(tick, unit)
        """
        tick = event.data
        inst_id = tick.get("instrument_id", "")
        unit = self.get_unit(inst_id)
        if unit is None:
            return
        if not unit.enabled:
            return
        unit.on_tick(tick)        # 先让 unit 处理（合成合约计算等）
        self.on_tick(tick, unit)  # 再回调到策略子类
```

### 3.6 StrategyEngine — 策略引擎

```python
# strategy/engine.py

from trader.event import EventType

class StrategyEngine:
    """策略引擎：管理所有策略实例，桥接 EventEngine 和 Gateway"""

    def __init__(self, event_engine: "EventEngine",
                       td_gateway: "TdGateway",
                       md_gateway: "MdGateway"):
        self.event_engine = event_engine
        self.td_gateway = td_gateway
        self.md_gateway = md_gateway
        self.strategies: dict[str, BaseStrategy] = {}

    # ── 策略管理 ──

    def register(self, strategy: BaseStrategy):
        strategy.engine = self
        strategy.on_init()
        self.strategies[strategy.name] = strategy

    def unregister(self, name: str):
        s = self.strategies.pop(name, None)
        if s:
            s.on_stop()

    def get(self, name: str) -> BaseStrategy | None:
        return self.strategies.get(name)

    def list_names(self) -> list[str]:
        return list(self.strategies.keys())

    # ── 生命周期 ──

    def start(self, name: str):
        s = self.get(name)
        if not s or s.status != StrategyStatus.STOPPED:
            return
        s.status = StrategyStatus.STARTING
        # 注册事件监听
        self.event_engine.register(EventType.TICK, s._route_tick)
        self.event_engine.register(EventType.ORDER, self._make_on_order(s))
        self.event_engine.register(EventType.TRADE, self._make_on_trade(s))
        # 订阅行情
        for unit in s.units.values():
            unit.subscribe_market(self.md_gateway)
        s.on_start()

    def stop(self, name: str):
        s = self.get(name)
        if not s or s.status != StrategyStatus.RUNNING:
            return
        s.status = StrategyStatus.STOPPING
        s.on_stop()
        # 取消事件监听
        self.event_engine.unregister(EventType.TICK, s._route_tick)
        # ... unregister others

    def start_all(self):
        for name in self.list_names():
            self.start(name)

    def stop_all(self):
        for name in self.list_names():
            self.stop(name)

    # ── 内部 ──

    def _make_on_order(self, strategy):
        def handler(event):
            order = event.data
            unit = strategy.get_unit(order.get("instrument_id", ""))
            if unit: unit.on_order(event)
        return handler

    def _make_on_trade(self, strategy):
        def handler(event):
            trade = event.data
            unit = strategy.get_unit(trade.get("instrument_id", ""))
            if unit: unit.on_trade(event)
        return handler
```

## 四、数据流

```
MdGateway → EventEngine → StrategyEngine._on_tick
                                │
                    ┌───────────┴───────────┐
                    │   strategy._route_tick │
                    │   (by instrument_id)   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │    unit.on_tick(tick)  │
                    │  · RealUnit: 直传      │
                    │  · SyntheticUnit:      │
                    │    缓存→计算→合成tick   │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │ strategy.on_tick(     │
                    │   tick, unit)         │
                    │ 子类在此:              │
                    │  · K线聚合(未来)       │
                    │  · 指标计算(未来)       │
                    │  · 信号判断            │
                    │  · 调用 send_order     │
                    └───────────────────────┘
```

## 五、生命周期状态机

```
                    register()
                        │
                        ▼
                 ┌──────────────┐
                 │   STOPPED    │
                 └──────┬───────┘
                     start()
                        │
                        ▼
                 ┌──────────────┐
                 │  STARTING    │
                 │ subscribe    │
                 │ register evt │─────► on_start()
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │   RUNNING    │◄────  update_params() + restart()
                 └──────┬───────┘       (修改参数后重新计算)
                     stop()
                        │
                        ▼
                 ┌──────────────┐
                 │  STOPPING    │─────► on_stop()
                 └──────────────┘
```

### 单个 ContractUnit 的操作语义

| 操作 | 行为 |
|---|---|
| `enable()` | 恢复行情处理和信号计算 |
| `disable()` | 暂停信号计算，**不主动平仓** |
| `update_params(params)` | 更新参数字典，标记需要重启 |
| `restart()` | 清空所有计算状态（K线/指标），使用新参数从零开始 |
| `clear_position()` | 对当前合约发送反向平仓单，清除多+空持仓 |

## 六、文件规划

```
strategy/
├── __init__.py
├── base.py           # BaseStrategy ABC, StrategyStatus
├── engine.py         # StrategyEngine
├── unit.py           # AbstractUnit + RealUnit + SyntheticUnit
├── position.py       # Position dataclass
│
│   # ===== 预留钩子（暂不实现） =====
├── bar.py            # Bar dataclass: OHLCV + from_tick() + update()
├── bar_builder.py    # BarBuilder: tick → K线聚合
├── bar_cache.py      # BarCache: 内存滑动窗口缓存
├── indicator.py      # IndicatorEngine: 指标计算 + 外部DB基本面过滤
├── order_manager.py  # OrderManager: 下单/撤单/订单追踪/PnL
│
└── examples/         # 示例策略（后续实现）
    └── __init__.py

tests/strategy/
├── __init__.py
├── test_unit.py
├── test_position.py
├── test_base.py
├── test_engine.py
└── test_synthetic.py
```

## 七、后续实现路线

> 与本设计相关的 TDD 步骤

| Step | 内容 | 依赖 |
|---|---|---|
| Position | `Position` dataclass 及计算属性测试 | 无 |
| AbstractUnit | `AbstractUnit` + `RealUnit` 基本行为测试 | Position |
| SyntheticUnit | `SyntheticUnit` 合成价计算测试 | AbstractUnit, Contract |
| BaseStrategy | `BaseStrategy` unit 管理和事件路由测试 | AbstractUnit |
| StrategyEngine | `StrategyEngine` 注册/启停/事件分发测试 | BaseStrategy |
| Bar | (钩子) `Bar` 数据结构 | — |
| BarBuilder | (钩子) K线聚合 | Bar |
| Indicator | (钩子) 指标引擎 | Bar, BarCache |
| OrderManager | (钩子) 订单管理 | Position, TdGateway |

---

*最后更新：2026-05-08*