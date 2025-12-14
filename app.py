import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile
import datetime
import feedparser
from nselib import capital_market

# ================= PAGE SETUP =================

st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("Official NSE Data (Price) | Yahoo Finance (Fundamentals)")

# ================= SECTOR MODELS =================

SECTOR_MODELS = {
    "Banks": {
        "tech_weight": 0.3,
        "fund_weight": 0.7,
        "bench": {"roe": 0.14, "debt": 800, "peg": 1.5}
    },
    "IT Services": {
        "tech_weight": 0.4,
        "fund_weight": 0.6,
        "bench": {"roe": 0.18, "debt": 50, "peg": 2.0}
    },
    "Metals": {
        "tech_weight": 0.6,
        "fund_weight": 0.4,
        "bench": {"roe": 0.12, "debt": 150, "peg": 1.2}
    },
    "FMCG": {
        "tech_weight": 0.25,
        "fund_weight": 0.75,
        "bench": {"roe": 0.20, "debt": 60, "peg": 3.0}
    }
}

DEFAULT_MODEL = {
    "tech_weight": 0.5,
    "fund_weight": 0.5,
    "bench": {"roe": 0.15, "debt": 100, "peg": 1.8}
}

def normalize_sector(sector):
    if not sector:
        return "DEFAULT"
    s = sector.lower()
    if "bank" in s or "financial" in s:
        return "Banks"
    if "information technology" in s or "software" in s:
        return "IT Services"
    if "metal" in s or "steel" in s or "mining" in s:
        return "Metals"
    if "consumer defensive" in s or "fmcg" in s:
        return "FMCG"
    return "DEFAULT"

# ================= NSE LIST =================

@st.cache_data(ttl=86400)
def load_nse_list():
    df = pd.read_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
    df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
    return df

nse_df = load_nse_list()
choice = st.selectbox("🔎 Search NSE Stock", nse_df["display"])
row = nse_df[nse_df["display"] == choice].iloc[0]
symbol = row["SYMBOL"]
company_name = row["NAME OF COMPANY"]

# ================= SIDEBAR =================

st.sidebar.subheader("Investment Horizon")
horizon = st.sidebar.selectbox(
    "Select Horizon", ["Short Term", "Medium Term", "Long Term"]
)

chart_type = st.sidebar.radio("Chart Type", ["Candlestick", "Line"])
tf = st.sidebar.selectbox("Chart Range", ["1 Month", "6 Months", "1 Year"])

# ================= DATA =================

@st.cache_data(ttl=3600)
def fetch_price(symbol):
    end = datetime.datetime.now().strftime("%d-%m-%Y")
    start = (datetime.datetime.now() - datetime.timedelta(days=500)).strftime("%d-%m-%Y")
    df = capital_market.price_volume_and_deliverable_position_data(
        symbol=symbol, from_date=start, to_date=end
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df["Date"] = pd.to_datetime(df["Date"], format="%d-%b-%Y")
    df.set_index("Date", inplace=True)
    df = df.rename(columns={
        "OpenPrice": "Open",
        "HighPrice": "High",
        "LowPrice": "Low",
        "ClosePrice": "Close",
        "TotalTradedQuantity": "Volume"
    })
    df = df.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(",", ""), errors="coerce"))
    return df.dropna()

@st.cache_data(ttl=3600)
def fetch_fundamentals(symbol):
    t = yf.Ticker(f"{symbol}.NS")
    return t.info

def fetch_news(q):
    rss = f"https://news.google.com/rss/search?q={q}%20stock%20India&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(rss)

# ================= ANALYSIS =================

def run_analysis(symbol):
    df = fetch_price(symbol)

    if df.empty or len(df) < 2:
        st.error("Insufficient NSE data (holiday, rate-limit, or newly listed stock).")
        return

    info = fetch_fundamentals(symbol)
    sector = normalize_sector(info.get("sector"))
    model = SECTOR_MODELS.get(sector, DEFAULT_MODEL)

    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price = latest["Close"]
    change = (price - prev["Close"]) / prev["Close"] * 100

    tech_score = 0
    fund_score = 0
    pros, cons = [], []

    # ----- TECHNICAL (HORIZON AWARE) -----
    if horizon == "Short Term":
        if pd.notna(latest["EMA20"]) and price > latest["EMA20"]:
            tech_score += 2; pros.append("Above 20 EMA")
        if pd.notna(latest["RSI"]) and 50 < latest["RSI"] < 70:
            tech_score += 2; pros.append("Healthy RSI")

    elif horizon == "Medium Term":
        if pd.notna(latest["EMA50"]) and price > latest["EMA50"]:
            tech_score += 2; pros.append("Above 50 EMA")
        if pd.notna(latest["EMA50"]) and pd.notna(latest["EMA200"]) and latest["EMA50"] > latest["EMA200"]:
            tech_score += 2; pros.append("Golden Cross")

    else:
        if pd.notna(latest["EMA200"]) and price > latest["EMA200"]:
            tech_score += 3; pros.append("Above 200 EMA")
        if pd.notna(latest["RSI"]) and latest["RSI"] < 70:
            tech_score += 1

    if sector in ["Banks", "FMCG"]:
        tech_score = min(tech_score, 4)

    # ----- FUNDAMENTAL (SECTOR RELATIVE) -----
    roe = info.get("returnOnEquity", 0)
    debt = info.get("debtToEquity", 9999)
    peg = info.get("pegRatio", None)

    if roe > model["bench"]["roe"]:
        fund_score += 3; pros.append("ROE above sector")
    else:
        cons.append("Low sector ROE")

    if debt < model["bench"]["debt"]:
        fund_score += 2; pros.append("Healthy debt")
    else:
        cons.append("High sector debt")

    if peg and peg < model["bench"]["peg"]:
        fund_score += 2; pros.append("PEG cheaper than sector")
    elif peg:
        cons.append("PEG expensive vs sector")

    final = (tech_score * model["tech_weight"]) + (fund_score * model["fund_weight"])
    max_score = (6 * model["tech_weight"]) + (7 * model["fund_weight"])
    score = round((final / max_score) * 10, 1) if max_score > 0 else 0

    verdict = "🟢 BUY" if score >= 7 else "🟡 HOLD" if score >= 4 else "🔴 AVOID"

    # ================= UI =================

    st.subheader(symbol)
    st.caption(f"Sector: {sector} | Horizon: {horizon}")
    st.metric("Price", f"₹{round(price,2)}", f"{round(change,2)}%")
    st.metric("Score", f"{score}/10", verdict)

    c1, c2 = st.columns(2)
    with c1:
        st.success("Positives")
        for p in pros: st.write("•", p)
    with c2:
        st.error("Negatives")
        for c in cons: st.write("•", c)

    # ----- CHART -----
    days = 30 if tf == "1 Month" else 180 if tf == "6 Months" else 365
    chart_df = df.tail(days)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)
    fig.add_trace(go.Candlestick(
        x=chart_df.index,
        open=chart_df["Open"], high=chart_df["High"],
        low=chart_df["Low"], close=chart_df["Close"]
    ), row=1, col=1)
    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df["Volume"]), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=600)
    st.plotly_chart(fig, use_container_width=True)

    # ----- NEWS -----
    st.subheader("📰 Latest News")
    feed = fetch_news(company_name)
    for e in feed.entries[:5]:
        st.markdown(f"[{e.title}]({e.link})")

# ================= RUN =================

if st.button("🚀 Run Analysis", type="primary"):
    run_analysis(symbol)
