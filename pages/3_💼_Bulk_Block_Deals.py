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
    .buy-row { color: #00c853; font-weight: 600; }
    .sell-row { color: #ff1744; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("💼 Bulk & Block Deals")
st.caption("Daily institutional & large trades reported to NSE/BSE — 0 day lag")
st.divider()

# ── Helpers ────────────────────────────────────────────────────────────────────
NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/',
    'Connection': 'keep-alive',
}

@st.cache_data(ttl=600)
def fetch_nse_bulk_deals(date_str):
    """Fetch bulk deals from NSE for a given date (DD-MM-YYYY)."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass
    url = f"https://www.nseindia.com/api/historical/bulk-deals?from={date_str}&to={date_str}"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            deals = data.get('data', [])
            if deals:
                df = pd.DataFrame(deals)
                rename = {
                    'symbol': 'Symbol', 'clientName': 'Client / Entity',
                    'dealType': 'Deal Type', 'quantity': 'Quantity',
                    'price': 'Price (₹)', 'exchange': 'Exchange',
                    'mktCapType': 'Segment',
                }
                df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
                for col in ['Quantity', 'Price (₹)']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                return df, None
            return pd.DataFrame(), "No bulk deals found for this date."
        return pd.DataFrame(), f"NSE returned status {r.status_code}."
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=600)
def fetch_nse_block_deals(date_str):
    """Fetch block deals from NSE for a given date (DD-MM-YYYY)."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass
    url = f"https://www.nseindia.com/api/historical/block-deals?from={date_str}&to={date_str}"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            deals = data.get('data', [])
            if deals:
                df = pd.DataFrame(deals)
                rename = {
                    'symbol': 'Symbol', 'clientName': 'Client / Entity',
                    'dealType': 'Deal Type', 'quantity': 'Quantity',
                    'price': 'Price (₹)', 'exchange': 'Exchange',
                }
                df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
                for col in ['Quantity', 'Price (₹)']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                return df, None
            return pd.DataFrame(), "No block deals found for this date."
        return pd.DataFrame(), f"NSE returned status {r.status_code}."
    except Exception as e:
        return pd.DataFrame(), str(e)

def style_deal_type(val):
    if isinstance(val, str):
        if val.upper() in ['BUY', 'B']:
            return 'color: #00c853; font-weight: 600'
        elif val.upper() in ['SELL', 'S']:
            return 'color: #ff5252; font-weight: 600'
    return ''

def display_deals_table(df, search_q, label, top_n=20):
    if df.empty:
        st.info(f"ℹ️ No {label} data available.")
        return

    # Filter by stock search
    if search_q:
        mask = df.apply(lambda row: row.astype(str).str.contains(search_q, case=False).any(), axis=1)
        df = df[mask]

    total = len(df)
    if df.empty:
        st.info(f"No {label} matched **{search_q}**.")
        return

    # Sort by quantity desc, show top N
    if 'Quantity' in df.columns:
        df = df.sort_values('Quantity', ascending=False)

    shown = df.head(top_n).reset_index(drop=True)
    shown.index = shown.index + 1

    st.caption(f"Showing top {min(top_n, total)} of {total} deals")

    # Format numbers
    if 'Quantity' in shown.columns:
        shown['Quantity'] = shown['Quantity'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else '-')
    if 'Price (₹)' in shown.columns:
        shown['Price (₹)'] = shown['Price (₹)'].apply(lambda x: f"₹{x:,.2f}" if pd.notna(x) else '-')

    # Colour deal type
    if 'Deal Type' in shown.columns:
        styled = shown.style.applymap(style_deal_type, subset=['Deal Type'])
    else:
        styled = shown.style

    st.dataframe(styled, use_container_width=True, height=min(40 + len(shown) * 38, 600))

# ── Controls ───────────────────────────────────────────────────────────────────
col_date, col_search, col_refresh = st.columns([2, 3, 1])

with col_date:
    # Default to today; skip weekends
    today = datetime.now()
    if today.weekday() == 5:   # Saturday
        today -= timedelta(days=1)
    elif today.weekday() == 6: # Sunday
        today -= timedelta(days=2)
    selected_date = st.date_input("Date", value=today, max_value=today)

with col_search:
    stock_filter = st.text_input(
        "Filter by stock / entity",
        placeholder="e.g. RELIANCE or Goldman Sachs",
        label_visibility="visible",
    )

with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

date_str = selected_date.strftime("%d-%m-%Y")
st.caption(f"Fetching deals for **{selected_date.strftime('%d %B %Y')}** from NSE")

# ── Bulk Deals ─────────────────────────────────────────────────────────────────
st.markdown("### 📦 Bulk Deals")
st.caption("Trades where quantity > 0.5% of listed shares — reported same day by NSE/BSE")

with st.spinner("Fetching bulk deals..."):
    bulk_df, bulk_err = fetch_nse_bulk_deals(date_str)

if bulk_err and bulk_df.empty:
    st.warning(f"⚠️ {bulk_err}")
else:
    display_deals_table(bulk_df, stock_filter.strip(), "Bulk Deals")

st.divider()

# ── Block Deals ────────────────────────────────────────────────────────────────
st.markdown("### 🧱 Block Deals")
st.caption("Large trades (≥ ₹10 Cr) executed in a separate block-deal window at the open")

with st.spinner("Fetching block deals..."):
    block_df, block_err = fetch_nse_block_deals(date_str)

if block_err and block_df.empty:
    st.warning(f"⚠️ {block_err}")
else:
    display_deals_table(block_df, stock_filter.strip(), "Block Deals")

# ── Explainer ──────────────────────────────────────────────────────────────────
st.divider()
with st.expander("ℹ️ How to read this data"):
    st.markdown("""
**Bulk Deal** — Any single trade where the quantity exceeds 0.5% of the company's listed shares.
Reported to NSE/BSE by end of day. If you see a mutual fund or FII name here, they made a
significant move in that stock today.

**Block Deal** — A large pre-negotiated trade (minimum ₹10 crore) executed in the special
15-minute block deal window at market open (9:15–9:30 AM). Usually institutional.

**Deal Type**
- 🟢 **BUY** — institution / large client bought the stock
- 🔴 **SELL** — institution / large client sold the stock

**Tip:** Combine this with F&O participant OI data (Sentiment page) for stronger conviction.
    """)

st.caption("📊 Data source: NSE India official API  •  Refreshed every 10 minutes")
