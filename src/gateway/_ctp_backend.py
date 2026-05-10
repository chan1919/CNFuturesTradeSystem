"""Backend resolver: re-exports mdapi and tdapi from either openctp_ctp (live)
or openctp_tts (test) based on the TRADE_MODE environment variable.

Usage:
    from src.gateway._ctp_backend import mdapi, tdapi

TRADE_MODE=test  (default) → from openctp_tts import mdapi, tdapi
TRADE_MODE=live             → from openctp_ctp import mdapi, tdapi
"""
import os
import sys

_mode = os.getenv("TRADE_MODE", "test")

if _mode == "live":
    from openctp_ctp import mdapi, tdapi
else:
    try:
        from openctp_tts import mdapi, tdapi
    except ImportError:
        print(
            "openctp_tts not installed; falling back to openctp_ctp. "
            "Run: pip install openctp-tts",
            file=sys.stderr,
        )
        from openctp_ctp import mdapi, tdapi