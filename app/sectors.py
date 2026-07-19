"""Industry sector definitions and representative tickers.

Sectors flagged with has_us=True are heavily influenced by US markets, so
representative US-listed stocks are tracked alongside the KR names. Every
sector also tracks representative Japan-listed stocks (jp_stocks) for
cross-market comparison.
"""

SECTORS = [
    {
        "key": "semiconductor",
        "name_kr": "반도체",
        "has_us": True,
        "kr_stocks": [
            ("005930", "삼성전자"),
            ("000660", "SK하이닉스"),
            ("000990", "DB하이텍"),
            ("058470", "리노공업"),
        ],
        "us_stocks": [
            ("NVDA", "NVIDIA"),
            ("AMD", "AMD"),
            ("INTC", "Intel"),
            ("TSM", "TSMC"),
            ("AVGO", "Broadcom"),
        ],
        "jp_stocks": [
            ("8035.T", "Tokyo Electron"),
            ("6857.T", "Advantest"),
            ("6723.T", "Renesas Electronics"),
        ],
    },
    {
        "key": "defense",
        "name_kr": "방산",
        "has_us": True,
        "kr_stocks": [
            ("012450", "한화에어로스페이스"),
            ("064350", "현대로템"),
            ("079550", "LIG넥스원"),
            ("047810", "한국항공우주"),
        ],
        "us_stocks": [
            ("LMT", "Lockheed Martin"),
            ("RTX", "RTX Corporation"),
            ("NOC", "Northrop Grumman"),
            ("GD", "General Dynamics"),
        ],
        "jp_stocks": [
            ("7011.T", "Mitsubishi Heavy Industries"),
            ("7013.T", "IHI Corporation"),
        ],
    },
    {
        "key": "shipbuilding",
        "name_kr": "조선",
        "has_us": True,
        "kr_stocks": [
            ("009540", "HD한국조선해양"),
            ("010140", "삼성중공업"),
            ("042660", "한화오션"),
        ],
        "us_stocks": [
            ("HII", "Huntington Ingalls Industries"),
        ],
        "jp_stocks": [
            ("7003.T", "Mitsui E&S"),
            ("7014.T", "Namura Shipbuilding"),
        ],
    },
    {
        "key": "energy",
        "name_kr": "에너지",
        "has_us": True,
        "kr_stocks": [
            ("096770", "SK이노베이션"),
            ("078930", "GS"),
            ("010950", "S-Oil"),
            ("015760", "한국전력"),
        ],
        "us_stocks": [
            ("XOM", "ExxonMobil"),
            ("CVX", "Chevron"),
            ("OXY", "Occidental Petroleum"),
        ],
        "jp_stocks": [
            ("5020.T", "ENEOS Holdings"),
            ("1605.T", "Inpex"),
        ],
    },
    {
        "key": "nuclear",
        "name_kr": "원전",
        "has_us": True,
        "kr_stocks": [
            ("034020", "두산에너빌리티"),
            ("052690", "한전기술"),
            ("051600", "한전KPS"),
        ],
        "us_stocks": [
            ("CCJ", "Cameco"),
            ("BWXT", "BWX Technologies"),
            ("CEG", "Constellation Energy"),
            ("SMR", "NuScale Power"),
        ],
        "jp_stocks": [
            ("6501.T", "Hitachi"),
            ("9503.T", "Kansai Electric Power"),
        ],
    },
    {
        "key": "autonomous_driving",
        "name_kr": "자율주행",
        "has_us": True,
        "kr_stocks": [
            ("012330", "현대모비스"),
            ("204320", "만도"),
            ("005380", "현대차"),
        ],
        "us_stocks": [
            ("TSLA", "Tesla"),
            ("MBLY", "Mobileye"),
            ("APTV", "Aptiv"),
        ],
        "jp_stocks": [
            ("7203.T", "Toyota Motor"),
            ("6902.T", "Denso"),
        ],
    },
    {
        "key": "physical_ai",
        "name_kr": "피지컬 AI",
        "has_us": True,
        "kr_stocks": [
            ("277810", "레인보우로보틱스"),
            ("454910", "두산로보틱스"),
            ("058610", "에스피지"),
        ],
        "us_stocks": [
            ("PLTR", "Palantir Technologies"),
            ("MSFT", "Microsoft"),
            ("GOOGL", "Alphabet (Google)"),
            ("META", "Meta Platforms"),
            ("SYM", "Symbotic"),
        ],
        "jp_stocks": [
            ("6954.T", "Fanuc"),
            ("6506.T", "Yaskawa Electric"),
        ],
    },
    {
        "key": "cosmetics",
        "name_kr": "화장품",
        "has_us": True,
        "kr_stocks": [
            ("090430", "아모레퍼시픽"),
            ("051900", "LG생활건강"),
            ("192820", "코스맥스"),
        ],
        "us_stocks": [
            ("EL", "Estée Lauder"),
            ("ELF", "e.l.f. Beauty"),
            ("COTY", "Coty"),
        ],
        "jp_stocks": [
            ("4911.T", "Shiseido"),
            ("4452.T", "Kao Corporation"),
        ],
    },
    {
        "key": "entertainment",
        "name_kr": "엔터테인먼트",
        "has_us": True,
        "kr_stocks": [
            ("352820", "하이브"),
            ("035900", "JYP Ent."),
            ("041510", "에스엠"),
            ("122870", "와이지엔터테인먼트"),
        ],
        "us_stocks": [
            ("DIS", "Walt Disney"),
            ("NFLX", "Netflix"),
            ("WBD", "Warner Bros. Discovery"),
        ],
        "jp_stocks": [
            ("6758.T", "Sony Group"),
            ("9602.T", "Toho"),
        ],
    },
    {
        "key": "battery",
        "name_kr": "2차전지/배터리",
        "has_us": True,
        "kr_stocks": [
            ("373220", "LG에너지솔루션"),
            ("006400", "삼성SDI"),
            ("247540", "에코프로비엠"),
        ],
        "us_stocks": [
            ("TSLA", "Tesla"),
            ("ALB", "Albemarle"),
        ],
        "jp_stocks": [
            ("6752.T", "Panasonic Holdings"),
            ("6762.T", "TDK Corporation"),
        ],
    },
]


def all_kr_tickers():
    return [(t, name, s["key"]) for s in SECTORS for t, name in s["kr_stocks"]]


def all_us_tickers():
    return [(t, name, s["key"]) for s in SECTORS for t, name in s["us_stocks"]]


def all_jp_tickers():
    return [(t, name, s["key"]) for s in SECTORS for t, name in s["jp_stocks"]]


# Commodity and bond proxies tracked via yfinance (Phase 3)
COMMODITIES = [
    ("GC=F", "금"),
    ("SI=F", "은"),
    ("HG=F", "구리"),
    ("CL=F", "WTI 원유"),
]

BONDS = [
    ("^TNX", "미국 10년물 국채금리"),
    ("TLT", "미국 장기채 ETF"),
    ("148070.KS", "국고채 10년 ETF (KOSEF)"),
]

# Major market indices (마켓정보 page), grouped by country.
INDICES = [
    {"country": "KR", "label": "🇰🇷 한국", "symbols": [("^KS11", "코스피"), ("^KQ11", "코스닥")]},
    {"country": "JP", "label": "🇯🇵 일본", "symbols": [("^N225", "닛케이225")]},
    {"country": "TW", "label": "🇹🇼 대만", "symbols": [("^TWII", "대만가권지수")]},
    {
        "country": "US",
        "label": "🇺🇸 미국",
        "symbols": [("^GSPC", "S&P 500"), ("^DJI", "다우존스"), ("^IXIC", "나스닥")],
    },
]


def all_index_symbols():
    return [(sym, name) for group in INDICES for sym, name in group["symbols"]]
