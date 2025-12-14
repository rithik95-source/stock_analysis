import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser

# ================= PAGE SETUP =================
st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("Official NSE Data (Price via Yahoo) | Yahoo Finance (Fundamentals)")

# ================= SECTOR MODELS =================
SECTOR_MODELS = {
    "Banks": {"tech": 0.3, "fund": 0.7, "roe": 0.14, "debt": 800, "peg": 1.5},
    "IT Services": {"tech": 0.4, "fund": 0.6, "roe": 0.18, "debt": 50, "peg": 2.0},
    "Metals": {"tech": 0.6, "fund": 0.4, "roe": 0.12, "debt": 150, "peg": 1.2},
    "FMCG": {"tech": 0.25, "fund": 0.75, "roe": 0.20, "debt": 60, "peg": 3.0},
}
DEFAULT_MODEL = {"tech": 0.5, "fund": 0.5, "roe": 0.15, "debt": 100, "peg": 1.8}

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
        df = pd.read_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
        df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
        return df
    except:
        st.error("Could not load NSE stock list. Using fallback.")
        return pd.DataFrame({"display": ["TATASTEEL – Tata Steel Limited"], "SYMBOL": ["TATASTEEL"], "NAME OF COMPANY": ["Tata Steel Limited"]})

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
# [NEW] Chart Type Toggle
chart_type = st.sidebar.radio("Chart Style", ["Candlestick", "Line"], horizontal=True)

# ================= DATA FETCH (FIXED WITH YFINANCE) =================
@st.cache_data(ttl=3600)
def fetch_price(symbol):
    try:
        # Fetch 2 years of data to ensure enough history for 200 EMA calculation
        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period="2y")
        
        if df.empty:
            return pd.DataFrame()

        # yfinance columns are already Open, High, Low, Close, Volume
        # Ensure index is timezone naive for cleaner plotting
        df.index = df.index.tz_localize(None)
        return df

    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_fundamentals(symbol):
    try:
        return yf.Ticker(f"{symbol}.NS").info
    except:
        return {}

def fetch_news(q):
    url = f"https://news.google.com/rss/search?q={q}%20stock%20India&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(url)

# ================= ANALYSIS =================
def run_analysis(symbol):
    df = fetch_price(symbol)

    if df.empty or len(df) < 200:
        st.error("Insufficient data available for this stock.")
        return

    info = fetch_fundamentals(symbol)
    sector = normalize_sector(info.get("sector"))
    model = SECTOR_MODELS.get(sector, DEFAULT_MODEL)

    # Technical Indicators
    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = latest["Close"]
    change = (price - prev["Close"]) / prev["Close"] * 100

    # ... [Scoring Logic Remains Same] ...
    tech_score, fund_score = 0, 0
    pros, cons = [], []

    # Technical Scoring
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
    else: # Long Term
        if pd.notna(latest["EMA200"]) and price > latest["EMA200"]:
            tech_score += 3; pros.append("Above 200 EMA")
        if pd.notna(latest["RSI"]) and latest["RSI"] < 70:
            tech_score += 1

    if sector in ["Banks", "FMCG"]:
        tech_score = min(tech_score, 4)

    # Fundamental Scoring
    roe = info.get("returnOnEquity", 0)
    debt = info.get("debtToEquity", 9999)
    peg = info.get("pegRatio")

    if roe > model["roe"]: fund_score += 3; pros.append("ROE above sector")
    else: cons.append("Low sector ROE")

    if debt < model["debt"]: fund_score += 2; pros.append("Healthy debt")
    else: cons.append("High sector debt")

    if peg and peg < model["peg"]: fund_score += 2; pros.append("PEG cheaper than sector")
    elif peg: cons.append("PEG expensive vs sector")

    final = tech_score * model["tech"] + fund_score * model["fund"]
    max_score = 6 * model["tech"] + 7 * model["fund"]
    score = round((final / max_score) * 10, 1) if max_score > 0 else 0
    verdict = "🟢 BUY" if score >= 7 else "🟡 HOLD" if score >= 4 else "🔴 AVOID"

    # ================= UI RENDERING =================
    st.subheader(f"{symbol} - {company_name}")
    st.caption(f"Sector: {sector} | Horizon: {horizon} | Price Date: {df.index.max().date()}")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"₹{round(price,2)}", f"{round(change,2)}%")
    c2.metric("Recommendation", verdict)
    c3.metric("Algo Score", f"{score}/10")

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

    # [NEW] Toggle Logic for Candlestick vs Line
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=chart_df.index,
            open=chart_df["Open"], high=chart_df["High"],
            low=chart_df["Low"], close=chart_df["Close"],
            name="Price"
        ), row=1, col=1)
    else:
        # Line Chart (Area style looks nicer)
        fig.add_trace(go.Scatter(
            x=chart_df.index,
            y=chart_df["Close"],
            mode='lines',
            fill='tozeroy', # Fills area under line
            name="Close Price",
            line=dict(color='#00F0FF', width=2)
        ), row=1, col=1)

    # Add EMA overlays if selected (Optional, but looks good)
    if horizon != "Short Term":
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df["EMA200"], 
                                mode='lines', line=dict(color='orange', width=1), name="EMA 200"), row=1, col=1)

    # Volume Chart
    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df["Volume"], name="Volume", marker_color='rgba(200, 200, 200, 0.5)'), row=2, col=1)

    fig.update_layout(
        template="plotly_dark", 
        height=700,
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # -------- NEWS --------
    st.subheader(f"📰 News on {symbol}")
    feed = fetch_news(company_name)
    for e in feed.entries[:5]:
        st.markdown(f"• [{e.title}]({e.link})")

# ================= RUN =================
if st.button("🚀 Run Analysis", type="primary"):
    run_analysis(symbol)
