"""Shared visual theme: card-style metrics, tightened spacing/typography, and
a Korean-market-correct 상승=빨간색/하락=파란색 color convention for price
deltas -- st.metric's built-in delta is hardcoded green=up/red=down (US
convention), which reads backwards to a Korean audience.

Call inject_theme() once near the top of each page, right after
st.set_page_config(). Use colored_metric() instead of st.metric(..., delta=...)
anywhere a price change/등락 is shown.
"""

import html

import streamlit as st
from streamlit_extras.metric_cards import style_metric_cards

PRIMARY_COLOR = "#2f6fed"
UP_COLOR = "#e0393e"  # 상승 -- 빨간색 (한국 증시 관례)
DOWN_COLOR = "#1f6feb"  # 하락 -- 파란색 (한국 증시 관례)
FLAT_COLOR = "#8a8f98"


def inject_theme():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2rem; padding-bottom: 3rem; }
        h1, h2, h3 { letter-spacing: -0.01em; }
        div[data-testid="stMetricLabel"] { font-weight: 600; opacity: 0.75; }
        div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
        .stButton > button { border-radius: 8px; }
        div[data-testid="stDataFrame"], table { font-variant-numeric: tabular-nums; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    style_metric_cards(
        background_color="rgba(127, 127, 127, 0.04)",
        border_color="rgba(127, 127, 127, 0.25)",
        border_left_color=PRIMARY_COLOR,
        border_radius_px=10,
        box_shadow=True,
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
            f'<div style="color:{color};font-size:0.9rem;font-weight:600;margin-top:2px;">'
            f"{arrow} {abs(delta_value):,.{decimals}f}{html.escape(delta_suffix)}</div>"
        )
    st.markdown(
        f"""
        <div style="background-color:rgba(127,127,127,0.04);border:1px solid rgba(127,127,127,0.25);
                    border-left:0.5rem solid {PRIMARY_COLOR};border-radius:10px;
                    padding:0.9rem 1rem;box-shadow:0 0.15rem 1.75rem 0 rgba(58,59,69,0.1);">
            <div style="font-weight:600;opacity:0.75;font-size:0.85rem;">{html.escape(label)}</div>
            <div style="font-size:1.6rem;font-weight:600;font-variant-numeric:tabular-nums;">{html.escape(value)}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
