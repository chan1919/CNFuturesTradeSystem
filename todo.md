# CNFuturesTradeSystem — TODO

## Current Status

- [x] 项目基础框架（EventEngine + MdGateway + TdGateway）
- [x] EventType 事件枚举（涵盖连接、登录、行情、交易、查询、结算）
- [x] 合约编码转换（CTP ↔ 标准格式，含 CZCE 3/4 位兼容）
- [x] TdGateway 认证支持（ReqAuthenticate，AppID 字段）
- [x] MdGateway / TdGateway flow 文件统一存放 flow/ 目录
- [x] 实盘集成测试 test_live_trade.py（连接、认证、登录、查资金、查持仓、订阅行情、开平仓）
- [x] 自动清理测试残留仓位（teardown_method + cleanup_positions.py）
- [x] LogHandler 日志模块（按月目录、按日文件、分离 error 日志）
- [x] OnRspError 日志输出（print to stderr + SYSTEM 事件）
- [x] Gateway 回调 log_level 字段接入（log_level: info/warning/error/debug）
- [x] LogHandler 集成到实盘测试入口（当前 gateway 已带 log_level，测试中未初始化 Logger）
- [x] 认证超时机制 — authenticate() 调用后如果 OnRspAuthenticate 永不返回，自动回退到登录流程
- [x] 认证超时迟到响应保护 — OnRspAuthenticate 在超时回退后不重复调用 login()
- [x] 结算单确认 — QrySettlementInfo + SettlementInfoConfirm 流程
- [x] Trader 撤单测试 — cancel_order() 实盘测试已覆盖
- [x] RuntimeGuard 连接守护 — 时间窗口控制、CONNECTING 超时重试

## Pending

### 断线重连
- [ ] MdGateway 断线自动重连 + 恢复订阅
- [ ] TdGateway 断线自动重连 + 重走认证/登录

### Server 层 (server/ — FastAPI)
- [ ] server/models/ — 数据模型
- [ ] server/schemas/ — Pydantic 序列化
- [ ] server/api/ — REST API 路由
- [ ] server/ws/ — WebSocket 推送
- [ ] server/bridge/ — 桥接 trader 与 server

### 策略引擎 (strategy/)
- [ ] 规划中

### 数据库
- [ ] 规划中

### 前端
- [ ] 规划中

### 其他规划模块
- [ ] 风控模块
- [ ] 换月模块
- [ ] 套利模块