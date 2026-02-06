import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta

# =========================
# COMEX (Yahoo Finance)
# =========================
def fetch_comex(symbol: str) -> pd.DataFrame:
    """
    Fetches 2 days of intraday data to allow comparison with 
    yesterday's final closing price.
    """
    try:
        ticker = yf.Ticker(symbol)
        # Fetching 2 days gives us 'Yesterday' and 'Today'
        df = ticker.history(period="2d", interval="1m", auto_adjust=False)

        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()
        # Filter for active trading minutes
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
    Finds the two most recent available MCX Bhavcopy files.
    Accounts for weekends and holidays by looking back up to 7 days.
    """
    found_dfs = []
    
    # Check the last 7 days to find the 2 latest valid files
    for i in range(7):
        date_str = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.mcxindia.com/downloads/Bhavcopy_{date_str}.csv"
        
        try:
            # Short timeout to keep the app responsive
            r = requests.get(url, timeout=5)
            if r.status_code == 200 and "SYMBOL" in r.text:
                df = pd.read_csv(io.StringIO(r.text))
                df.columns = df.columns.str.strip()
                found_dfs.append(df)
            
            if len(found_dfs) == 2:
                break
        except Exception:
            continue

    if len(found_dfs) == 2:
        # found_dfs[0] is most recent (Today), [1] is previous session
        return found_dfs[0], found_dfs[1]

    return pd.DataFrame(), pd.DataFrame()
