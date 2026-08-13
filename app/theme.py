"""Shared visual theme, designed around what this app actually is: a
data-dense Korean personal-finance dashboard, not a marketing page. The
reference point is Korean fintech (Toss/증권사 apps) rather than a generic
"AI dashboard" look -- Pretendard (the de facto standard Korean UI typeface)
for text, a tabular monospace face for every number so columns of prices
line up and read at a glance, a restrained single indigo accent instead of
a rainbow of chart colors, and hairline borders instead of heavy shadows.

The one non-negotiable, subject-specific rule: 상승 = 빨간색, 하락 = 파란색
(Korean market convention) for every price delta -- st.metric's built-in
delta is hardcoded green=up/red=down (US convention), which reads backwards
here, so colored_metric() replaces it wherever a 등락 is shown.

Call inject_theme() once near the top of each page, right after
st.set_page_config().
"""

import html

import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

INK = "#12141c"
PAPER = "#fafbfc"
SURFACE = "rgba(18, 20, 28, 0.035)"
LINE = "rgba(18, 20, 28, 0.10)"
ACCENT = "#3454d1"
UP_COLOR = "#d93a3a"  # 상승 -- 빨간색 (한국 증시 관례)
DOWN_COLOR = "#2f6fb0"  # 하락 -- 파란색 (한국 증시 관례)
FLAT_COLOR = "#8a8f98"

_FONT_STACK = "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, sans-serif"
_MONO_STACK = "'IBM Plex Mono', 'JetBrains Mono', ui-monospace, SFMono-Regular, monospace"


def inject_theme():
    st.markdown(
        f"""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css');
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&display=swap');

        html, body, [class*="css"] {{ font-family: {_FONT_STACK}; }}

        .block-container {{ padding-top: 2.25rem; padding-bottom: 3rem; max-width: 1200px; }}
        h1, h2, h3 {{ letter-spacing: -0.02em; font-weight: 700; color: {INK}; }}
        p, .stMarkdown, .stCaption {{ color: {INK}; }}

        /* every number in the app lines up on a tabular grid, not just metrics */
        div[data-testid="stMetricValue"], div[data-testid="stMetricDelta"],
        table, div[data-testid="stDataFrame"], .stMarkdown table {{
            font-family: {_MONO_STACK};
            font-variant-numeric: tabular-nums;
        }}
        div[data-testid="stMetricLabel"] {{
            font-family: {_FONT_STACK};
            font-weight: 600;
            font-size: 0.78rem;
            letter-spacing: 0.01em;
            opacity: 0.6;
            text-transform: uppercase;
        }}

        .stButton > button {{ border-radius: 6px; font-weight: 600; }}
        div[role="radiogroup"] label {{ font-size: 0.92rem; }}

        table {{ border-collapse: collapse; }}
        table th {{
            font-family: {_FONT_STACK} !important;
            font-weight: 600 !important;
            font-size: 0.78rem !important;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            opacity: 0.55;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    style_metric_cards(
        background_color=SURFACE,
        border_color=LINE,
        border_left_color=ACCENT,
        border_radius_px=8,
        box_shadow=False,
    )


def colored_metric(label: str, value: str, delta_value: float = None, delta_suffix: str = "", decimals: int = 2):
    """A card-styled metric matching style_metric_cards' look, but with a
    상승=빨간색/하락=파란색 delta instead of st.metric's US-convention
    green/red. Call inside a `with column:` block to place it in a column,
    same as st.metric."""
    delta_html = ""
    if delta_value is not None:
        if delta_value > 0:
            color, arrow = UP_COLOR, "▲"
        elif delta_value < 0:
            color, arrow = DOWN_COLOR, "▼"
        else:
            color, arrow = FLAT_COLOR, "―"
        delta_html = (
            f'<div style="color:{color};font-family:{_MONO_STACK};font-size:0.9rem;'
            f'font-weight:600;margin-top:2px;">'
            f"{arrow} {abs(delta_value):,.{decimals}f}{html.escape(delta_suffix)}</div>"
        )
    st.markdown(
        f"""
        <div style="background-color:{SURFACE};border:1px solid {LINE};
                    border-left:3px solid {ACCENT};border-radius:8px;
                    padding:0.9rem 1.1rem;">
            <div style="font-weight:600;opacity:0.6;font-size:0.78rem;text-transform:uppercase;
                        letter-spacing:0.01em;">{html.escape(label)}</div>
            <div style="font-family:{_MONO_STACK};font-size:1.55rem;font-weight:600;
                        font-variant-numeric:tabular-nums;color:{INK};">{html.escape(value)}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
