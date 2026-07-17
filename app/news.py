"""Naver Search API (news) client.

Requires a free Naver Developers app with the "검색" (Search) API enabled:
https://developers.naver.com/apps
"""

import html
import re

import requests

from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"

_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(raw: str) -> str:
    return html.unescape(_TAG_RE.sub("", raw or ""))


def fetch_news(keyword: str, display: int = 10) -> list[dict]:
    """Returns up to `display` recent news items for `keyword`, sorted by date.

    Each item: {title, description, link, pubDate}, with Naver's <b> highlight
    tags stripped and HTML entities unescaped.
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET가 설정되지 않았습니다.")

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": display, "sort": "date"}

    resp = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()

    return [
        {
            "title": _clean_text(item.get("title", "")),
            "description": _clean_text(item.get("description", "")),
            "link": item.get("link", ""),
            "pubDate": item.get("pubDate", ""),
        }
        for item in resp.json().get("items", [])
    ]
