import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import urllib.parse  # Fixed: For safe URL encoding

# ================= PAGE SETUP =================
st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("Official NSE Data (Price via Yahoo) | Yahoo Finance (Fundamentals)")

# ================= CONFIGURATION =================
# Horizon Weights: How much Tech vs. Fund matters for each timeframe
HORIZON_WEIGHTS = {
    "Short Term":  {"tech": 0.8, "fund": 0.2},  # Traders care about price action
    "Medium Term": {"tech": 0.5, "fund": 0.5},  # Balanced approach
    "Long Term":   {"tech": 0.3, "fund": 0.7}   # Investors care about company quality
}

SECTOR_MODELS = {
    "Banks": {"roe": 0.14, "debt": 800, "peg": 1.5, "pm": 0.15},
    "IT Services": {"roe": 0.18, "debt": 50, "peg": 2.0, "pm": 0.12},
    "Metals": {"roe": 0.12, "debt": 150, "peg": 1.2, "pm": 0.08},
    "FMCG": {"roe": 0.20, "debt": 60, "peg": 3.0, "pm": 0.10},
}
DEFAULT_MODEL = {"roe": 0.15, "debt": 100, "peg": 1.8, "pm": 0.10}

def normalize_sector(sector):
    if not sector: return "DEFAULT"
    s = sector.lower()
    if "bank" in s or "financial" in s: return "Banks"
    if "information technology" in s or "software" in s: return "IT Services"
    if "metal" in s or "steel" in s or "mining" in s: return "Metals"
    if "consumer defensive" in s or "fmcg" in s: return "FMCG"
    return "DEFAULT"

# ================= NSE LIST =================
@st.cache_data(ttl=86400)
def load_nse_list():
    try:
        # Fallback list if URL fails
        fallback = pd.DataFrame([
            {"SYMBOL": "RELIANCE", "NAME OF COMPANY": "Reliance Industries Ltd"},
            {"SYMBOL": "TATASTEEL", "NAME OF COMPANY": "Tata Steel Ltd"},
            {"SYMBOL": "INFY", "NAME OF COMPANY": "Infosys Ltd"},
            {"SYMBOL": "HDFCBANK", "NAME OF COMPANY": "HDFC Bank Ltd"}
        ])
        fallback["display"] = fallback["SYMBOL"] + " – " + fallback["NAME OF COMPANY"]

        df = pd.read_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
        df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
        return df
    except:
        return fallback

nse_df = load_nse_list()
selected = st.selectbox("🔎 Search NSE Stock", nse_df["display"])
row = nse_df[nse_df["display"] == selected].iloc[0]
symbol = row["SYMBOL"]
company_name = row["NAME OF COMPANY"]

# ================= SIDEBAR =================
st.sidebar.subheader("Investment Horizon")
horizon = st.sidebar.selectbox("Select Horizon", ["Short Term", "Medium Term", "Long Term"])
chart_range = st.sidebar.selectbox("Chart Range", ["1 Month", "6 Months", "1 Year"])

st.sidebar.subheader("Chart Options")
chart_type = st.sidebar.radio("Chart Style", ["Candlestick", "Line"], horizontal=True)

# ================= DATA FETCH =================
@st.cache_data(ttl=3600)
def fetch_price(symbol):
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period="2y")
        if df.empty: return pd.DataFrame()
        df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_fundamentals(symbol):
    try:
        return yf.Ticker(f"{symbol}.NS").info
    except:
        return {}

def fetch_news(q):
    # FIXED: Use quote to encode special characters in company names
    encoded_q = urllib.parse.quote(q)
    url = f"https://news.google.com/rss/search?q={encoded_q}%20stock%20India&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(url)

# ================= ANALYSIS =================
def run_analysis(symbol):
    df = fetch_price(symbol)
    
    if df.empty or len(df) < 200:
        st.error(f"Could not fetch sufficient data for {symbol}.")
        return

    info = fetch_fundamentals(symbol)
    sector = normalize_sector(info.get("sector"))
    model = SECTOR_MODELS.get(sector, DEFAULT_MODEL)
    weights = HORIZON_WEIGHTS[horizon]

    # ---- Technical Indicators ----
    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)
    
    # MACD Calculation for Medium Term
    macd = ta.macd(df["Close"])
    df = pd.concat([df, macd], axis=1) # Append MACD columns

    latest = df.iloc[-1]
    price = latest["Close"]
    
    tech_score = 0
    fund_score = 0
    max_tech = 0
    max_fund = 0
    pros, cons = [], []

    # ---- DYNAMIC TECHNICAL SCORING ----
    
    # 1. Trend Analysis (All Horizons)
    if price > latest["EMA200"]:
        tech_score += 1; pros.append("Long-term Uptrend (>200 EMA)")
    max_tech += 1

    # 2. Horizon Specific Logic
    if horizon == "Short Term":
        # RSI Strategy
        if 40 < latest["RSI"] < 70:
            tech_score += 2; pros.append("RSI in Bullish Zone")
        elif latest["RSI"] > 70:
            tech_score -= 1; cons.append("Overbought (RSI > 70)")
        max_tech += 2
        
        # Momentum
        if price > latest["EMA20"]:
            tech_score += 2; pros.append("Strong Short-term Momentum (>20 EMA)")
        else:
            cons.append("Weak Short-term Momentum (<20 EMA)")
        max_tech += 2

    elif horizon == "Medium Term":
        # MACD Strategy
        if latest["MACDh_12_26_9"] > 0: # Histogram positive
            tech_score += 2; pros.append("MACD Bullish Crossover")
        else:
            cons.append("MACD Bearish/Weak")
        max_tech += 2

        # 50 EMA Support
        if price > latest["EMA50"]:
            tech_score += 2; pros.append("Above Medium-term Baseline (50 EMA)")
        max_tech += 2

    else: # Long Term
        # Golden Cross Check
        if latest["EMA50"] > latest["EMA200"]:
            tech_score += 3; pros.append("Golden Cross (50 > 200 EMA)")
        max_tech += 3
        
        # Buying the dip?
        if latest["RSI"] < 40:
             tech_score += 1; pros.append("RSI Attractive for Accumulation")
        max_tech += 1

    # ---- FUNDAMENTAL SCORING (Enhanced) ----
    
    roe = info.get("returnOnEquity", 0)
    debt = info.get("debtToEquity", 9999) # Default high if missing
    peg = info.get("pegRatio", None)
    pm = info.get("profitMargins", 0)
    rev_growth = info.get("revenueGrowth", 0)

    # ROE Check
    if roe > model["roe"]:
        fund_score += 2; pros.append(f"High ROE ({round(roe*100,1)}%)")
    else:
        cons.append("Below avg ROE")
    max_fund += 2

    # Profit Margin Check (New)
    if pm > model["pm"]:
        fund_score += 2; pros.append("Healthy Profit Margins")
    else:
        cons.append("Thin Profit Margins")
    max_fund += 2

    # Debt Check
    if debt < model["debt"]:
        fund_score += 2; pros.append("Low Debt Level")
    else:
        cons.append("High Debt Level")
    max_fund += 2

    # Growth Check (New)
    if rev_growth > 0.10: # >10% growth
        fund_score += 1; pros.append("Double Digit Revenue Growth")
    max_fund += 1

    # Valuation Check
    if peg and peg < model["peg"]:
        fund_score += 2; pros.append("Undervalued (PEG Ratio)")
    elif peg is None:
        pass # Ignore if data missing
    else:
        cons.append("Valuation Expensive")
    max_fund += 2

    # ---- FINAL CALCULATION ----
    
    # Normalize scores to 10
    norm_tech = (tech_score / max_tech) * 10 if max_tech > 0 else 0
    norm_fund = (fund_score / max_fund) * 10 if max_fund > 0 else 0
    
    # Apply Weighted Average based on Horizon
    final_score = (norm_tech * weights["tech"]) + (norm_fund * weights["fund"])
    final_score = round(final_score, 1)

    verdict = "🟢 BUY" if final_score >= 7.5 else "🟡 HOLD" if final_score >= 4.5 else "🔴 AVOID"

    # ================= UI RENDERING =================
    st.subheader(f"{symbol} - {company_name}")
    st.caption(f"Sector: {sector} | Horizon: {horizon} | Strategy: {int(weights['tech']*100)}% Tech / {int(weights['fund']*100)}% Fund")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"₹{round(price,2)}")
    c2.metric("Recommendation", verdict)
    c3.metric("Algo Score", f"{final_score}/10")

    sc1, sc2 = st.columns(2)
    with sc1:
        st.success("Positives")
        for p in pros: st.write(f"✅ {p}")
    with sc2:
        st.error("Negatives")
        for c in cons: st.write(f"❌ {c}")

    # -------- CHART --------
    days = 30 if chart_range == "1 Month" else 180 if chart_range == "6 Months" else 365
    chart_df = df.tail(days)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.1, row_heights=[0.7, 0.3])

    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=chart_df.index, open=chart_df["Open"], high=chart_df["High"],
            low=chart_df["Low"], close=chart_df["Close"], name="Price"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=chart_df.index, y=chart_df["Close"], mode='lines',
            fill='tozeroy', name="Close Price", line=dict(color='#00F0FF', width=2)
        ), row=1, col=1)

    # Plot EMA overlays based on Horizon
    if horizon == "Short Term":
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["EMA20"], line=dict(color='yellow', width=1), name="EMA 20"), row=1, col=1)
    elif horizon == "Medium Term":
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["EMA50"], line=dict(color='orange', width=1), name="EMA 50"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["EMA200"], line=dict(color='purple', width=1), name="EMA 200"), row=1, col=1)

    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df["Volume"], name="Volume", marker_color='rgba(200, 200, 200, 0.5)'), row=2, col=1)

    fig.update_layout(template="plotly_dark", height=700, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    # -------- NEWS --------
    st.subheader(f"📰 News on {symbol}")
    feed = fetch_news(company_name)
    if feed.entries:
        for e in feed.entries[:5]:
            st.markdown(f"• [{e.title}]({e.link})")
    else:
        st.write("No recent news found.")

# ================= RUN =================
if st.button("🚀 Run Analysis", type="primary"):
    run_analysis(symbol)
