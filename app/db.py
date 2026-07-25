import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS stocks (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector_key TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('KR', 'US', 'JP'))
);

CREATE TABLE IF NOT EXISTS market_data (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL,
    market_cap REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS financials (
    ticker TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    revenue REAL,
    operating_income REAL,
    PRIMARY KEY (ticker, year, quarter)
);

CREATE TABLE IF NOT EXISTS commodity_prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS bond_prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL,
    PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS holdings (
    ticker TEXT PRIMARY KEY,
    quantity REAL NOT NULL,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('stock', 'commodity', 'bond'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('KOSPI', 'KOSDAQ', 'US', 'JP')),
    keyword TEXT
);

CREATE TABLE IF NOT EXISTS sector_stocks (
    sector_key TEXT NOT NULL,
    ticker TEXT NOT NULL,
    name TEXT NOT NULL,
    market TEXT NOT NULL CHECK (market IN ('KR', 'US', 'JP')),
    PRIMARY KEY (sector_key, ticker)
);

CREATE TABLE IF NOT EXISTS index_prices (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (symbol, date)
);
"""


# Tables whose CHECK constraint gained new allowed values (JP) after they may
# already have been created by an older version of this app. `CREATE TABLE IF
# NOT EXISTS` is a no-op on a table that already exists, so a pre-existing
# data/portfolio.db would keep rejecting JP rows forever without this migration.
_LEGACY_MIGRATIONS = {
    "stocks": """
        CREATE TABLE stocks (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector_key TEXT NOT NULL,
            market TEXT NOT NULL CHECK (market IN ('KR', 'US', 'JP'))
        )
    """,
    "watchlist": """
        CREATE TABLE watchlist (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            market TEXT NOT NULL CHECK (market IN ('KOSPI', 'KOSDAQ', 'US', 'JP')),
            keyword TEXT
        )
    """,
}


def _migrate_legacy_check_constraints(conn):
    for table, create_sql in _LEGACY_MIGRATIONS.items():
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if row is None or row[0] is None or "'JP'" in row[0]:
            continue  # table doesn't exist yet (SCHEMA below will create it), or already migrated
        conn.execute(f"ALTER TABLE {table} RENAME TO {table}_legacy")
        conn.execute(create_sql)
        conn.execute(f"INSERT INTO {table} SELECT * FROM {table}_legacy")
        conn.execute(f"DROP TABLE {table}_legacy")


# New (nullable) columns added to a table after it may already have been
# created by an older version of this app -- ALTER TABLE ADD COLUMN is safe
# to run on an existing table, unlike the CHECK-constraint case above which
# needs a full rebuild.
_LEGACY_COLUMN_ADDITIONS = {
    "index_prices": ["volume INTEGER"],
}


def _migrate_legacy_missing_columns(conn):
    for table, column_defs in _LEGACY_COLUMN_ADDITIONS.items():
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
        if row is None or row[0] is None:
            continue  # table doesn't exist yet (SCHEMA below will create it with the column already)
        existing_columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for column_def in column_defs:
            column_name = column_def.split()[0]
            if column_name not in existing_columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _migrate_legacy_check_constraints(conn)
        conn.executescript(SCHEMA)
        _migrate_legacy_missing_columns(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        pass  # get_conn() already runs SCHEMA; kept for existing call sites


def upsert_stock(conn, ticker, name, sector_key, market):
    conn.execute(
        """INSERT INTO stocks (ticker, name, sector_key, market)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET name=excluded.name,
               sector_key=excluded.sector_key, market=excluded.market""",
        (ticker, name, sector_key, market),
    )


def delete_stock(conn, ticker):
    conn.execute("DELETE FROM stocks WHERE ticker = ?", (ticker,))


def upsert_market_data(conn, ticker, date, close, market_cap, volume):
    conn.execute(
        """INSERT INTO market_data (ticker, date, close, market_cap, volume)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(ticker, date) DO UPDATE SET close=excluded.close,
               market_cap=excluded.market_cap, volume=excluded.volume""",
        (ticker, date, close, market_cap, volume),
    )


def upsert_financials(conn, ticker, year, quarter, revenue, operating_income):
    conn.execute(
        """INSERT INTO financials (ticker, year, quarter, revenue, operating_income)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(ticker, year, quarter) DO UPDATE SET revenue=excluded.revenue,
               operating_income=excluded.operating_income""",
        (ticker, year, quarter, revenue, operating_income),
    )


def upsert_price(conn, table, symbol, date, close):
    conn.execute(
        f"""INSERT INTO {table} (symbol, date, close) VALUES (?, ?, ?)
           ON CONFLICT(symbol, date) DO UPDATE SET close=excluded.close""",
        (symbol, date, close),
    )


def upsert_index_price(conn, symbol, date, close, volume):
    conn.execute(
        """INSERT INTO index_prices (symbol, date, close, volume) VALUES (?, ?, ?, ?)
           ON CONFLICT(symbol, date) DO UPDATE SET close=excluded.close, volume=excluded.volume""",
        (symbol, date, close, volume),
    )


def upsert_holding(conn, ticker, quantity, asset_class):
    conn.execute(
        """INSERT INTO holdings (ticker, quantity, asset_class)
           VALUES (?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET quantity=excluded.quantity,
               asset_class=excluded.asset_class""",
        (ticker, quantity, asset_class),
    )


def delete_holding(conn, ticker):
    conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker,))


def upsert_watchlist(conn, ticker, name, market, keyword=None):
    conn.execute(
        """INSERT INTO watchlist (ticker, name, market, keyword)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET name=excluded.name,
               market=excluded.market, keyword=excluded.keyword""",
        (ticker, name, market, keyword or None),
    )


def delete_watchlist(conn, ticker):
    conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))


def get_watchlist(conn):
    rows = conn.execute("SELECT ticker, name, market, keyword FROM watchlist ORDER BY ticker").fetchall()
    return [
        {"ticker": ticker, "name": name, "market": market, "keyword": keyword or name}
        for ticker, name, market, keyword in rows
    ]


def upsert_sector_stock(conn, sector_key, ticker, name, market):
    conn.execute(
        """INSERT INTO sector_stocks (sector_key, ticker, name, market)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(sector_key, ticker) DO UPDATE SET name=excluded.name, market=excluded.market""",
        (sector_key, ticker, name, market),
    )


def delete_sector_stock(conn, sector_key, ticker):
    conn.execute("DELETE FROM sector_stocks WHERE sector_key = ? AND ticker = ?", (sector_key, ticker))


def get_sector_stocks(conn, sector_key):
    rows = conn.execute(
        "SELECT ticker, name, market FROM sector_stocks WHERE sector_key = ? ORDER BY market, ticker",
        (sector_key,),
    ).fetchall()
    return [{"ticker": t, "name": n, "market": m} for t, n, m in rows]


def get_all_sector_stocks(conn):
    rows = conn.execute("SELECT sector_key, ticker, name, market FROM sector_stocks").fetchall()
    return [{"sector_key": sk, "ticker": t, "name": n, "market": m} for sk, t, n, m in rows]


def seed_sector_stocks_if_empty(conn, sectors):
    """Populates sector_stocks from the sectors.py defaults on first run only;
    once seeded, the table (editable via the UI) is the source of truth."""
    count = conn.execute("SELECT COUNT(*) FROM sector_stocks").fetchone()[0]
    if count > 0:
        return
    for sector in sectors:
        for ticker, name in sector["kr_stocks"]:
            upsert_sector_stock(conn, sector["key"], ticker, name, "KR")
        for ticker, name in sector["us_stocks"]:
            upsert_sector_stock(conn, sector["key"], ticker, name, "US")
        for ticker, name in sector["jp_stocks"]:
            upsert_sector_stock(conn, sector["key"], ticker, name, "JP")
