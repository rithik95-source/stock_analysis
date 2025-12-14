import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile

# ================= PAGE SETUP =================

st.set_page_config(page_title="Indian Stock Research Platform", layout="wide")
st.title("📊 Indian Stock Research Platform")
st.caption("Yahoo Finance | Technical + Fundamental | Research Tool")

# ================= NSE STOCK LIST =================

@st.cache_data(ttl=86400)
def load_nse_list():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    df = pd.read_csv(url)
    df["symbol"] = df["SYMBOL"] + ".NS"
    df["display"] = df["SYMBOL"] + " – " + df["NAME OF COMPANY"]
    return df[["symbol", "display"]]

nse_df = load_nse_list()

selected = st.selectbox("🔎 Search NSE Stock", nse_df["display"])
symbol = nse_df.loc[nse_df["display"] == selected, "symbol"].values[0]

# ================= SIDEBAR CONTROLS =================

st.sidebar.header("⚙️ Controls")

horizon = st.sidebar.selectbox(
    "Investment Horizon",
    ["Short Term", "Medium Term", "Long Term"]
)

tech_weight = st.sidebar.slider("Technical Weight", 0.0, 1.0, 0.6, 0.05)
fund_weight = st.sidebar.slider("Fundamental Weight", 0.0, 1.0, 0.4, 0.05)

timeframe_map = {
    "1D": 1,
    "7D": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "3Y": 1095,
    "ALL": None
}

tf_label = st.sidebar.selectbox("Chart Timeframe", list(timeframe_map.keys()))

# ================= DATA FETCH =================

@st.cache_data(ttl=3600)
def fetch_max_price(symbol):
    stock = yf.Ticker(symbol)
    return stock.history(period="max")

# ================= ANALYSIS =================

def run_analysis(symbol):

    df = fetch_max_price(symbol)
    stock = yf.Ticker(symbol)

    if df.empty:
        st.error("No price data available")
        return

    # -------- FILTER DATA FOR CHART --------
    if timeframe_map[tf_label]:
        df = df.tail(timeframe_map[tf_label])

    # -------- INDICATORS --------
    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)

    price = df["Close"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    # -------- TECHNICAL SCORE --------
    tech_score = 0

    if horizon == "Short Term":
        if price > df["EMA20"].iloc[-1]: tech_score += 2
        if 50 < rsi < 70: tech_score += 2

    elif horizon == "Medium Term":
        if price > df["EMA50"].iloc[-1]: tech_score += 2
        if df["EMA50"].iloc[-1] > df["EMA200"].iloc[-1]: tech_score += 2

    else:  # Long Term
        if price > df["EMA200"].iloc[-1]: tech_score += 3

    # -------- FUNDAMENTAL SCORE --------
    info = stock.info
    fund_score = 0

    if info.get("returnOnEquity", 0) > 0.15: fund_score += 2
    if info.get("debtToEquity", 2) < 1: fund_score += 2
    if info.get("pegRatio") and info["pegRatio"] < 1: fund_score += 3

    # -------- FINAL SCORE & RATING --------
    final_score = tech_score * tech_weight + fund_score * fund_weight

    if final_score >= 7:
        verdict = "🟢 BUY"
    elif final_score >= 4:
        verdict = "🟡 HOLD"
    else:
        verdict = "🔴 AVOID"

    # ================= OUTPUT =================

    st.subheader(symbol.replace(".NS", ""))
    st.metric("Current Price", f"₹{round(price,2)}")
    st.metric("Final Score", round(final_score, 2))
    st.markdown(f"## Final Rating: **{verdict}**")

    # -------- PRICE CHART --------
    st.markdown("### 📈 Price & EMA Chart")
    st.line_chart(df[["Close", "EMA20", "EMA50", "EMA200"]].dropna())

    # -------- SHAREHOLDING SNAPSHOT --------
    st.markdown("### 👥 Shareholding Snapshot (Yahoo Finance)")

    try:
        major = stock.major_holders
        inst = stock.institutional_holders

        if major is not None and not major.empty:
            major.columns = ["Value"]
            st.markdown("**Major Holders (%)**")
            st.dataframe(major)

        if inst is not None and not inst.empty:
            st.markdown("**Institutional Holders**")

            inst_disp = inst.rename(columns={
                "Shares": "Shares Held",
                "Value": "Holding Value",
                "% Out": "% Outstanding",
                "Date Reported": "Reported Date"
            })

            st.dataframe(inst_disp)

            if "Reported Date" in inst_disp.columns:
                dates = pd.to_datetime(inst_disp["Reported Date"], errors="coerce")
                if dates.notna().sum() > 1:
                    latest = inst_disp.iloc[0]
                    prev = inst_disp.iloc[1]
                    change = latest["% Outstanding"] - prev["% Outstanding"]
                    st.write(
                        f"📌 Institutional holding changed by "
                        f"**{round(change,2)}%** since last reported period."
                    )
                else:
                    st.caption("Historical change not available.")
        else:
            st.caption("Institutional holding data not available.")

    except:
        st.info("Shareholding data not available.")

    # -------- NEWS --------
    st.markdown("### 📰 Latest News")
    try:
        for n in stock.news[:5]:
            st.markdown(f"**{n['title']}**")
            st.caption(n["publisher"])
            st.markdown(f"[Read more]({n['link']})")
    except:
        st.info("No recent news available")

    # -------- PDF EXPORT --------
    if st.button("📄 Download PDF Report"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            c = canvas.Canvas(f.name, pagesize=A4)
            c.drawString(40, 800, f"Stock: {symbol}")
            c.drawString(40, 780, f"Price: ₹{round(price,2)}")
            c.drawString(40, 760, f"Score: {round(final_score,2)}")
            c.drawString(40, 740, f"Rating: {verdict}")
            c.save()

            st.download_button(
                "⬇️ Download PDF",
                open(f.name, "rb"),
                file_name=f"{symbol}_report.pdf"
            )

# ================= RUN =================

if st.button("Run Analysis"):
    run_analysis(symbol)

