import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

# =========================
# COMEX (Yahoo Finance)
# =========================
def fetch_comex(symbol):
    try:
        ticker = yf.Ticker(symbol)
        # Fetch 5 days to ensure Day High/Low and Prev Close are available
        df = ticker.history(period="5d", interval="1m")
        return df.reset_index() if not df.empty else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

# =========================
# MCX Bhavcopy (Official)
# =========================
def fetch_mcx_two_days():
    found = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(10):  # Look back 10 days to handle holidays
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.mcxindia.com/downloads/Bhavcopy_{date}.csv"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                df.columns = df.columns.str.strip().str.upper()
                found.append(df)
            if len(found) == 2: break
        except: continue
    return (found[0], found[1]) if len(found) >= 2 else (pd.DataFrame(), pd.DataFrame())

# =========================
# STOCK RECOS & NEWS
# =========================
def get_dynamic_recos():
    # Example picks from recent public institutional reports
    data = [
        {"Stock": "Bharti Airtel", "Symbol": "BHARTIARTL.NS", "Buy_Rate": "2365", "Target": 2700, "Date": datetime.now() - timedelta(days=2)},
        {"Stock": "SBI", "Symbol": "SBIN.NS", "Buy_Rate": "920", "Target": 1100, "Date": datetime.now() - timedelta(days=1)},
        {"Stock": "Reliance", "Symbol": "RELIANCE.NS", "Buy_Rate": "2980", "Target": 3500, "Date": datetime.now() - timedelta(days=5)},
    ]
    one_week_ago = datetime.now() - timedelta(days=7)
    recos = [r for r in data if r['Date'] > one_week_ago]
    for r in recos:
        t = yf.Ticker(r['Symbol'])
        r['CMP'] = t.fast_info['lastPrice']
        r['Date'] = r['Date'].strftime('%Y-%m-%d')
        r['Upside %'] = round(((r['Target'] - r['CMP']) / r['CMP']) * 100, 2)
    return pd.DataFrame(recos)

def get_live_market_news():
    news = []
    for sym in ["^NSEI", "^BSESN"]:
        news.extend(yf.Ticker(sym).news[:5])
    return news
