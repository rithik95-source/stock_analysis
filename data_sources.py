import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

# =========================
# COMEX (Yahoo Finance)
# =========================
def fetch_comex(symbol):
    """
    Fetch last 60 minutes of COMEX data (1m bars)
    """
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m")

        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        return df.tail(60)

    except Exception:
        return pd.DataFrame()


def fetch_mcx():
    """
    Fetch latest available MCX Bhavcopy CSV
    (tries today, then yesterday)
    """
    for i in range(2):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.mcxindia.com/downloads/Bhavcopy_{date}.csv"

        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and "SYMBOL" in r.text:
                df = pd.read_csv(io.StringIO(r.text))
                df.columns = df.columns.str.strip()
                return df
        except Exception:
            continue

    return pd.DataFrame()
