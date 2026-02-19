import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Bulk & Block Deals", layout="wide", page_icon="💼")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("💼 Bulk & Block Deals")
st.caption("Daily institutional & large trades reported to NSE — 0 day lag")
st.divider()

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.nseindia.com/market-data/bulk-deals',
    'Connection': 'keep-alive',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
}

def get_nse_session():
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get('https://www.nseindia.com', timeout=10)
        session.get('https://www.nseindia.com/market-data/bulk-deals', timeout=10)
    except Exception:
        pass
    return session

@st.cache_data(ttl=600)
def fetch_bulk_deals(from_date, to_date):
    """Fetch bulk deals from NSE between two dates (DD-MM-YYYY)."""
    session = get_nse_session()
    url = f"https://www.nseindia.com/api/historical/bulk-deals?from={from_date}&to={to_date}"
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            deals = data.get('data', [])
            if deals:
                df = pd.DataFrame(deals)
                col_map = {
                    'symbol': 'Symbol',
                    'clientName': 'Client / Entity',
                    'dealType': 'Buy/Sell',
                    'quantity': 'Quantity',
                    'price': 'Price (₹)',
                    'exchange': 'Exchange',
                    'tradeDate': 'Date',
                    'mktCapType': 'Segment',
                }
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if 'Quantity' in df.columns:
                    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
                if 'Price (₹)' in df.columns:
                    df['Price (₹)'] = pd.to_numeric(df['Price (₹)'], errors='coerce')
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%d %b %Y')
                return df, None
            return pd.DataFrame(), "No bulk deals found for this period."
        return pd.DataFrame(), f"NSE returned status {r.status_code}. Try refreshing."
    except Exception as e:
        return pd.DataFrame(), f"Connection error: {str(e)[:120]}"

@st.cache_data(ttl=600)
def fetch_block_deals(from_date, to_date):
    """Fetch block deals from NSE between two dates (DD-MM-YYYY)."""
    session = get_nse_session()
    url = f"https://www.nseindia.com/api/historical/block-deals?from={from_date}&to={to_date}"
    try:
        r = session.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            deals = data.get('data', [])
            if deals:
                df = pd.DataFrame(deals)
                col_map = {
                    'symbol': 'Symbol',
                    'clientName': 'Client / Entity',
                    'dealType': 'Buy/Sell',
                    'quantity': 'Quantity',
                    'price': 'Price (₹)',
                    'exchange': 'Exchange',
                    'tradeDate': 'Date',
                }
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if 'Quantity' in df.columns:
                    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
                if 'Price (₹)' in df.columns:
                    df['Price (₹)'] = pd.to_numeric(df['Price (₹)'], errors='coerce')
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%d %b %Y')
                return df, None
            return pd.DataFrame(), "No block deals found for this period."
        return pd.DataFrame(), f"NSE returned status {r.status_code}. Try refreshing."
    except Exception as e:
        return pd.DataFrame(), f"Connection error: {str(e)[:120]}"

def colour_deal(val):
    if isinstance(val, str):
        v = val.strip().upper()
        if v in ('BUY', 'B'):
            return 'color: #00c853; font-weight: 700'
        elif v in ('SELL', 'S'):
            return 'color: #ff5252; font-weight: 700'
    return ''

def show_table(df, stock_q, label, top_n=20):
    if df.empty:
        st.info(f"ℹ️ No {label} found.")
        return

    # Filter by stock symbol if user typed something
    filtered = df.copy()
    if stock_q:
        sym_col = 'Symbol' if 'Symbol' in filtered.columns else filtered.columns[0]
        mask = filtered[sym_col].astype(str).str.upper().str.contains(stock_q.upper(), na=False)
        filtered = filtered[mask]
        if filtered.empty:
            st.info(f"No {label} found for **{stock_q.upper()}**.")
            return
        total = len(filtered)
        st.caption(f"📌 Filtered: {total} deals for **{stock_q.upper()}** — showing all")
        show = filtered.reset_index(drop=True)
    else:
        # Most recent first if Date col exists, else original order
        if 'Date' in filtered.columns:
            show = filtered.reset_index(drop=True)
        else:
            show = filtered.reset_index(drop=True)
        total = len(show)
        show = show.head(top_n)
        st.caption(f"Showing latest {min(top_n, total)} of {total} deals")

    # Format for display
    disp = show.copy()
    disp.index = disp.index + 1
    if 'Quantity' in disp.columns:
        disp['Quantity'] = disp['Quantity'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else '-')
    if 'Price (₹)' in disp.columns:
        disp['Price (₹)'] = disp['Price (₹)'].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else '-')

    if 'Buy/Sell' in disp.columns:
        styled = disp.style.applymap(colour_deal, subset=['Buy/Sell'])
    else:
        styled = disp.style

    st.dataframe(styled, use_container_width=True, height=min(60 + len(disp) * 38, 620))

# ── Controls ───────────────────────────────────────────────────────────────────
today = datetime.now()
if today.weekday() == 5:
    today -= timedelta(days=1)
elif today.weekday() == 6:
    today -= timedelta(days=2)

c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    date_range = st.selectbox(
        "Period",
        options=["Today", "Last 3 Days", "Last 7 Days", "Last 30 Days"],
        index=0,
        key="bd_period",
    )
with c2:
    stock_search = st.text_input(
        "Filter by stock symbol",
        placeholder="e.g. RELIANCE (leave blank to see all top 20)",
        label_visibility="visible",
        key="bd_stock",
    )
with c3:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Compute date range
days_back = {"Today": 0, "Last 3 Days": 3, "Last 7 Days": 7, "Last 30 Days": 30}[date_range]
from_dt = today - timedelta(days=days_back)
from_str = from_dt.strftime("%d-%m-%Y")
to_str = today.strftime("%d-%m-%Y")

st.caption(f"📅 Period: **{from_dt.strftime('%d %b %Y')}** → **{today.strftime('%d %b %Y')}**  |  Data from NSE India")

# ── Bulk Deals ─────────────────────────────────────────────────────────────────
st.markdown("### 📦 Bulk Deals")
st.caption("Trades where a single entity buys/sells > 0.5% of listed shares — reported same day")

with st.spinner("Fetching bulk deals from NSE..."):
    bulk_df, bulk_err = fetch_bulk_deals(from_str, to_str)

if bulk_err and bulk_df.empty:
    st.warning(f"⚠️ {bulk_err}")
    st.info("NSE requires a browser-like session. If this persists, the data will appear after market hours when NSE updates its API.")
else:
    show_table(bulk_df, stock_search.strip(), "Bulk Deals")

st.divider()

# ── Block Deals ────────────────────────────────────────────────────────────────
st.markdown("### 🧱 Block Deals")
st.caption("Large pre-negotiated trades (≥ ₹10 Cr) in the 15-min block window at market open")

with st.spinner("Fetching block deals from NSE..."):
    block_df, block_err = fetch_block_deals(from_str, to_str)

if block_err and block_df.empty:
    st.warning(f"⚠️ {block_err}")
    st.info("Block deal data may be limited outside market hours.")
else:
    show_table(block_df, stock_search.strip(), "Block Deals")

st.divider()
with st.expander("ℹ️ How to read this data"):
    st.markdown("""
**Bulk Deal** — Any single trade where the quantity is more than 0.5% of a company's total listed shares.
NSE mandates reporting by end of the trading day. Mutual funds and FIIs frequently appear here.

**Block Deal** — Large pre-arranged trades (minimum ₹10 crore) done in a special 15-minute window
at 9:15 AM before regular market hours. Almost always institutional.

**Buy/Sell**
- 🟢 **BUY** — Large entity accumulated the stock
- 🔴 **SELL** — Large entity exited / reduced position

**Search tip:** Leave the stock filter blank to see the top 20 biggest deals of the day.
Type a symbol (e.g. `RELIANCE`) to see all deals for that stock.
    """)

st.caption("📊 Source: NSE India official API  •  Cached 10 minutes")
