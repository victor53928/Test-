import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _get_secret(key: str, default: str = "") -> str:
    """Prefer Streamlit secrets (used on Streamlit Community Cloud); fall back to
    the environment / .env (local dev), so the same code works in both places."""
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


DB_PATH = BASE_DIR / _get_secret("DB_PATH", "data/portfolio.db")
DART_API_KEY = _get_secret("DART_API_KEY", "")

# Static USD->KRW / JPY->KRW rates used to combine KR/US/JP holdings into one
# portfolio total. Not live-updated; adjust in .env (or Streamlit Cloud secrets)
# as the actual rate moves. JPY_KRW_RATE is per 1 JPY (not per 100 JPY).
USD_KRW_RATE = float(_get_secret("USD_KRW_RATE", "1400"))
JPY_KRW_RATE = float(_get_secret("JPY_KRW_RATE", "9.3"))

# Naver Search API (news) - free, register at https://developers.naver.com/apps
NAVER_CLIENT_ID = _get_secret("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = _get_secret("NAVER_CLIENT_SECRET", "")
