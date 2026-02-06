import yfinance as yf
import pandas as pd
import requests
from datetime import datetime

# ---------- COMEX ----------
def fetch_comex(symbol):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1d", interval="1m")
    df = df.reset_index()
    return df.tail(60)  # last 60 minutes


# ---------- MCX (Bhavcopy) ----------
def fetch_mcx():
    url = "https://www.mcxindia.com/backpage.aspx/GetMarketWatch"
    payload = {
        "InstrumentName": "FUTCOM",
        "Expiry": ""
    }
    headers = {"Content-Type": "application/json"}

    r = requests.post(url, json=payload, headers=headers, timeout=5)
    data = r.json()["d"]
    df = pd.DataFrame(data)

    df["LTP"] = pd.to_numeric(df["LastTradedPrice"], errors="coerce")
    df["Time"] = datetime.now()

    return df
