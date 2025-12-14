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
st.caption("NSE & BSE | Technical + Fundamental | Internal Research Tool")

# ------------------ LOAD NSE + BSE MASTER LIST ------------------

@st.cache_data(ttl=86400)
def load_stock_master():
    nse = pd.read_csv(
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    )
    nse["symbol"] = nse["SYMBOL"] + ".NS"
    nse["display"] = nse["SYMBOL"] + " – " + nse["NAME OF COMPANY"]

    return nse[["symbol", "display"]]

stock_master = load_stock_master()

# ------------------ UI: STOCK SEARCH ------------------

selected = st.selectbox(
    "🔎 Search NSE Stock (Ticker or Name)",
    stock_master["display"]
)

symbol = stock_master.loc[
    stock_master["display"] == selected, "symbol"
].values[0]

# ------------------ WEIGHT CONTROLS ------------------

st.sidebar.header("⚖️ Scoring Weights")
tech_weight = st.sidebar.slider("Technical Weight", 0.0, 1.0, 0.6)
fund_weight = st.sidebar.slider("Fundamental Weight", 0.0, 1.0, 0.4)

horizon = st.sidebar.selectbox(
    "Investment Horizon",
    ["Short Term", "Medium Term", "Long Term"]
)

# ------------------ DATA FETCH ------------------

@st.cache_data(ttl=3600)
def fetch_data(symbol):
    stock = yf.Ticker(symbol)
    df = stock.history(period="2y")
    return df, stock

# ------------------ ANALYSIS ------------------

def run_analysis(symbol):
    df, stock = fetch_data(symbol)

    if df.empty:
        st.error("No data available")
        return

    # Indicators
    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)

    price = df["Close"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    # Technical score
    tech_score = 0
    if price > df["EMA50"].iloc[-1]:
        tech_score += 2
    if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]:
        tech_score += 2
    if rsi < 75:
        tech_score += 1

    # Fundamental score
    info = stock.info
    fund_score = 0
    if info.get("returnOnEquity", 0) > 0.15:
        fund_score += 3
    if info.get("debtToEquity", 2) < 1:
        fund_score += 2
    if info.get("pegRatio", 2) and info["pegRatio"] < 1:
        fund_score += 3

    final_score = (tech_score * tech_weight) + (fund_score * fund_weight)

    # ------------------ OUTPUT ------------------

    st.subheader(f"{symbol.replace('.NS','')}")
    st.metric("Current Price", f"₹{round(price,2)}")
    st.metric("Final Conviction Score", round(final_score, 2))

    # ------------------ PRICE CHART ------------------

    st.markdown("### 📈 Price & EMA Chart")
    chart_df = df[["Close", "EMA20", "EMA50", "EMA200"]].dropna()
    st.line_chart(chart_df)

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
        st.info("No recent news")

    # ------------------ PDF EXPORT ------------------

    if st.button("📄 Download PDF Report"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            c = canvas.Canvas(f.name, pagesize=A4)
            c.drawString(40, 800, f"Stock Report: {symbol}")
            c.drawString(40, 780, f"Price: ₹{round(price,2)}")
            c.drawString(40, 760, f"Final Score: {round(final_score,2)}")
            c.drawString(40, 740, f"Sector: {sector}")
            c.save()
            st.download_button(
                "Download PDF",
                open(f.name, "rb"),
                file_name=f"{symbol}_report.pdf"
            )

# ------------------ RUN ------------------

if st.button("Run Full Analysis"):
    run_analysis(symbol)

