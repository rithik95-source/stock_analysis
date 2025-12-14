import yfinance as yf
import pandas as pd
import pandas_ta as ta

# ------------------ DATA FETCH ------------------

def get_indian_stock_data(symbol):
    symbol = symbol.upper().replace(" ", "")
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        symbol = f"{symbol}.NS"

    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="2y")
        return df, stock, symbol
    except:
        return pd.DataFrame(), None, symbol

# ------------------ FUNDAMENTAL ANALYSIS ------------------

def analyze_fundamentals(stock):
    info = stock.info
    financials = stock.financials
    cashflow = stock.cashflow
    balance = stock.balance_sheet

    score = 0
    log = []

    # --- VALUATION ---
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

    # --- PROFITABILITY ---
    roe = info.get("returnOnEquity")
    if roe and roe > 0.15:
        score += 2
        log.append(f"✅ Strong ROE ({round(roe*100,1)}%)")
    elif roe and roe > 0.08:
        score += 1
        log.append(f"⚠️ Average ROE ({round(roe*100,1)}%)")

    # --- DEBT ---
    try:
        debt = balance.loc["Total Debt"].iloc[0]
        equity = balance.loc["Total Stockholder Equity"].iloc[0]
        de = debt / equity
        if de < 1:
            score += 1
            log.append(f"✅ Healthy D/E ({round(de,2)})")
    except:
        pass

    # --- CASH FLOW ---
    try:
        op_cf = cashflow.loc["Total Cash From Operating Activities"].iloc[0]
        if op_cf > 0:
            score += 1
            log.append("✅ Positive Operating Cash Flow")
    except:
        pass

    return score, log

# ------------------ TECHNICAL ANALYSIS ------------------

def analyze_stock(symbol, horizon):
    df, stock, ticker = get_indian_stock_data(symbol)

    if df.empty:
        print("❌ No price data found.")
        return

    # Indicators
    df['EMA20'] = ta.ema(df['Close'], 20)
    df['EMA50'] = ta.ema(df['Close'], 50)
    df['EMA200'] = ta.ema(df['Close'], 200)
    df['RSI'] = ta.rsi(df['Close'], 14)

    price = df['Close'].iloc[-1]
    ema20 = df['EMA20'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]
    ema200 = df['EMA200'].iloc[-1]
    rsi = df['RSI'].iloc[-1]

    tech_score = 0
    tech_log = []

    # --- SHORT ---
    if horizon == "short":
        if price > ema20:
            tech_score += 2
            tech_log.append("✅ Price above 20 EMA")

        if 50 < rsi < 70:
            tech_score += 2
            tech_log.append("✅ Healthy RSI momentum")

        if df['Volume'].iloc[-1] > df['Volume'].rolling(20).mean().iloc[-1]:
            tech_score += 1
            tech_log.append("✅ Volume confirmation")

    # --- MEDIUM ---
    elif horizon == "medium":
        if price > ema50:
            tech_score += 2
            tech_log.append("✅ Price above 50 EMA")

        if ema50 > ema200:
            tech_score += 2
            tech_log.append("✅ Golden Cross")

        if rsi < 80:
            tech_score += 1
            tech_log.append("✅ RSI safe")

    # --- LONG ---
    else:
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

    # ------------------ OUTPUT ------------------

    f_score, f_log = analyze_fundamentals(stock)

    final_score = tech_score + (f_score / 2)

    print("\n" + "="*55)
    print(f"📊 STOCK ANALYSIS: {ticker}")
    print(f"💰 Price: ₹{round(price,2)} | Horizon: {horizon.upper()}")

    print("\n🛠 TECHNICALS:")
    for t in tech_log:
        print(t)
    print(f"Technical Score: {tech_score}/5")

    print("\n📘 FUNDAMENTALS:")
    for f in f_log:
        print(f)
    print(f"Fundamental Score: {f_score}/10")

    print("\n🎯 FINAL CONVICTION SCORE:", round(final_score,1), "/10")

    if final_score >= 7:
        print("🟢 VERDICT: HIGH CONVICTION BUY")
    elif final_score >= 4:
        print("🟡 VERDICT: HOLD / WATCH")
    else:
        print("🔴 VERDICT: AVOID")

# ------------------ MAIN LOOP ------------------

while True:
    symbol = input("\nEnter stock symbol (or 'exit'): ").strip()
    if symbol.lower() in ["exit", "quit"]:
        break

    print("\n1. Short Term\n2. Medium Term\n3. Long Term")
    choice = input("Choose horizon (1/2/3): ").strip()
    horizon = {"1": "short", "2": "medium", "3": "long"}.get(choice, "medium")

    analyze_stock(symbol, horizon)
