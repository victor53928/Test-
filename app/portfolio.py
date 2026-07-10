"""Portfolio valuation and rebalancing logic.

Target allocation: stock 50% / commodity 30% / bond 20%.

KR holdings are priced in KRW; US stocks, commodity futures and TLT are priced
in USD. Everything is converted to KRW (via config.USD_KRW_RATE) before being
combined, otherwise weights would be meaningless.
"""

from app.config import USD_KRW_RATE

TARGET_WEIGHTS = {"stock": 0.50, "commodity": 0.30, "bond": 0.20}
REBALANCE_TOLERANCE = 0.05  # 5 percentage points

_PRICE_TABLE_BY_ASSET_CLASS = {
    "stock": ("market_data", "ticker"),
    "commodity": ("commodity_prices", "symbol"),
    "bond": ("bond_prices", "symbol"),
}

# Bond symbols priced in KRW; anything else in BONDS (TLT, ^TNX) defaults to USD.
_KRW_BOND_SYMBOLS = {"148070.KS"}


def get_latest_price(conn, asset_class: str, ticker: str):
    table, column = _PRICE_TABLE_BY_ASSET_CLASS[asset_class]
    row = conn.execute(
        f"SELECT close FROM {table} WHERE {column} = ? ORDER BY date DESC LIMIT 1",
        (ticker,),
    ).fetchone()
    return row[0] if row else None


def get_currency(conn, asset_class: str, ticker: str) -> str:
    if asset_class == "stock":
        row = conn.execute("SELECT market FROM stocks WHERE ticker = ?", (ticker,)).fetchone()
        market = row[0] if row else "KR"
        return "KRW" if market == "KR" else "USD"
    if asset_class == "commodity":
        return "USD"
    if asset_class == "bond":
        return "KRW" if ticker in _KRW_BOND_SYMBOLS else "USD"
    raise ValueError(asset_class)


def to_krw(amount: float, currency: str) -> float:
    return amount if currency == "KRW" else amount * USD_KRW_RATE


def get_holdings_with_value(conn):
    """Returns a list of dicts: ticker, quantity, asset_class, currency, price,
    market_value (native currency), market_value_krw."""
    holdings = conn.execute("SELECT ticker, quantity, asset_class FROM holdings").fetchall()
    result = []
    for ticker, quantity, asset_class in holdings:
        price = get_latest_price(conn, asset_class, ticker)
        currency = get_currency(conn, asset_class, ticker)
        market_value = price * quantity if price is not None else None
        market_value_krw = to_krw(market_value, currency) if market_value is not None else None
        result.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "asset_class": asset_class,
                "currency": currency,
                "price": price,
                "market_value": market_value,
                "market_value_krw": market_value_krw,
            }
        )
    return result


def summarize_by_asset_class(holdings_with_value):
    """Returns (totals, weights, grand_total), all in KRW."""
    totals = {k: 0.0 for k in TARGET_WEIGHTS}
    for h in holdings_with_value:
        if h["market_value_krw"] is not None:
            totals[h["asset_class"]] += h["market_value_krw"]
    grand_total = sum(totals.values())
    weights = {k: (v / grand_total if grand_total else 0.0) for k, v in totals.items()}
    return totals, weights, grand_total


def compute_rebalancing_plan(totals, grand_total):
    """Returns a list of dicts, one per asset class, with current vs target weight
    (in KRW) and the amount to buy (positive) or sell (negative) to reach target."""
    plan = []
    for asset_class, target_weight in TARGET_WEIGHTS.items():
        current_value = totals.get(asset_class, 0.0)
        current_weight = current_value / grand_total if grand_total else 0.0
        target_value = grand_total * target_weight
        deviation_pp = (current_weight - target_weight) * 100
        plan.append(
            {
                "asset_class": asset_class,
                "current_value": current_value,
                "current_weight": current_weight,
                "target_weight": target_weight,
                "deviation_pp": deviation_pp,
                "action_amount": target_value - current_value,
                "needs_rebalance": abs(current_weight - target_weight) > REBALANCE_TOLERANCE,
            }
        )
    return plan
