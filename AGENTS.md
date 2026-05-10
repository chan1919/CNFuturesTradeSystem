# AGENTS.md

## Branches
- `main` — stable core trading framework
- `dev` — active development, TDD-style strategy engine

## Test markers

```
gateway          all CTP gateway tests (unit mocks + live integration)
live             tests that connect to a real CTP server
live_trade_window  tests that place real orders (requires market open)
```

`pytest` defaults to `-m "not gateway"` — gateway tests are skipped.

```powershell
python -m pytest src/tests              # all non-gateway tests (src/tests is default via pytest.ini)
python -m pytest -m gateway             # all gateway tests
python -m pytest -m "gateway and not live"  # mock-only unit tests
python -m pytest -m "gateway and live_trade_window"  # real order placement
```

## Environment

- `.env.local` is **gitignored**, contains `CTP_USER_ID`, `CTP_PASSWORD`, `CTP_BROKER_ID`, `CTP_TD_FRONT`, `CTP_MD_FRONT`, `CTP_APP_ID`, `CTP_AUTH_CODE`
- Loaded via `python-dotenv` in live tests only
- `flow/` and `logs/*.log` are also gitignored

## Dependencies

```powershell
pip install openctp-ctp python-dotenv pytest
```

No `pyproject.toml`, no `requirements.txt`, no lint/typecheck toolchain. The only dev command is:

```powershell
python -m pytest
```

## Architecture

Event-driven system. `EventEngine` (`src/trader/engine.py`) is the central publish/subscribe bus. Gateways (`src/trader/gateway/`) wrap CTP native libs and convert callbacks into `Event` objects pushed into the engine.

## Mock pattern in tests

Gateway unit tests mock the CTP DLL modules **before** importing the gateway class:

```python
with patch("src.trader.gateway.md_gateway.mdapi") as mock_mdapi:
    mock_mdapi.CThostFtdcMdApi.CreateFtdcMdApi.return_value = md_api
    from src.trader.gateway.md_gateway import MdGateway
```

Same pattern applies for `td_gateway` → patch `src.trader.gateway.td_gateway.tdapi`.

## Test file layout

```
tests/
├── gateway/market/test_md_gateway.py    # MdGateway unit tests (mock)
├── gateway/trade/test_td_gateway.py     # TdGateway unit tests (mock)
├── gateway/trade/test_live_trade.py     # Real CTP integration (live)
├── gateway/trade/cleanup_positions.py   # Standalone position-closing script
├── trader/test_event_engine.py          # EventEngine unit tests
├── trader/test_contract.py              # Contract codec tests
├── trader/test_logger.py                # LogHandler tests
├── trader/test_trading_time.py          # Trading time window tests
└── test_main.py                         # RuntimeGuard tests
```

## TDD workflow

All `dev` branch work follows the TDD roadmap in `README.md`. Write tests first, then implement. Each step verifies with `python -m pytest` before moving on.