import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import feedparser
import urllib.parse
import numpy as np

# ================= PAGE SETUP & CONFIG =================
st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("Official NSE Data (Price via Yahoo) | Yahoo Finance (Fundamentals)")

# Horizon Weights: How much Tech vs. Fund matters for each timeframe
HORIZON_WEIGHTS = {
    "Short Term":  {"tech": 0.8, "fund": 0.2},
    "Medium Term": {"tech": 0.5, "fund": 0.5},
    "Long Term":   {"tech": 0.3, "fund": 0.7}
}

# Added Current Ratio (cr) and Net Profit Margin (npm) targets
SECTOR_MODELS = {
    "Banks": {"roe": 0.13, "debt": 9999, "peg": 1.5, "cr": 0.0, "npm": 0.15, "pb_target": 1.5},
    "IT Services": {"roe": 0.18, "debt": 50, "peg": 2.0, "cr": 2.0, "npm": 0.12, "pb_target": 3.0},
    "Metals": {"roe": 0.10, "debt": 150, "peg": 1.2, "cr": 1.5, "npm": 0.08, "pb_target": 2.0},
    "FMCG": {"roe": 0.20, "debt": 60, "peg": 3.0, "cr": 1.8, "npm": 0.10, "pb_target": 4.0},
}
DEFAULT_MODEL = {"roe": 0.15, "debt": 100, "peg": 1.8, "cr": 1.5, "npm": 0.10, "pb_target": 2.5}

def normalize_sector(sector):
    if not sector: return "DEFAULT"
    s = sector.lower()
    if "bank" in s or "financial" in s or "insurance" in s: return "Banks"
    if "information technology" in s or "software" in s: return "IT Services"
    if "metal" in s or "steel" in s or "mining" in s: return "Metals"
    if "consumer defensive" in s or "fmcg" in s: return "FMCG"
    return "DEFAULT"

# ================= NSE LIST & SIDEBAR (Unchanged) =================
@st.cache_data(ttl=86400)
def load_nse_list():
    try:
        # Fallback list if URL fails
        fallback = pd.DataFrame([
            {"SYMBOL": "RELIANCE", "NAME OF COMPANY": "Reliance Industries Ltd"},
            {"SYMBOL": "TATASTEEL", "NAME OF COMPANY": "Tata Steel Ltd"},
            {"SYMBOL": "INFY", "NAME OF COMPANY": "Infosys Ltd"},
            {"SYMBOL": "BANKBARODA", "NAME OF COMPANY": "Bank of Baroda"}
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

# Sidebars
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
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info
        bs = ticker.balance_sheet
        cf = ticker.cashflow
        
        # Calculate Current Ratio manually (yfinance sometimes misses it)
        if 'Current Assets' in bs.index and 'Current Liabilities' in bs.index and not bs.empty:
            current_assets = bs.loc['Current Assets'].iloc[0]
            current_liabilities = bs.loc['Current Liabilities'].iloc[0]
            if current_liabilities > 0:
                info['currentRatio'] = current_assets / current_liabilities
            else:
                info['currentRatio'] = 999
        
        # Calculate Free Cash Flow (FCF) Margin
        if 'Operating Cash Flow' in cf.index and 'Capital Expenditure' in cf.index and 'Total Revenue' in info and not cf.empty:
            fcf = cf.loc['Operating Cash Flow'].iloc[0] + cf.loc['Capital Expenditure'].iloc[0] # Note: CapEx is usually negative in yfinance data
            revenue = info['totalRevenue']
            info['fcfMargin'] = fcf / revenue
            
        # Infer Debt Trend (Simplified check for long-term analysis)
        if 'Total Debt' in bs.index and len(bs.columns) >= 2:
            current_debt = bs.loc['Total Debt'].iloc[0]
            prev_debt = bs.loc['Total Debt'].iloc[1]
            info['debtTrend'] = 'reducing' if current_debt < prev_debt else 'increasing'
            
        return info

    except Exception as e:
        st.warning(f"Could not fetch full fundamental details: {e}")
        return {}

def fetch_news(q):
    encoded_q = urllib.parse.quote(q)
    url = f"https://news.google.com/rss/search?q={encoded_q}%20stock%20India&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(url)

# ================= UPGRADED ANALYSIS =================
def run_analysis(symbol):
    df = fetch_price(symbol)
    
    if df.empty or len(df) < 200:
        st.error(f"Could not fetch sufficient price data for {symbol}.")
        return

    info = fetch_fundamentals(symbol)
    
    # Check if fundamentals are available
    if not info:
        st.error(f"Could not fetch fundamental data for {symbol}.")
        return

    sector = normalize_sector(info.get("sector"))
    model = SECTOR_MODELS.get(sector, DEFAULT_MODEL)
    weights = HORIZON_WEIGHTS[horizon]

    # ---- Technical Indicators ----
    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)
    macd = ta.macd(df["Close"])
    df = pd.concat([df, macd], axis=1)

    latest = df.iloc[-1]
    price = latest["Close"]
    prev = df.iloc[-2]
    change = (price - prev["Close"]) / prev["Close"] * 100
    
    tech_score = 0
    fund_score = 0
    max_tech = 8
    max_fund = 14 # Increased max score for new checks
    pros, cons = [], []

    # ---- TECHNICAL SCORING (Same logic) ----
    if price > latest["EMA200"]: tech_score += 2; pros.append("Long-term Uptrend (>200 EMA)")
    
    if horizon == "Short Term":
        if 40 < latest["RSI"] < 70: tech_score += 3; pros.append("RSI in Bullish Zone")
        if price > latest["EMA20"]: tech_score += 3; pros.append("Strong Short-term Momentum (>20 EMA)")
        elif latest["RSI"] > 70: cons.append("Overbought (RSI > 70)")
    elif horizon == "Medium Term":
        if latest["MACDh_12_26_9"] > 0: tech_score += 4; pros.append("MACD Bullish Crossover")
        if price > latest["EMA50"]: tech_score += 2; pros.append("Above Medium-term Baseline (50 EMA)")
    else: # Long Term
        if latest["EMA50"] > latest["EMA200"]: tech_score += 3; pros.append("Golden Cross (50 > 200 EMA)")
        if latest["RSI"] < 45: tech_score += 3; pros.append("RSI Attractive for Accumulation")
    
    # ---- EXPANDED FUNDAMENTAL SCORING ----
    
    # Retrieve all metrics safely, defaulting to None/0
    roe = info.get("returnOnEquity", 0)
    debt = info.get("debtToEquity", 9999) 
    peg = info.get("pegRatio", np.nan)
    npm = info.get("profitMargins", 0) # Net Profit Margin
    pb = info.get("priceToBook")
    cr = info.get("currentRatio")
    fcf_m = info.get("fcfMargin")
    debt_trend = info.get("debtTrend", 'unknown')

    # 1. CORE PROFITABILITY (ROE & Net Margin)
    if roe > model["roe"]:
        fund_score += 2; pros.append(f"High ROE ({round(roe*100,1)}%)")
    else:
        cons.append(f"Below target ROE ({round(roe*100,1)}%)")
    
    if npm > model["npm"]:
        fund_score += 2; pros.append("Healthy Net Profit Margin")
    else:
        cons.append("Low Net Profit Margin")
        
    # 2. CAPITAL STRUCTURE & RISK (Debt & Debt Trend)
    if debt < model["debt"]:
        fund_score += 2; pros.append("Low Debt Level")
    else:
        cons.append("High Debt Level")
        
    if debt_trend == 'reducing':
        fund_score += 1; pros.append("Debt is being reduced (Positive Trend)")
    elif debt_trend == 'increasing':
        cons.append("Debt level is increasing (Negative Trend)")
        
    # 3. LIQUIDITY (Current Ratio)
    # Banks are an exception, their liquidity is measured differently (P/B is key)
    if sector != "Banks" and cr is not None:
        if cr >= model["cr"]:
            fund_score += 2; pros.append(f"Excellent Current Ratio ({round(cr, 2)})")
        else:
            cons.append(f"Low Current Ratio ({round(cr, 2)}) - Short-term risk")
    elif sector == "Banks":
        # P/B is the core "asset quality" check for financials
        if pb is not None and pb < model["pb_target"]:
             fund_score += 3; pros.append(f"Undervalued by Price/Book ({round(pb,2)})")
        else:
             cons.append(f"P/B ({round(pb,2)}) near or above sector norm")
    
    # 4. GROWTH & EFFICIENCY (PEG & FCF)
    
    # PEG Check (General Sector Valuation)
    if not pd.isna(peg):
        if peg < model["peg"]:
            fund_score += 1; pros.append(f"PEG ({round(peg,2)}) cheaper than sector")
        else:
            cons.append(f"PEG ({round(peg,2)}) expensive vs sector")

    # Free Cash Flow (FCF) Check - The highest quality signal for profitability
    if fcf_m is not None:
        if fcf_m > 0.05: # High quality companies usually have FCF margin > 5%
            fund_score += 3; pros.append(f"Strong Free Cash Flow Margin ({round(fcf_m*100,1)}%)")
        else:
            cons.append("Weak or Negative Free Cash Flow")
            
    # 5. Revenue Growth
    rev_growth = info.get("revenueGrowth", 0)
    if rev_growth > 0.15: # >15% growth
        fund_score += 1; pros.append(f"High Revenue Growth ({round(rev_growth*100,1)}%)")

    
    # ---- FINAL CALCULATION ----
    norm_tech = (tech_score / max_tech) * 10
    norm_fund = (fund_score / max_fund) * 10
    final_score = (norm_tech * weights["tech"]) + (norm_fund * weights["fund"])
    final_score = round(final_score, 1)

    verdict = "🟢 BUY" if final_score >= 7.5 else "🟡 HOLD" if final_score >= 4.5 else "🔴 AVOID"

    # ================= UI RENDERING =================
    st.subheader(f"{symbol} - {company_name}")
    st.caption(f"Sector: {sector} | Horizon: {horizon} | Strategy: {int(weights['tech']*100)}% Tech / {int(weights['fund']*100)}% Fund")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Current Price", f"₹{round(price,2)}", f"{round(change,2)}%")
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

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.7, 0.3])

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
