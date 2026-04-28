# CNFuturesTradeSystem — TODO

## Project Overview
期货内盘量化交易系统，基于 openctp-ctp 的事件驱动框架。

## Current Status

- [x] 项目基础框架（EventEngine + MdGateway + TdGateway）
- [x] EventType 事件枚举（涵盖连接、登录、行情、交易、查询）
- [x] 合约编码转换（CTP ↔ 标准格式，含 CZCE 3/4 位兼容）
- [x] TdGateway 认证支持（ReqAuthenticate，AppID 字段）
- [x] MdGateway / TdGateway flow 文件统一存放 flow/ 目录
- [x] 实盘集成测试 test_live_trade.py（连接、认证、登录、查资金、查持仓、订阅行情、开平仓）
- [x] 自动清理测试残留仓位（teardown_method + cleanup_positions.py）
- [x] LogHandler 日志模块（按月目录、按日文件、分离 error 日志）
- [x] OnRspError 日志输出（print to stderr + SYSTEM 事件）
- [x] Gateway 回调 log_level 字段接入（log_level: info/warning/error/debug）

## Pending

- [x] LogHandler 集成到实盘测试入口（当前 gateway 已带 log_level，测试中未初始化 Logger）
- [x] 认证超时机制 — `authenticate()` 调用后如果 `OnRspAuthenticate` 永不返回，自动回退到登录流程
- [x] 结算单确认 — QrySettlementInfo + SettlementInfoConfirm 流程
- [x] Trader 撤单测试 — `cancel_order()` 实盘测试已覆盖
- [ ] 断线重连 — OnFrontDisconnected 后的自动重连逻辑
- [ ] 策略 handler 层 — `trader/handler/` 目前为空
- [ ] server 层 — `server/` 目前全为 stub
