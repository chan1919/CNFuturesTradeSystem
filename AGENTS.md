# AGENTS.md

## 分支

- `main` — 稳定核心交易框架
- `dev` — 策略运行时开发分支，按 TDD 推进

## 当前后端策略

- 默认后端 `TTS`，通过 `TRADE_MODE=test`
- 生产环境后端 `CTP`，通过 `TRADE_MODE=live`
- `TTS` 和 `CTP` 视为同一 gateway 抽象后面的可互换后端
- 集成测试优先覆盖共享流程，避免为每个后端重复同样场景

## 测试标签

```text
gateway            所有 gateway 测试
live               会连接真实柜台环境的测试（TTS 或 CTP）
live_trade_window  会真实发单的测试，要求在可交易时段运行
```

`pytest` 默认使用 `-m "not gateway"`，即默认不跑网关测试。

```powershell
python -m pytest
python -m pytest
python -m pytest -m "gateway and not live"
python -m pytest -m "gateway and live"
python -m pytest -m "gateway and live_trade_window"
```

## 环境

- 使用 `.env`，不要用 `.env.local`
- `.env.example` 同时包含 `TTS_*` 和 `CTP_*` 变量
- `TRADE_MODE=test` 是默认开发模式
- `TRADE_MODE=live` 保留给最终的 CTP 实盘和真实集成验证
- `flow/` 和 `logs/*.log` 在 gitignore 中

## 依赖

```powershell
pip install openctp-ctp openctp-tts python-dotenv pytest
```

目前没有维护 `pyproject.toml`、`requirements.txt` 和独立的 lint/typecheck 工具链。

## 架构

事件驱动系统。[event_bus.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/event_bus/event_bus.py) 是发布/订阅核心。`src/gateway/` 中的网关封装了 `TTS` 或 `CTP` 原生 API，将回调转换为 `Event` 对象推送到总线。

## Messenger 层

`src/messenger/` 提供统一的 IM 接口层（飞书/钉钉/Telegram），替代构建独立前端。

- `BotAdapter` 是抽象基类，所有平台适配器实现它
- `CommandRouter` 通过正则表达式将文本命令映射到 handler
- `MessengerBridge` 订阅 EventBus，向所有已配置平台推送通知
- 各平台凭证存放于 `.env`

完整架构：[docs/messenger_architecture.md](C:/Users/suoni/Desktop/CNFuturesTradeSystem/docs/messenger_architecture.md)

实施顺序：base/router/context → Telegram 适配器 → 查询命令 → bridge → 交易命令 → webhook server → 飞书/钉钉

## Gateway 单元测试 Mock 模式

在导入 gateway 之前 mock 后端模块。

```python
with patch("gateway.md_gateway.mdapi") as mock_mdapi:
    mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
    from gateway.md_gateway import MdGateway
```

交易网关测试：

```python
with patch("gateway.td_gateway.tdapi") as mock_tdapi:
    ...
```

## 测试文件布局

```text
tests/
├── common/
├── event_bus/
├── gateway/
│   ├── market/test_md_gateway.py
│   └── trade/
│       ├── ...
```

含义：

- `test_live_trade.py` 是双后端共享的端到端集成测试套件
- `test_tts_integration.py` 是 TTS 专属补充覆盖
- `_integration_support.py` 是共享测试骨架，应复用而非重复连接或事件等待代码
- Messenger 测试在实现时放入 `test_messenger/` 目录

## TDD 工作流

`dev` 分支上的工作遵循 [README.md](C:/Users/suoni/Desktop/CNFuturesTradeSystem/README.md) 中的路线图。先写测试，再实现，最后用 `python -m pytest` 验证后再推进。
