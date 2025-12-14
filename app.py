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
st.caption("NSE Stocks | Technical + Fundamental | Free Research Tool")

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

st.sidebar.header("⚖️ Scoring Controls")

tech_weight = st.sidebar.slider(
    "Technical Weight", 0.0, 1.0, 0.6, step=0.05
)

fund_weight = st.sidebar.slider(
    "Fundamental Weight", 0.0, 1.0, 0.4, step=0.05
)

horizon = st.sidebar.selectbox(
    "Investment Horizon",
    ["Short Term", "Medium Term", "Long Term"]
)

# ------------------ DATA FETCH (CACHE SAFE) ------------------

@st.cache_data(ttl=3600)
def fetch_price_data(symbol):
    stock = yf.Ticker(symbol)
    df = stock.history(period="2y")
    return df

# ------------------ ANALYSIS ENGINE ------------------

def run_analysis(symbol):

    df = fetch_price_data(symbol)
    stock = yf.Ticker(symbol)  # DO NOT CACHE THIS

    if df.empty:
        st.error("❌ No price data available.")
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
    tech_log = []

    if price > df["EMA20"].iloc[-1]:
        tech_score += 1
        tech_log.append("Price above EMA 20")

    if price > df["EMA50"].iloc[-1]:
        tech_score += 2
        tech_log.append("Price above EMA 50")

    if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]:
        tech_score += 2
        tech_log.append("Golden Cross")

    if rsi < 75:
        tech_score += 1
        tech_log.append("RSI in safe zone")

    # ------------------ FUNDAMENTAL SCORE ------------------

    info = stock.info
    fund_score = 0
    fund_log = []

    if info.get("returnOnEquity", 0) > 0.15:
        fund_score += 2
        fund_log.append("Strong ROE")

    if info.get("debtToEquity", 2) < 1:
        fund_score += 2
        fund_log.append("Low Debt")

    peg = info.get("pegRatio")
    if peg and peg < 1:
        fund_score += 3
        fund_log.append("Attractive PEG")

    # ------------------ FINAL SCORE ------------------

    final_score = (tech_score * tech_weight) + (fund_score * fund_weight)

    # ------------------ OUTPUT ------------------

    st.subheader(f"📈 {symbol.replace('.NS','')}")
    st.metric("Current Price", f"₹{round(price,2)}")
    st.metric("Final Conviction Score", round(final_score, 2))

    # ------------------ PRICE CHART ------------------

    st.markdown("### 📊 Price & EMA Chart")
    chart_df = df[["Close", "EMA20", "EMA50", "EMA200"]].dropna()
    st.line_chart(chart_df)

    # ------------------ TECH & FUND DETAILS ------------------

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🛠 Technicals")
        for t in tech_log:
            st.write("✅", t)

    with col2:
        st.markdown("### 📘 Fundamentals")
        for f in fund_log:
            st.write("✅", f)

    # ------------------ SECTOR INFO ------------------

    st.markdown("### 🏭 Sector Information")
    sector = info.get("sector", "Unknown")
    st.write(f"**Sector:** {sector}")

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
    if st.button("📄 Generate PDF Report"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            c = canvas.Canvas(f.name, pagesize=A4)
            c.drawString(40, 800, f"Stock Report: {symbol}")
            c.drawString(40, 780, f"Price: ₹{round(price,2)}")
            c.drawString(40, 760, f"Final Score: {round(final_score,2)}")
            c.drawString(40, 740, f"Sector: {sector}")
            c.save()

            st.download_button(
                "⬇️ Download PDF",
                open(f.name, "rb"),
                file_name=f"{symbol}_report.pdf"
            )

# ------------------ RUN ------------------

if st.button("Run Full Analysis"):
    run_analysis(symbol)
