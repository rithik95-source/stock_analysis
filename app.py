import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# ------------------ PAGE SETUP ------------------

st.set_page_config(
    page_title="Indian Stock Analysis",
    layout="centered"
)

st.title("📊 Indian Stock Analysis Tool")
st.caption("Technical + Fundamental Conviction Model")

# ------------------ DATA FETCH ------------------

def get_indian_stock_data(symbol):
    symbol = symbol.upper().replace(" ", "")
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        symbol = f"{symbol}.NS"

    stock = yf.Ticker(symbol)
    df = stock.history(period="2y")
    return df, stock, symbol

# ------------------ FUNDAMENTAL ANALYSIS ------------------

def analyze_fundamentals(stock):
    info = stock.info
    cashflow = stock.cashflow
    balance = stock.balance_sheet

    score = 0
    log = []

    pe = info.get("trailingPE")
    if pe and pe < 25:
        score += 1
        log.append(f"✅ P/E reasonable ({round(pe,1)})")

    peg = info.get("pegRatio")
    if peg and peg < 1:
        score += 2
        log.append(f"✅ PEG attractive ({round(peg,2)})")
    elif peg and peg < 2:
        score += 1
        log.append(f"⚠️ PEG moderate ({round(peg,2)})")

    pb = info.get("priceToBook")
    if pb and pb < 1:
        score += 2
        log.append(f"✅ Undervalued (P/B {round(pb,2)})")
    elif pb and pb < 3:
        score += 1
        log.append(f"⚠️ Fair valuation (P/B {round(pb,2)})")

    roe = info.get("returnOnEquity")
    if roe and roe > 0.15:
        score += 2
        log.append(f"✅ Strong ROE ({round(roe*100,1)}%)")
    elif roe and roe > 0.08:
        score += 1
        log.append(f"⚠️ Average ROE ({round(roe*100,1)}%)")

    try:
        debt = balance.loc["Total Debt"].iloc[0]
        equity = balance.loc["Total Stockholder Equity"].iloc[0]
        if debt / equity < 1:
            score += 1
            log.append("✅ Healthy Debt-to-Equity")
    except:
        pass

    try:
        if cashflow.loc["Total Cash From Operating Activities"].iloc[0] > 0:
            score += 1
            log.append("✅ Positive Operating Cash Flow")
    except:
        pass

    return score, log

# ------------------ TECHNICAL ANALYSIS ------------------

def analyze_stock(symbol, horizon):
    df, stock, ticker = get_indian_stock_data(symbol)

    if df.empty:
        st.error("❌ No price data found.")
        return

    df["EMA20"] = ta.ema(df["Close"], 20)
    df["EMA50"] = ta.ema(df["Close"], 50)
    df["EMA200"] = ta.ema(df["Close"], 200)
    df["RSI"] = ta.rsi(df["Close"], 14)

    price = df["Close"].iloc[-1]
    ema20 = df["EMA20"].iloc[-1]
    ema50 = df["EMA50"].iloc[-1]
    ema200 = df["EMA200"].iloc[-1]
    rsi = df["RSI"].iloc[-1]

    tech_score = 0
    tech_log = []

    if horizon == "Short Term":
        if price > ema20:
            tech_score += 2
            tech_log.append("✅ Price above 20 EMA")
        if 50 < rsi < 70:
            tech_score += 2
            tech_log.append("✅ Healthy RSI momentum")
        if df["Volume"].iloc[-1] > df["Volume"].rolling(20).mean().iloc[-1]:
            tech_score += 1
            tech_log.append("✅ Volume confirmation")

    elif horizon == "Medium Term":
        if price > ema50:
            tech_score += 2
            tech_log.append("✅ Price above 50 EMA")
        if ema50 > ema200:
            tech_score += 2
            tech_log.append("✅ Golden Cross")
        if rsi < 80:
            tech_score += 1
            tech_log.append("✅ RSI safe")

    else:  # Long Term
        if price > ema200:
            tech_score += 3
            tech_log.append("✅ Price above 200 EMA")
        else:
            tech_score -= 2
            tech_log.append("❌ Below 200 EMA")

        dist = ((price - ema200) / ema200) * 100
        if 0 < dist < 15:
            tech_score += 2
            tech_log.append("✅ Near long-term value zone")

    f_score, f_log = analyze_fundamentals(stock)
    final_score = tech_score + (f_score / 2)

    # ------------------ OUTPUT ------------------

    st.subheader(f"📈 {ticker}")
    st.write(f"**Current Price:** ₹{round(price,2)}")

    st.markdown("### 🛠 Technicals")
    for t in tech_log:
        st.write(t)
    st.write(f"**Technical Score:** {tech_score}/5")

    st.markdown("### 📘 Fundamentals")
    for f in f_log:
        st.write(f)
    st.write(f"**Fundamental Score:** {f_score}/10")

    st.markdown(f"## 🎯 Final Conviction Score: **{round(final_score,1)}/10**")

    if final_score >= 7:
        st.success("🟢 HIGH CONVICTION BUY")
    elif final_score >= 4:
        st.warning("🟡 HOLD / WATCH")
    else:
        st.error("🔴 AVOID")

# ------------------ UI ------------------

symbol = st.text_input("Enter Stock Symbol (e.g. HDFCBANK)")
horizon = st.selectbox(
    "Select Investment Horizon",
    ["Short Term", "Medium Term", "Long Term"]
)

if st.button("Run Analysis"):
    analyze_stock(symbol, horizon)
