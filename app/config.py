import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / os.getenv("DB_PATH", "data/portfolio.db")
DART_API_KEY = os.getenv("DART_API_KEY", "")
