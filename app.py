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

# ================= PAGE SETUP =================

st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("Yahoo Finance | Technical + Fundamental | Research Tool")

# ================= NSE STOCK LIST =================

@st.cache_data(ttl=86400)
def load_nse_list():
    # Helper to get valid NSE symbols
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    try:
        df = pd.read_csv(url)
        df["symbol"] = df["SYMBOL"] + ".NS"
        df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
        return df[["symbol", "display"]]
    except Exception as e:
        # Fallback if NSE server is busy
        return pd.DataFrame(columns=["symbol", "display"])

nse_df = load_nse_list()

if not nse_df.empty:
    selected = st.selectbox("🔎 Search NSE Stock", nse_df["display"])
    symbol = nse_df.loc[nse_df["display"] == selected, "symbol"].values[0]
else:
    symbol = st.text_input("Enter Symbol (e.g., RELIANCE.NS)", "RELIANCE.NS")

# ================= SIDEBAR CONTROLS =================

st.sidebar.header("⚙️ Controls")

# Analysis parameters (Independent of chart view)
horizon = st.sidebar.selectbox(
    "Investment Horizon",
    ["Short Term", "Medium Term", "Long Term"]
)

tech_weight = st.sidebar.slider("Technical Weight", 0.0, 1.0, 0.6, 0.05)
fund_weight = st.sidebar.slider("Fundamental Weight", 0.0, 1.0, 0.4, 0.05)

# Chart specific controls
st.sidebar.markdown("---")
st.sidebar.subheader("Chart Settings")
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

# ================= DATA FETCH (FIXED) =================

@st.cache_data(ttl=3600)
def fetch_stock_data(symbol):
    # We ONLY return the DataFrame here to avoid caching errors
    stock = yf.Ticker(symbol)
    df = stock.history(period="max")
    return df

# ================= ANALYSIS ENGINE =================

def run_analysis(symbol):
    
    # 1. Fetch Full Data (Cached)
    df_full = fetch_stock_data(symbol)
    
    # Re-initialize Ticker here (Fast operation, safe to run every time)
    stock = yf.Ticker(symbol)

    if df_full.empty:
        st.error(f"No price data available for {symbol}")
        return

    # 2. Calculate Indicators on FULL Data
    # Ensure indices are aligned
    df_full["EMA20"] = ta.ema(df_full["Close"], length=20)
    df_full["EMA50"] = ta.ema(df_full["Close"], length=50)
    df_full["EMA200"] = ta.ema(df_full["Close"], length=200)
    df_full["RSI"] = ta.rsi(df_full["Close"], length=14)

    # Get the latest values for Scoring
    latest = df_full.iloc[-1]
    price = latest["Close"]
    rsi = latest["RSI"]
    ema20 = latest["EMA20"]
    ema50 = latest["EMA50"]
    ema200 = latest["EMA200"]

    # 3. Calculate Technical Score
    tech_score = 0
    if horizon == "Short Term":
        if price > ema20: tech_score += 2
        if 50 < rsi < 70: tech_score += 2
    elif horizon == "Medium Term":
        if price > ema50: tech_score += 2
        if ema50 > ema200: tech_score += 2
    else:  # Long Term
        if price > ema200: tech_score += 3
        if rsi < 70: tech_score += 1

    # 4. Calculate Fundamental Score
    info = stock.info
    fund_score = 0
    
    roe = info.get("returnOnEquity", 0)
    debt_eq = info.get("debtToEquity", 1000) 
    peg = info.get("pegRatio", 5) 
    
    if roe > 0.15: fund_score += 2
    if debt_eq < 100: fund_score += 2 
    if peg < 1.5: fund_score += 3

    # 5. Final Verdict
    final_score = (tech_score * tech_weight) + (fund_score * fund_weight)
    max_score = (4 * tech_weight) + (7 * fund_weight)
    normalized_score = (final_score / max_score) * 10
    
    if normalized_score >= 7: verdict = "🟢 BUY"
    elif normalized_score >= 4: verdict = "🟡 HOLD"
    else: verdict = "🔴 AVOID"

    # ================= UI LAYOUT =================

    # --- Header Section ---
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

    st.markdown("---")

    # --- Chart Section (Plotly) ---
    st.subheader("📈 Technical Chart")
    
    lookback = timeframe_map[tf_label]
    if lookback:
        chart_df = df_full.tail(lookback)
    else:
        chart_df = df_full

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Candlestick
    fig.add_trace(go.Candlestick(x=chart_df.index,
                    open=chart_df['Open'], high=chart_df['High'],
                    low=chart_df['Low'], close=chart_df['Close'],
                    name='Price'), row=1, col=1)

    # EMAs
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

    # --- Shareholding Section ---
    st.markdown("### 👥 Shareholding Pattern")
    
    sh_col1, sh_col2 = st.columns(2)
    
    with sh_col1:
        st.markdown("**Ownership Breakdown**")
        try:
            major = stock.major_holders
            if major is not None and not major.empty:
                major.columns = ["Percentage", "Holder"]
                st.dataframe(major, hide_index=True, use_container_width=True)
            else:
                st.info("Major holder data unavailable.")
        except:
            st.info("Data unavailable.")

    with sh_col2:
        st.markdown("**Top Institutional Holders**")
        try:
            inst = stock.institutional_holders
            if inst is not None and not inst.empty:
                inst_clean = inst[["Holder", "Shares", "Date Reported", "% Out"]].copy()
                inst_clean.columns = ["Institution Name", "Shares", "Date", "% Holding"]
                inst_clean["% Holding"] = (inst_clean["% Holding"] * 100).round(2).astype(str) + "%"
                inst_clean["Date"] = pd.to_datetime(inst_clean["Date"]).dt.date
                st.dataframe(inst_clean, hide_index=True, use_container_width=True)
            else:
                st.warning("No Institutional Holders found.")
        except:
            st.info("Institutional data unavailable.")

    # --- News Section ---
    st.markdown("### 📰 Latest News")
    
    try:
        news_list = stock.news
        if news_list:
            for article in news_list[:5]:
                with st.expander(f"{article.get('title', 'No Title')}"):
                    if 'providerPublishTime' in article:
                        pub_date = datetime.datetime.fromtimestamp(article['providerPublishTime']).strftime('%Y-%m-%d %H:%M')
                        st.caption(f"Source: {article.get('publisher', 'Unknown')} | {pub_date}")
                    
                    col_txt, col_img = st.columns([3, 1])
                    with col_txt:
                        st.write(f"[Read Full Article]({article['link']})")
                    with col_img:
                        if 'thumbnail' in article and 'resolutions' in article['thumbnail']:
                            st.image(article['thumbnail']['resolutions'][0]['url'], use_column_width=True)
        else:
            st.info("No news articles found.")
    except:
        st.info("News data unavailable.")

    # --- PDF Report ---
    if st.button("📄 Generate PDF Report"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            c = canvas.Canvas(f.name, pagesize=A4)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(40, 800, f"Research Report: {symbol}")
            c.setFont("Helvetica", 12)
            c.drawString(40, 770, f"Date: {datetime.datetime.now().strftime('%Y-%m-%d')}")
            c.drawString(40, 750, f"Price: Rs. {round(price, 2)}")
            c.drawString(40, 730, f"Score: {round(normalized_score, 1)}/10")
            c.drawString(40, 710, f"Verdict: {verdict}")
            c.save()
            st.success("PDF Generated!")
            st.download_button("Download PDF", open(f.name, "rb"), file_name=f"{symbol}_report.pdf")

# ================= RUN =================

if st.button("🚀 Run Analysis", type="primary"):
    run_analysis(symbol)
