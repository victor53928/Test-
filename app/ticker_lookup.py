"""Resolves a company name to a ticker, so add-by-name forms don't require
the user to already know the ticker code.

KR resolution uses DART's company list (reliable, exact/substring match).
US/JP resolution is best-effort via yfinance's search endpoint, which isn't
guaranteed to exist/work across all yfinance versions -- callers should treat
a None result as "ask the user for the exact ticker instead."
"""

from app.collectors import dart_collector
from app.config import DART_API_KEY


def resolve_kr_ticker(name: str) -> str:
    """Returns a stock code for `name` via DART's company list, or None."""
    if not DART_API_KEY:
        return None

    name_map = dart_collector.get_corp_name_map()
    if name in name_map:
        return name_map[name]

    matches = [code for corp_name, code in name_map.items() if name in corp_name]
    return matches[0] if len(matches) == 1 else None


def resolve_yf_ticker(name: str) -> str:
    """Best-effort company-name -> ticker lookup via yfinance's search endpoint."""
    try:
        import yfinance as yf

        results = yf.Search(name, max_results=1).quotes
        if results:
            return results[0].get("symbol")
    except Exception:
        pass
    return None
