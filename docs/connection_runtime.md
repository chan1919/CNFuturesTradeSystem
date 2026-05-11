# Connection Runtime

## Purpose

This document defines the runtime rules for automatic gateway connection management.

The design is backend-agnostic:

- `MdGateway` / `TdGateway` may be backed by `TTS` or `CTP`
- runtime connection policy should not care which backend is active
- backend selection is handled by `TRADE_MODE` and `src/gateway/_ctp_backend.py`

## Responsibility Boundary

### Gateway Layer

`src/gateway/` is responsible for:

1. `connect()` / `close()` / `login()` / `authenticate()`
2. `subscribe()` / `send_order()` / `cancel_order()` / `query_*`
3. translating backend callbacks into `EventEngine` events
4. maintaining minimal runtime state such as `status`, `front_id`, `session_id`

`src/gateway/` is not responsible for:

1. trading-session window judgment
2. reconnection policy
3. pre-open connection timing
4. post-session reconnection suppression

### Runtime Layer

[src/main.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/main.py) owns:

1. deciding whether the current time is inside a connection window
2. deciding when disconnected gateways should be connected
3. deciding when stuck `CONNECTING` gateways should be retried
4. stopping automatic connection after explicit shutdown

## Connection Window

Allowed proactive connection window:

### Day Session

- start: `08:56`
- end: `15:01`

### Night Session

- start: `20:56`
- end: `02:45`

## Weekly Rules

### Monday Early Morning

- Monday `00:00 - 02:45` is not treated as an extension of the previous trading day
- automatic connect or reconnect should not happen in that window

### Weekday Day Session

- Monday to Friday `08:56 - 15:01` allows active connection attempts

### Monday To Thursday Night Session

- Monday to Thursday `20:56 - 23:59:59` allows active connection attempts
- the following day `00:00 - 02:45` also allows reconnect

### Friday Night Session

- Friday `20:56 - 23:59:59` allows active connection attempts
- Saturday `00:00 - 02:45` also allows reconnect

### Weekend

- after Saturday `02:45` until Monday `08:56`, runtime should not proactively connect
- if a gateway disconnects during that interval, runtime should not reconnect it

## Runtime Policy

### Pre-open Connect

- when entering a valid connection window, disconnected gateways may be connected proactively
- current guard behavior uses `08:56` and `20:56` as pre-open thresholds

### In-session Reconnect

- while inside a valid connection window, a disconnected gateway may be reconnected automatically
- if a gateway remains in `CONNECTING` for too long, runtime may retry connect

### Post-session Behavior

- runtime does not need to force-close healthy connections immediately after the session
- if a gateway disconnects outside the connection window, runtime should not reconnect until the next valid window

### Manual Stop

- after explicit `stop()`, runtime should not automatically reconnect gateways again

## Testing Strategy

Tests should stay split across three layers:

1. `trading_time` pure-function tests
2. `RuntimeGuard` behavior tests in [test_main.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/tests/test_main.py)
3. gateway tests that validate callbacks and requests, not runtime reconnection strategy
