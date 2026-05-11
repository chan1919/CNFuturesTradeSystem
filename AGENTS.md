# AGENTS.md

## Branches

- `main` — stable core trading framework
- `dev` — active strategy-engine development branch

## Current Backend Policy

- Default backend is `TTS` via `TRADE_MODE=test`
- Final production backend is `CTP` via `TRADE_MODE=live`
- `TTS` and `CTP` are treated as backend substitutes behind the same gateway abstraction
- Integration tests should prefer shared workflow coverage and avoid duplicating the same scenario per backend

## Test Markers

```text
gateway            all gateway tests
live               tests that connect to a real backend session (TTS or CTP)
live_trade_window  tests that submit real orders and require a tradable session
```

`pytest` defaults to `-m "not gateway"` so gateway tests are skipped unless explicitly requested.

```powershell
python -m pytest
python -m pytest src/tests
python -m pytest -m "gateway and not live"
python -m pytest -m "gateway and live"
python -m pytest -m "gateway and live_trade_window"
```

## Environment

- Use `.env`, not `.env.local`
- `.env.example` documents both `TTS_*` and `CTP_*` variables
- `TRADE_MODE=test` is the default development mode
- `TRADE_MODE=live` is reserved for final CTP runtime and real integration validation
- `flow/` and `logs/*.log` are gitignored

## Dependencies

```powershell
pip install openctp-ctp openctp-tts python-dotenv pytest
```

No `pyproject.toml`, no `requirements.txt`, and no separate lint/typecheck toolchain are currently maintained.

## Architecture

Event-driven system. [event_bus.py](C:/Users/suoni/Desktop/CNFuturesTradeSystem/src/event_bus/event_bus.py) is the publish/subscribe core. Gateways in `src/gateway/` wrap either `TTS` or `CTP` native APIs and convert callbacks into `Event` objects pushed into the bus.

## Gateway Unit-Test Mock Pattern

Mock the backend module before importing the gateway class.

```python
with patch("gateway.md_gateway.mdapi") as mock_mdapi:
    mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
    from gateway.md_gateway import MdGateway
```

For trade gateway tests:

```python
with patch("gateway.td_gateway.tdapi") as mock_tdapi:
    ...
```

## Test File Layout

```text
src/tests/
├── gateway/market/test_md_gateway.py
├── gateway/trade/test_td_gateway.py
├── gateway/trade/test_live_trade.py
├── gateway/trade/test_tts_integration.py
├── gateway/trade/_integration_support.py
├── gateway/trade/cleanup_positions.py
├── strategy/test_*.py
└── test_main.py
```

Meaning:

- `test_live_trade.py` is the shared end-to-end integration suite for both backends
- `test_tts_integration.py` contains extra TTS-only coverage
- `_integration_support.py` is the shared harness and should be reused instead of duplicating connection or event-wait code

## TDD Workflow

All `dev` branch work follows the strategy roadmap in [README.md](C:/Users/suoni/Desktop/CNFuturesTradeSystem/README.md). Write tests first, then implement, and verify with `python -m pytest` before moving on.
