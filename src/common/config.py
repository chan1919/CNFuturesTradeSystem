"""Central configuration module.

Loads .env via python-dotenv and exposes unified credential variables.
The active set (CTP_* / TTS_*) is chosen by the TRADE_MODE env variable.

Usage:
    from src.common.config import USER_ID, PASSWORD, BROKER_ID, TD_FRONT, MD_FRONT, \
        APP_ID, AUTH_CODE, is_live_mode, is_test_mode
"""
import os
from dotenv import load_dotenv

load_dotenv(".env")

TRADE_MODE = os.getenv("TRADE_MODE", "test")
_prefix = "CTP_" if TRADE_MODE == "live" else "TTS_"

USER_ID   = os.getenv(f"{_prefix}USER_ID", "")
PASSWORD  = os.getenv(f"{_prefix}PASSWORD", "")
BROKER_ID = os.getenv(f"{_prefix}BROKER_ID", "")
TD_FRONT  = os.getenv(f"{_prefix}TD_FRONT", "")
MD_FRONT  = os.getenv(f"{_prefix}MD_FRONT", "")
APP_ID    = os.getenv(f"{_prefix}APP_ID", "")
AUTH_CODE = os.getenv(f"{_prefix}AUTH_CODE", "")


def is_live_mode():
    return TRADE_MODE == "live"


def is_test_mode():
    return TRADE_MODE == "test"