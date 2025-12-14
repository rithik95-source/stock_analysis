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

# ================= NSE STOCK LIST =================

@st.cache_data(ttl=86400)
def load_nse_list():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    try:
        df = pd.read_csv(url)
        df["symbol"] = df["SYMBOL"] 
        df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
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
    symbol = st.text_input("Enter Symbol (e.g., RELIANCE)", "RELIANCE")
    company_name = symbol

# ================= SIDEBAR CONTROLS =================

st.sidebar.header("⚙️ Controls")

horizon = st.sidebar.selectbox(
    "Investment Horizon",
    ["Short Term", "Medium Term", "Long Term"]
)

tech_weight = st.sidebar.slider("Technical Weight", 0.0, 1.0, 0.6, 0.05)
fund_weight = st.sidebar.slider("Fundamental Weight", 0.0, 1.0, 0.4, 0.05)

st.sidebar.markdown("---")
st.sidebar.subheader("Chart Settings")
chart_type = st.sidebar.radio("Graph Type", ["Candlestick", "Line"])

timeframe_map = {
    "1 Month": "1M",
    "6 Months": "6M",
    "1 Year": "1Y"
}
tf_label = st.sidebar.selectbox("Chart View Range", list(timeframe_map.keys()))

# ================= DATA FETCH =================

@st.cache_data(ttl=3600)
def fetch_price_data_nse(symbol):
    try:
        # Fetching 1 Year of data for calculation (Using '1Y' string as approx)
        # nselib requires specific dates or period strings. 
        # We fetch 1Y to ensure enough data for EMA200 calculation.
        end_date = datetime.datetime.now().strftime("%d-%m-%Y")
        start_date = (datetime.datetime.now() - datetime.timedelta(days=400)).strftime("%d-%m-%Y")
        
        # Use nselib to get official data
        data = capital_market.price_volume_and_deliverable_position_data(symbol=symbol, from_date=start_date, to_date=end_date)
        
        # Clean and Format Data
        data['Date'] = pd.to_datetime(data['Date'], format='%d-%b-%Y')
        data = data.sort_values('Date')
        data.set_index('Date', inplace=True)
        
        # Convert columns to numeric (remove commas if any)
        cols = ['OpenPrice', 'HighPrice', 'LowPrice', 'ClosePrice', 'TotalTradedQuantity']
        for col in cols:
            data[col] = pd.to_numeric(data[col].astype(str).str.replace(',', ''), errors='coerce')
            
        # Rename to standard names for analysis
        data = data.rename(columns={
            'OpenPrice': 'Open',
            'HighPrice': 'High', 
            'LowPrice': 'Low', 
            'ClosePrice': 'Close',
            'TotalTradedQuantity': 'Volume'
        })
        
        return data
    except Exception as e:
        return pd.DataFrame()

# Fallback/Fundamental Data (Yahoo)
@st.cache_data(ttl=3600)
def fetch_fundamentals(symbol):
    # Yahoo requires .NS extension
    stock = yf.Ticker(f"{symbol}.NS")
    return stock

# Google News Fetcher
def fetch_google_news(query):
    clean_query = query.replace(" ", "%20")
    rss_url = f"https://news.google.com/rss/search?q={clean_query}%20stock%20news%20India&hl=en-IN&gl=IN&ceid=IN:en"
    return feedparser.parse(rss_url)

# ================= ANALYSIS ENGINE =================

def run_analysis(symbol):
    
    # 1. Fetch Price Data (Official NSE)
    with st.spinner('Fetching Official NSE Data...'):
        df_full = fetch_price_data_nse(symbol)
    
    if df_full.empty:
        st.error(f"Could not fetch official NSE data for {symbol}. Try again later or check symbol.")
        return

    # 2. Fetch Fundamentals (Yahoo)
    stock_fund = fetch_fundamentals(symbol)
    info = stock_fund.info

    # 3. Indicators
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

    # 4. Scoring & Pros/Cons Logic
    tech_score = 0
    fund_score = 0
    pros = []
    cons = []

    # --- Technical Analysis ---
    if horizon == "Short Term":
        if price > ema20:
            tech_score += 2
            pros.append("Price > 20 EMA (Short-term Bullish trend)")
        else:
            cons.append("Price < 20 EMA (Short-term Bearish trend)")
            
        if 50 < rsi < 70:
            tech_score += 2
            pros.append(f"RSI is {round(rsi,1)} (Healthy Momentum)")
        elif rsi >= 70:
            cons.append(f"RSI is {round(rsi,1)} (Overbought - High Risk)")
        else:
            cons.append(f"RSI is {round(rsi,1)} (Weak Momentum)")

    elif horizon == "Medium Term":
        if price > ema50:
            tech_score += 2
            pros.append("Price > 50 EMA (Medium-term Bullish)")
        else:
            cons.append("Price < 50 EMA (Medium-term Bearish)")
        
        if ema50 > ema200:
            tech_score += 2
            pros.append("Golden Cross (50 EMA > 200 EMA)")
        else:
            cons.append("Death Cross (50 EMA < 200 EMA)")

    else:  # Long Term
        if price > ema200:
            tech_score += 3
            pros.append("Price > 200 EMA (Long-term Bullish)")
        else:
            cons.append("Price < 200 EMA (Long-term Bearish)")
            
        if rsi < 70:
            tech_score += 1

    # --- Fundamental Analysis ---
    # Note: Using default values carefully to avoid false positives
    roe = info.get("returnOnEquity", 0)
    debt_eq = info.get("debtToEquity", 1000) 
    peg = info.get("pegRatio", 5) 

    if roe > 0.15: 
        fund_score += 2
        pros.append(f"Strong ROE: {round(roe*100, 2)}%")
    else:
        cons.append(f"Low ROE: {round(roe*100, 2)}% (Target > 15%)")
    
    if debt_eq < 100: 
        fund_score += 2
        pros.append("Low Debt-to-Equity Ratio")
    else:
        cons.append("High Debt-to-Equity Ratio")
    
    if peg < 1.5: 
        fund_score += 3
        pros.append(f"Undervalued (PEG Ratio: {peg})")
    elif peg > 3:
        cons.append(f"Overvalued (PEG Ratio: {peg})")

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
        st.subheader(f"{symbol}")
        st.caption(f"Sector: {info.get('sector', 'N/A')} | Data Source: NSE Official")
    with c2:
        prev_close = df_full['Close'].iloc[-2]
        change = ((price - prev_close) / prev_close) * 100
        st.metric("Current Price", f"₹{round(price, 2)}", f"{round(change, 2)}%")
    with c3:
        st.metric("Algo Score", f"{round(normalized_score, 1)} / 10", verdict)

    # --- Pros & Cons ---
    col_p, col_c = st.columns(2)
    with col_p:
        st.success("✅ POSITIVES (Pros)")
        if pros:
            for p in pros: st.write(f"• {p}")
        else:
            st.write("No major positive signals detected.")
            
    with col_c:
        st.error("❌ NEGATIVES (Cons)")
        if cons:
            for c in cons: st.write(f"• {c}")
        else:
            st.write("No major negative signals detected.")

    st.markdown("---")

    # --- Chart Section ---
    st.subheader(f"📈 {chart_type} Chart (Official NSE)")
    
    # Filter for view
    view_days = 30 if tf_label == "1 Month" else 180 if tf_label == "6 Months" else 365
    chart_df = df_full.tail(view_days)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(x=chart_df.index,
                        open=chart_df['Open'], high=chart_df['High'],
                        low=chart_df['Low'], close=chart_df['Close'],
                        name='Price'), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['Close'],
                        mode='lines', name='Close Price',
                        line=dict(color='#00ff00', width=2)), row=1, col=1)

    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA20'], line=dict(color='blue', width=1), name='EMA 20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA50'], line=dict(color='orange', width=1), name='EMA 50'), row=1, col=1)
    fig.add_trace(go.Scatter(x=chart_df.index, y=chart_df['EMA200'], line=dict(color='red', width=2), name='EMA 200'), row=1, col=1)
    fig.add_trace(go.Bar(x=chart_df.index, y=chart_df['Volume'], marker_color='lightblue', name='Volume'), row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(l=0, r=0, t=0, b=0), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

    # --- News Section ---
    st.markdown("### 📰 Latest News")
    try:
        search_term = company_name if company_name else symbol
        feed = fetch_google_news(search_term)
        if feed.entries:
            for entry in feed.entries[:5]:
                with st.expander(f"{entry.title}"):
                    st.caption(f"Source: {entry.source.title} | {entry.published}")
                    st.write(f"[Read Article]({entry.link})")
        else:
            st.info("No recent news found.")
    except:
        st.error("Error fetching news.")

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
            
            y = 700
            c.drawString(40, y, "Positives:")
            y -= 20
            for p in pros:
                c.drawString(50, y, f"+ {p}")
                y -= 15
            
            y -= 20
            c.drawString(40, y, "Negatives:")
            y -= 20
            for con in cons:
                c.drawString(50, y, f"- {con}")
                y -= 15
                
            c.save()
            st.success("PDF Generated!")
            st.download_button("Download PDF", open(f.name, "rb"), file_name=f"{symbol}_report.pdf")

# ================= RUN =================

if st.button("🚀 Run Analysis", type="primary"):
    run_analysis(symbol)
