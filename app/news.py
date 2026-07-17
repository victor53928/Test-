"""Client for the Naver Search API (News) - keyword-based news lookup.

Requires a free app registered at https://developers.naver.com/apps/#/register
with the 검색 (Search) API enabled; the Client ID/Secret go in .env.
"""

import html
import re

import requests

from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

_TAG_RE = re.compile(r"<[^>]+>")


class NaverNewsError(RuntimeError):
    pass


def credentials_configured() -> bool:
    return bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text))


def search_news(query: str, display: int = 20, sort: str = "date") -> list[dict]:
    """Search Naver News for `query`.

    sort: 'date' (most recent first) or 'sim' (relevance).
    Returns a list of dicts with title, description, link, pub_date.
    """
    if not credentials_configured():
        raise NaverNewsError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET가 설정되지 않았습니다. .env를 확인하세요."
        )

    try:
        resp = requests.get(
            NAVER_NEWS_URL,
            params={"query": query, "display": display, "sort": sort},
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise NaverNewsError(f"네이버 뉴스 API 호출에 실패했습니다: {e}") from e

    items = resp.json().get("items", [])
    return [
        {
            "title": _clean(item["title"]),
            "description": _clean(item["description"]),
            "link": item.get("originallink") or item["link"],
            "pub_date": item["pubDate"],
        }
        for item in items
    ]
