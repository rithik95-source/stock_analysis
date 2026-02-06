import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

# =========================
# COMEX (Yahoo Finance)
# =========================
def fetch_comex(symbol: str) -> pd.DataFrame:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1d", interval="1m", auto_adjust=False)

        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        if "Volume" in df.columns:
            df = df[df["Volume"] > 0]

        return df

    except Exception:
        return pd.DataFrame()


# =========================
# MCX Bhavcopy (Official)
# =========================
def fetch_mcx_two_days():
    """
    Fetch today & yesterday MCX bhavcopy for comparison
    """
    data = {}

    for i in range(2):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.mcxindia.com/downloads/Bhavcopy_{date}.csv"

        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and "SYMBOL" in r.text:
                df = pd.read_csv(io.StringIO(r.text))
                df.columns = df.columns.str.strip()
                data[i] = df
        except Exception:
            continue

    if 0 in data and 1 in data:
        return data[0], data[1]

    return pd.DataFrame(), pd.DataFrame()
