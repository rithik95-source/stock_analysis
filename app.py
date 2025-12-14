import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile

# ------------------ PAGE SETUP ------------------

st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("NSE Stocks | Technical + Fundamental | Research Tool")

# ------------------ LOAD NSE STOCK MASTER ------------------

@st.cache_data(ttl=86400)
def load_nse_stock_master():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    df["symbol"] = df["SYMBOL"] + ".NS"
    df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
    return df[["symbol", "display"]]

stock_master = load_nse_stock_master()

# ------------------ UI: STOCK SEARCH ------------------

selected_stock = st.selectbox(
    "🔎 Search NSE Stock (Ticker or Company Name)",
    stock_master["display"]
)

symbol = stock_master.loc[
    stock_master["display"] == selected_stock, "symbol"
].values[0]

# ------------------ SIDEBAR CONTROLS ------------------

st.sidebar.header("⚙️ Controls")

timeframe_map = {
    "1 Day": "1d",
    "7 Days": "7d",
    "1 Month": "1mo",
    "3 Months": "3mo",
    "6 Months": "6mo",
    "1 Year": "1y",
    "3 Years": "3y",
    "All": "max"
}

timeframe_label = st.sidebar.selectbox(
    "Price Timeframe",
    list(timeframe_map.keys()),
    index=5
)

period = timeframe_map[timeframe_label]

tech_weight = st.sidebar.slider("Technical Weight", 0.0, 1.0, 0.6, 0.05)
fund_weight = st.sidebar.slider("Fundamental Weight", 0.0, 1.0, 0.4, 0.05)

# ------------------ DATA FETCH ------------------

@st.cache_data(ttl=3600)
def fetch_price_data(symbol, period):
    stock = yf.Ticker(symbol)
    df = stock.history(period=period)
    return df

# ------------------ ANALYSIS ------------------

def run_analysis(symbol, period):

    df = fetch_price_data(symbol, period)
    stock = yf.Ticker(symbol)

    if df.empty:
        st.error("No price data available")
        return

    # ------------------ INDICATORS ------------------

    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)

    price = df["Close"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    # ------------------ TECHNICAL SCORE ------------------

    tech_score = 0
    if price > df["EMA20"].iloc[-1]:
        tech_score += 1
    if price > df["EMA50"].iloc[-1]:
        tech_score += 2
    if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]:
        tech_score += 2
    if rsi < 75:
        tech_score += 1

    # ------------------ FUNDAMENTAL SCORE ------------------

    info = stock.info
    fund_score = 0

    if info.get("returnOnEquity", 0) > 0.15:
        fund_score += 2
    if info.get("debtToEquity", 2) < 1:
        fund_score += 2
    peg = info.get("pegRatio")
    if peg and peg < 1:
        fund_score += 3

    # ------------------ FINAL SCORE & RATING ------------------

    final_score = (tech_score * tech_weight) + (fund_score * fund_weight)

    if final_score >= 7:
        rating = "🟢 BUY"
    elif final_score >= 4:
        rating = "🟡 HOLD"
    else:
        rating = "🔴 AVOID"

    # ------------------ OUTPUT ------------------

    st.subheader(f"📈 {symbol.replace('.NS','')}")
    st.metric("Current Price", f"₹{round(price,2)}")
    st.metric("Final Score", round(final_score, 2))
    st.markdown(f"## Final Rating: **{rating}**")

    # ------------------ PRICE CHART ------------------

    st.markdown("### 📊 Price & EMA Chart")
    st.line_chart(df[["Close", "EMA20", "EMA50", "EMA200"]].dropna())

    # ------------------ SHAREHOLDING ------------------

    st.markdown("### 👥 Shareholding Snapshot (Yahoo Finance)")

    try:
        holders = stock.institutional_holders
        major = stock.major_holders

        if major is not None:
            st.write("**Major Holders (%)**")
            st.dataframe(major)

        if holders is not None:
            st.write("**Institutional Holders**")
            st.dataframe(holders)

        st.caption("Note: Indian promoter holding history is not publicly available via free APIs.")

    except:
        st.info("Shareholding data not available")

    # ------------------ NEWS ------------------

    st.markdown("### 📰 Latest News")

    try:
        for n in stock.news[:5]:
            st.markdown(f"**{n['title']}**")
            st.caption(n["publisher"])
            st.markdown(f"[Read more]({n['link']})")
    except:
        st.info("No recent news available")

    # ------------------ PDF EXPORT ------------------

    st.markdown("---")
    if st.button("📄 Download PDF Report"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            c = canvas.Canvas(f.name, pagesize=A4)
            c.drawString(40, 800, f"Stock Report: {symbol}")
            c.drawString(40, 780, f"Price: ₹{round(price,2)}")
            c.drawString(40, 760, f"Score: {round(final_score,2)}")
            c.drawString(40, 740, f"Rating: {rating}")
            c.save()

            st.download_button(
                "⬇️ Download PDF",
                open(f.name, "rb"),
                file_name=f"{symbol}_report.pdf"
            )

# ------------------ RUN ------------------

if st.button("Run Analysis"):
    run_analysis(symbol, period)

