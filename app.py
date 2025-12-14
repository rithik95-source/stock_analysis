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
import feedparser  # NEW: For Google News

# ================= PAGE SETUP =================

st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("Yahoo Finance | Technical + Fundamental | Research Tool")

# ================= NSE STOCK LIST =================

@st.cache_data(ttl=86400)
def load_nse_list():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    try:
        df = pd.read_csv(url)
        df["symbol"] = df["SYMBOL"] + ".NS"
        df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
        # Save company name for better news searching
        df["company_name"] = df["NAME OF COMPANY"]
        return df
    except Exception as e:
        return pd.DataFrame(columns=["symbol", "display", "company_name"])

nse_df = load_nse_list()

company_name = ""
if not nse_df.empty:
    selected = st.selectbox("🔎 Search NSE Stock", nse_df["display"])
    row = nse_df.loc[nse_df["display"] == selected].iloc[0]
    symbol = row["symbol"]
    company_name = row["company_name"]
else:
    symbol = st.text_input("Enter Symbol (e.g., RELIANCE.NS)", "RELIANCE.NS")
    company_name = symbol.replace(".NS", "")

# ================= SIDEBAR CONTROLS =================

st.sidebar.header("⚙️ Controls")

# Analysis parameters
horizon = st.sidebar.selectbox(
    "Investment Horizon",
    ["Short Term", "Medium Term", "Long Term"]
)

tech_weight = st.sidebar.slider("Technical Weight", 0.0, 1.0, 0.6, 0.05)
fund_weight = st.sidebar.slider("Fundamental Weight", 0.0, 1.0, 0.4, 0.05)

st.sidebar.markdown("---")
st.sidebar.subheader("Chart Settings")

# NEW: Chart Type Toggle
chart_type = st.sidebar.radio("Graph Type", ["Candlestick", "Line"])

timeframe_map = {
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
    "3 Years": 1095,
    "5 Years": 1825,
    "Max": None
}
tf_label = st.sidebar.selectbox("Chart View Range", list(timeframe_map.keys()))

# ================= DATA FETCH =================

@st.cache_data(ttl=3600)
def fetch_stock_data(symbol):
    # Only return DataFrame (Serializable)
    stock = yf.Ticker(symbol)
    df = stock.history(period="max")
    return df

# NEW: News Fetcher using Google RSS
def fetch_google_news(query):
    # Encode query for URL
    clean_query = query.replace(" ", "%20")
    rss_url = f"https://news.google.com/rss/search?q={clean_query}%20stock%20news%20India&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(rss_url)

# ================= ANALYSIS ENGINE =================

def run_analysis(symbol):
    
    # 1. Fetch Data
    df_full = fetch_stock_data(symbol)
    stock = yf.Ticker(symbol) # Re-init for info access

    if df_full.empty:
        st.error(f"No price data available for {symbol}")
        return

    # 2. Indicators
    df_full["EMA20"] = ta.ema(df_full["Close"], length=20)
    df_full["EMA50"] = ta.ema(df_full["Close"], length=50)
    df_full["EMA200"] = ta.ema(df_full["Close"], length=200)
    df_full["RSI"] = ta.rsi(df_full["Close"], length=14)

    latest = df_full.iloc[-1]
    price = latest["Close"]
    rsi = latest["RSI"]
    ema20 = latest["EMA20"]
    ema50 = latest["EMA50"]
    ema200 = latest["EMA200"]

    # 3. Scoring & Explanation Logic
    tech_score = 0
    reasons = [] # Store reasons for the summary
    
    # Technical Logic
    if horizon == "Short Term":
        if price > ema20: 
            tech_score += 2
            reasons.append("Price is above the 20-day EMA (Short-term Bullish).")
        else:
            reasons.append("Price is below the 20-day EMA (Short-term Bearish).")
            
        if 50 < rsi < 70: 
            tech_score += 2
            reasons.append(f"RSI is {round(rsi,1)} (Healthy momentum).")
        elif rsi >= 70:
            reasons.append(f"RSI is {round(rsi,1)} (Overbought - Caution).")
        else:
            reasons.append(f"RSI is {round(rsi,1)} (Weak momentum).")

    elif horizon == "Medium Term":
        if price > ema50: 
            tech_score += 2
            reasons.append("Price is above the 50-day EMA (Medium-term Bullish).")
        
        if ema50 > ema200: 
            tech_score += 2
            reasons.append("Golden Cross active (50 EMA > 200 EMA).")
        elif ema50 < ema200:
            reasons.append("Death Cross active (50 EMA < 200 EMA).")

    else:  # Long Term
        if price > ema200: 
            tech_score += 3
            reasons.append("Price is above the 200-day EMA (Long-term Bullish).")
        else:
            reasons.append("Price is below the 200-day EMA (Long-term Bearish).")
            
        if rsi < 70: 
            tech_score += 1

    # Fundamental Logic
    info = stock.info
    fund_score = 0
    
    roe = info.get("returnOnEquity", 0)
    debt_eq = info.get("debtToEquity", 1000) 
    peg = info.get("pegRatio", 5) 
    
    if roe > 0.15: 
        fund_score += 2
        reasons.append("ROE is strong (>15%).")
    
    if debt_eq < 100: 
        fund_score += 2
        reasons.append("Debt-to-Equity is healthy (<1).")
    
    if peg < 1.5: 
        fund_score += 3
        reasons.append("PEG Ratio indicates undervaluation (<1.5).")

    # Final Calculation
    final_score = (tech_score * tech_weight) + (fund_score * fund_weight)
    max_score = (4 * tech_weight) + (7 * fund_weight)
    normalized_score = (final_score / max_score) * 10
    
    if normalized_score >= 7: verdict = "🟢 BUY"
    elif normalized_score >= 4: verdict = "🟡 HOLD"
    else: verdict = "🔴 AVOID"

    # ================= UI LAYOUT =================

    # --- Header ---
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.subheader(f"{symbol.replace('.NS', '')}")
        st.caption(f"Sector: {info.get('sector', 'N/A')} | Industry: {info.get('industry', 'N/A')}")
    with c2:
        prev_close = df_full['Close'].iloc[-2]
        change = ((price - prev_close) / prev_close) * 100
        st.metric("Current Price", f"₹{round(price, 2)}", f"{round(change, 2)}%")
    with c3:
        st.metric("Algo Score", f"{round(normalized_score, 1)} / 10", verdict)

    # NEW: Analysis Summary
    with st.expander("📝 Analysis Summary (Why this score?)", expanded=True):
        for reason in reasons:
            st.write(f"- {reason}")

    st.markdown("---")

    # --- Chart Section (Conditional) ---
    st.subheader(f"📈 {chart_type} Chart")
    
    lookback = timeframe_map[tf_label]
    if lookback:
        chart_df = df_full.tail(lookback)
    else:
        chart_df = df_full

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Toggle between Candle and Line
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=chart_df.index,
                        open=chart_df['Open'], high=chart_df['High'],
                        low=chart_df['Low'], close=chart_df['Close'],
                        name='Price'), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['Close'],
                        mode='lines', name='Close Price',
                        line=dict(color='#00ff00', width=2)), row=1, col=1)

    # Indicators (Always visible)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA20'], 
                             line=dict(color='blue', width=1), name='EMA 20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA50'], 
                             line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA200'], 
                             line=dict(color='red', width=2), name='EMA 200'), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df['Volume'], 
                         marker_color='lightblue', name='Volume'), row=2, col=1)

    fig.update_layout(
        height=600, 
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, xanchor="left")
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # --- Shareholding ---
    st.markdown("### 👥 Shareholding Pattern")
    sh_col1, sh_col2 = st.columns(2)
    with sh_col1:
        try:
            major = stock.major_holders
            if major is not None and not major.empty:
                major.columns = ["Percentage", "Holder"]
                st.dataframe(major, hide_index=True, use_container_width=True)
            else:
                st.info("Major holder data unavailable.")
        except: st.info("Data unavailable.")

    with sh_col2:
        try:
            inst = stock.institutional_holders
            if inst is not None and not inst.empty:
                inst_clean = inst[["Holder", "Shares", "Date Reported", "% Out"]].copy()
                inst_clean.columns = ["Institution Name", "Shares", "Date", "% Holding"]
                inst_clean["% Holding"] = (inst_clean["% Holding"] * 100).round(2).astype(str) + "%"
                inst_clean["Date"] = pd.to_datetime(inst_clean["Date"]).dt.date
                st.dataframe(inst_clean, hide_index=True, use_container_width=True)
            else:
                st.info("Institutional data unavailable.")
        except: st.info("Institutional data unavailable.")

    # --- News Section (Google RSS) ---
    st.markdown("### 📰 Latest News")
    
    try:
        # Use company name for better results, fallback to symbol
        search_term = company_name if company_name else symbol
        feed = fetch_google_news(search_term)
        
        if feed.entries:
            for entry in feed.entries[:5]:
                with st.expander(f"{entry.title}"):
                    st.caption(f"Source: {entry.source.title} | {entry.published}")
                    st.write(f"[Read Article]({entry.link})")
        else:
            st.info("No recent news found on Google News.")
            
    except Exception as e:
        st.error(f"Error fetching news: {e}")

    # --- PDF Report ---
    if st.button("📄 Generate PDF Report"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            c = canvas.Canvas(f.name, pagesize=A4)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, 800, f"Research Report: {symbol}")
            c.setFont("Helvetica", 12)
            c.drawString(40, 770, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d')}")
            c.drawString(40, 750, f"Price: Rs. {round(price, 2)}")
            c.drawString(40, 730, f"Score: {round(normalized_score, 1)}/10 - {verdict}")
            
            y_pos = 700
            c.drawString(40, y_pos, "Key Drivers:")
            y_pos -= 20
            for r in reasons:
                c.drawString(50, y_pos, f"- {r}")
                y_pos -= 15
                
            c.save()
            st.success("PDF Generated!")
            st.download_button("Download PDF", open(f.name, "rb"), file_name=f"{symbol}_report.pdf")

# ================= RUN =================

if st.button("🚀 Run Analysis", type="primary"):
    run_analysis(symbol)
