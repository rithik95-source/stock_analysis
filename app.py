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
        "benchmarks": {"roe": 0.14, "debtToEquity": 800, "peg": 1.5}
    },
    "IT Services": {
        "tech_weight": 0.4,
        "fund_weight": 0.6,
        "benchmarks": {"roe": 0.18, "debtToEquity": 50, "peg": 2.0}
    },
    "Metals": {
        "tech_weight": 0.6,
        "fund_weight": 0.4,
        "benchmarks": {"roe": 0.12, "debtToEquity": 150, "peg": 1.2}
    },
    "FMCG": {
        "tech_weight": 0.25,
        "fund_weight": 0.75,
        "benchmarks": {"roe": 0.20, "debtToEquity": 60, "peg": 3.0}
    }
}

DEFAULT_MODEL = {
    "tech_weight": 0.5,
    "fund_weight": 0.5,
    "benchmarks": {"roe": 0.15, "debtToEquity": 100, "peg": 1.8}
}

def normalize_sector(yahoo_sector):
    if not yahoo_sector:
        return "DEFAULT"
    s = yahoo_sector.lower()
    if "bank" in s or "financial" in s:
        return "Banks"
    if "information technology" in s or "software" in s:
        return "IT Services"
    if "metal" in s or "steel" in s or "mining" in s:
        return "Metals"
    if "consumer defensive" in s or "fmcg" in s:
        return "FMCG"
    return "DEFAULT"

# ================= NSE STOCK LIST =================

@st.cache_data(ttl=86400)
def load_nse_list():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    df["symbol"] = df["SYMBOL"]
    df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
    df["company_name"] = df["NAME OF COMPANY"]
    return df

nse_df = load_nse_list()
selected = st.selectbox("🔎 Search NSE Stock", nse_df["display"])
row = nse_df.loc[nse_df["display"] == selected].iloc[0]
symbol = row["symbol"]
company_name = row["company_name"]

# ================= SIDEBAR =================

st.sidebar.subheader("Chart Settings")
chart_type = st.sidebar.radio("Graph Type", ["Candlestick", "Line"])
tf_label = st.sidebar.selectbox("Chart Range", ["1 Month", "6 Months", "1 Year"])

# ================= DATA FETCH =================

@st.cache_data(ttl=3600)
def fetch_price_data_nse(symbol):
    end = datetime.datetime.now().strftime("%d-%m-%Y")
    start = (datetime.datetime.now() - datetime.timedelta(days=500)).strftime("%d-%m-%Y")
    df = capital_market.price_volume_and_deliverable_position_data(
        symbol=symbol, from_date=start, to_date=end
    )
    df["Date"] = pd.to_datetime(df["Date"], format="%d-%b-%Y")
    df.set_index("Date", inplace=True)
    df = df.rename(columns={
        "OpenPrice": "Open", "HighPrice": "High",
        "LowPrice": "Low", "ClosePrice": "Close",
        "TotalTradedQuantity": "Volume"
    })
    df = df.apply(lambda x: pd.to_numeric(x.astype(str).str.replace(",", ""), errors="coerce"))
    return df.dropna()

@st.cache_data(ttl=3600)
def fetch_yahoo_details(symbol):
    stock = yf.Ticker(f"{symbol}.NS")
    return stock.info, stock.major_holders, stock.institutional_holders

def fetch_google_news(query):
    rss = f"https://news.google.com/rss/search?q={query}%20stock%20India&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(rss)

# ================= ANALYSIS =================

def run_analysis(symbol):
    df = fetch_price_data_nse(symbol)
    info, major, inst = fetch_yahoo_details(symbol)

    sector_name = normalize_sector(info.get("sector"))
    model = SECTOR_MODELS.get(sector_name, DEFAULT_MODEL)
    tech_weight = model["tech_weight"]
    fund_weight = model["fund_weight"]
    bench = model["benchmarks"]

    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)

    latest = df.iloc[-1]
    price = latest["Close"]
    prev = df["Close"].iloc[-2]
    change = (price - prev) / prev * 100

    tech_score, fund_score = 0, 0
    pros, cons = [], []

    # -------- TECHNICAL --------
    if latest["EMA50"] and price > latest["EMA50"]:
        tech_score += 2
        pros.append("Price above 50 EMA")
    if latest["EMA50"] and latest["EMA200"] and latest["EMA50"] > latest["EMA200"]:
        tech_score += 2
        pros.append("Golden Cross")
    if latest["RSI"] and 50 < latest["RSI"] < 70:
        tech_score += 1
        pros.append("Healthy RSI")

    if sector_name in ["Banks", "FMCG"]:
        tech_score = min(tech_score, 4)

    # -------- FUNDAMENTAL (RELATIVE) --------
    roe = info.get("returnOnEquity", 0)
    debt = info.get("debtToEquity", 9999)
    peg = info.get("pegRatio", None)

    if roe > bench["roe"]:
        fund_score += 3
        pros.append("ROE above sector average")
    else:
        cons.append("ROE below sector")

    if debt < bench["debtToEquity"]:
        fund_score += 2
        pros.append("Debt healthier than sector")
    else:
        cons.append("High sector-relative debt")

    if peg and peg < bench["peg"]:
        fund_score += 2
        pros.append("PEG cheaper than sector")
    elif peg:
        cons.append("PEG expensive vs sector")

    final = (tech_score * tech_weight) + (fund_score * fund_weight)
    max_score = (6 * tech_weight) + (7 * fund_weight)
    score = round((final / max_score) * 10, 1)

    verdict = "🟢 BUY" if score >= 7 else "🟡 HOLD" if score >= 4 else "🔴 AVOID"

    # ================= UI =================

    st.subheader(symbol)
    st.caption(f"Sector: {sector_name} | Auto Weights → T:{tech_weight} F:{fund_weight}")
    st.metric("Price", f"₹{round(price,2)}", f"{round(change,2)}%")
    st.metric("Score", f"{score}/10", verdict)

    c1, c2 = st.columns(2)
    with c1:
        st.success("Positives")
        for p in pros: st.write("•", p)
    with c2:
        st.error("Negatives")
        for c in cons: st.write("•", c)

    # -------- CHART --------
    days = 30 if tf_label == "1 Month" else 180 if tf_label == "6 Months" else 365
    chart_df = df.tail(days)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True)
    fig.add_trace(go.Candlestick(
        x=chart_df.index,
        open=chart_df["Open"], high=chart_df["High"],
        low=chart_df["Low"], close=chart_df["Close"]
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["EMA50"], name="EMA50"), row=1, col=1)
    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df["Volume"], name="Volume"), row=2, col=1)
    fig.update_layout(template="plotly_dark", height=600)
    st.plotly_chart(fig, use_container_width=True)

    # -------- NEWS --------
    st.subheader("📰 Latest News")
    feed = fetch_google_news(company_name)
    for e in feed.entries[:5]:
        st.markdown(f"[{e.title}]({e.link})")

# ================= RUN =================

if st.button("🚀 Run Analysis", type="primary"):
    run_analysis(symbol)
