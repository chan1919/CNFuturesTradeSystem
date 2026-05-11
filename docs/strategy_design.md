# Strategy Module Design

> Status: implemented core skeleton, still under TDD expansion

## Overview

The strategy module converts market events into trading actions.

Current design principles:

- `StrategyRuntime` manages strategy lifecycle and event integration
- each strategy owns multiple units
- units are the smallest execution elements
- both real contracts and synthetic contracts are supported
- strategy-level `on_order` and `on_trade` callbacks are first-class hooks

## Core Roles

### `StrategyRuntime`

Responsibilities:

- register and unregister strategies
- start and stop strategies
- subscribe unit market data through `MdGateway`
- route `ORDER` and `TRADE` events into both unit-level and strategy-level hooks

Current implementation: [runtime.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/runtime.py)

### `BaseStrategy`

Responsibilities:

- manage unit collection
- expose unit-level commands such as `enable`, `disable`, `update_params`, `restart`
- aggregate positions
- route ticks, positions, and account events to the right unit
- route component ticks into synthetic units through component mapping

Current implementation: [base.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/base.py)

### `AbstractUnit`

Responsibilities:

- store unit parameters
- own an independent `Position`
- define market subscription and tick-processing contract

### `RealUnit`

- one unit for one real exchange contract
- passes through matching ticks only

### `SyntheticUnit`

- subscribes component contracts
- caches component prices
- emits synthetic ticks after all component prices are available
- `last_price` on the routed synthetic tick is the synthetic price
- original leg information is preserved as `source_instrument_id` and `source_last_price`

Current implementation: [unit.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/strategy/unit.py)

## Event Flow

```text
MdGateway -> EventBus -> StrategyRuntime -> BaseStrategy._route_tick
                           -> direct unit match
                           -> synthetic component listeners
                           -> unit.on_tick(...)
                           -> strategy.on_tick(...)

TdGateway ORDER -> EventBus -> StrategyRuntime handler
                 -> unit.on_order(...)
                 -> strategy.on_order(...)

TdGateway TRADE -> EventBus -> StrategyRuntime handler
                 -> unit.on_trade(...)
                 -> strategy.on_trade(...)
```

## Current Data Model

### Position

[position.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/position.py)

- separate long and short sides
- `long_yd`, `long_today`, `long_avg_price`, `long_frozen`
- `short_yd`, `short_today`, `short_avg_price`, `short_frozen`
- `last_price`, `unrealized_pnl`, `realized_pnl`

### Contract

[contract.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/common/contract.py)

- preserves native CTP instrument code
- parses `product_id`, `year`, `month`, `year_month`

## Current Test Coverage

Strategy tests live in:

```text
src/tests/strategy/
├── test_base.py
├── test_runtime.py
├── test_position.py
├── test_synthetic.py
└── test_unit.py
```

Covered behaviors:

- position calculations
- unit lifecycle
- synthetic price calculation
- strategy event routing
- strategy-level order/trade callbacks
- strategy unregister cleanup

## Remaining Roadmap

Planned next steps:

1. Bar / BarBuilder / BarCache
2. IndicatorService
3. OrderManager
4. example strategies
5. full strategy-to-gateway integration coverage
