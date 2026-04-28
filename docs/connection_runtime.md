# Connection Runtime

## Purpose

本文档定义 CTP 连接守护的运行规则，用于约束 `main.py` 的守护调度逻辑。

核心原则：

1. `MdGateway` / `TdGateway` 只负责 CTP 适配与交易接口调用。
2. 自动连接、自动重连、盘前预连接、盘后停止重连等策略由守护入口统一负责。
3. 守护逻辑第一版放在 `main.py`，但交易时间判断应保持为可测试的纯函数。

## Connection Window

以下时间窗口表示“允许主动建立连接，且断线后允许自动重连”的时间段：

### Day Session

- Start: `08:56`
- End: `15:01`

### Night Session

- Start: `20:56`
- End: `02:45`

## Weekly Rules

### Monday Early Morning

- 周一凌晨 `00:00 - 02:45` 不属于上一个交易日夜盘延续。
- 因此周一凌晨不应自动连接，也不应自动重连。

### Weekday Day Session

- 周一到周五白盘窗口 `08:56 - 15:01` 允许连接。

### Monday To Thursday Night Session

- 周一到周四晚间 `20:56 - 23:59:59` 允许连接。
- 对应次日凌晨 `00:00 - 02:45` 也允许连接。

### Friday Night Session

- 周五晚间 `20:56 - 23:59:59` 允许连接。
- 周六凌晨 `00:00 - 02:45` 也允许连接。

### Weekend

- 周六 `02:45` 之后至周一 `08:56` 前，不应主动连接。
- 此期间若已被动断开，不应自动重连。

## Runtime Policy

### Pre-open Connect

- 在连接窗口开始后，如果网关尚未连接，守护逻辑应主动尝试连接。
- 白盘采用 `08:56` 提前连接。
- 夜盘采用 `20:56` 提前连接。

### In-session Reconnect

- 在连接窗口内，如果网关被动断开，守护逻辑可以自动重连。
- `TdGateway` 重连后沿用原有认证/登录流程。
- `MdGateway` 重连登录成功后，应恢复此前订阅的合约列表。

### Post-session Behavior

- 盘后不要求守护逻辑主动断开已有连接。
- 但如果盘后已经被动断开，则不再自动重连，等待下一个连接窗口。

### Manual Close

- 如果系统是被显式关闭的，守护逻辑不应再次自动拉起网关。

## Responsibility Boundary

### Gateway Layer

`trader/gateway/` 只负责：

1. `connect()` / `close()` / `login()` / `authenticate()`
2. `subscribe()` / `send_order()` / `cancel_order()` / `query_*`
3. CTP SPI 回调转 `EventEngine` 事件
4. 维护最小运行状态，如 `status`、`front_id`、`session_id`

不负责：

1. 交易时段判断
2. 是否允许重连的策略决策
3. 盘前预连接
4. 盘后停止重连

### Main Runtime

`main.py` 负责：

1. 创建 `EventEngine`、`MdGateway`、`TdGateway`
2. 周期性检查当前时间是否处于连接窗口
3. 在允许连接时主动连接未连接网关
4. 在连接窗口内处理断线后的重连决策
5. 在非连接窗口内停止自动重连

## Testing Strategy

测试分三层：

1. `trading_time` 纯函数测试：验证交易时间边界。
2. `main.py` 守护逻辑测试：验证何时连接、何时不重连。
3. `gateway` 适配层测试：验证底层回调与请求，不再验证“自行自动重连”。
