import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "data/portfolio.db")
DART_API_KEY = os.getenv("DART_API_KEY", "")

# Static USD->KRW rate used to combine KR and US holdings into one portfolio total.
# Not live-updated; adjust in .env as the actual rate moves.
USD_KRW_RATE = float(os.getenv("USD_KRW_RATE", "1400"))
