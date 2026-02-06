import yfinance as yf
import pandas as pd

def fetch_comex(symbol: str) -> pd.DataFrame:
    """
    Fetch intraday COMEX data from market open till now (1-minute bars)
    """
    try:
        ticker = yf.Ticker(symbol)

        df = ticker.history(
            period="1d",
            interval="1m",
            auto_adjust=False
        )

        if df.empty:
            return pd.DataFrame()

        df = df.reset_index()

        # Remove overnight / flat rows
        if "Volume" in df.columns:
            df = df[df["Volume"] > 0]

        return df

    except Exception:
        return pd.DataFrame()
