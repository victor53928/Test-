"""Naver Search API (news) client.

Requires a free Naver Developers app with the "검색" (Search) API enabled:
https://developers.naver.com/apps
"""

import html
import re

import requests

from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
NAVER_API_MAX_DISPLAY = 100

_TAG_RE = re.compile(r"<[^>]+>")

# Naver's news search API has no server-side "restrict to this publisher"
# parameter, so filtering by source is done client-side against originallink.
SOURCE_DOMAINS = {"매일경제": "mk.co.kr", "한국경제": "hankyung.com"}


def _clean_text(raw: str) -> str:
    return html.unescape(_TAG_RE.sub("", raw or ""))


def _clean_item(item: dict) -> dict:
    return {
        "title": _clean_text(item.get("title", "")),
        "description": _clean_text(item.get("description", "")),
        "link": item.get("link", ""),
        "originallink": item.get("originallink", ""),
        "pubDate": item.get("pubDate", ""),
    }


def _source_label(item: dict) -> str:
    url = item.get("originallink") or item.get("link") or ""
    for label, domain in SOURCE_DOMAINS.items():
        if domain in url:
            return label
    return ""


def fetch_news(keyword: str, display: int = 10, source_domains: list = None) -> list:
    """Returns up to `display` recent news items for `keyword`, sorted by date.

    Each item: {title, description, link, originallink, pubDate, source}, with
    Naver's <b> highlight tags stripped and HTML entities unescaped.

    If `source_domains` is given (e.g. ["mk.co.kr", "hankyung.com"]), only
    items whose originallink/link matches one of those domains are returned
    (fetching a larger page from Naver first, since there's no server-side
    publisher filter) -- results may come back empty if none of the requested
    publishers covered that keyword recently.
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID/NAVER_CLIENT_SECRET가 설정되지 않았습니다.")

    fetch_display = NAVER_API_MAX_DISPLAY if source_domains else display
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": fetch_display, "sort": "date"}

    resp = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()

    items = [_clean_item(item) for item in resp.json().get("items", [])]

    if source_domains:
        items = [
            item
            for item in items
            if any(domain in (item["originallink"] or item["link"]) for domain in source_domains)
        ]

    for item in items:
        item["source"] = _source_label(item)

    return items[:display]
