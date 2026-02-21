import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime, timedelta

st.set_page_config(page_title="Bulk & Block Deals", layout="wide", page_icon="💼")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
    .source-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        margin-left: 8px;
        vertical-align: middle;
    }
    .src-nse   { background:#1a3a5c; color:#4fc3f7; }
    .src-bse   { background:#1a3a2a; color:#69f0ae; }
    .src-groww { background:#3a1a3a; color:#ce93d8; }
</style>
""", unsafe_allow_html=True)

st.title("💼 Bulk & Block Deals")
st.caption("Institutional & large trades — pulls from NSE → BSE → Groww in order of availability")
st.divider()

PAGE_SIZE = 20

# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 1 — NSE India (official API, needs cookie session)
# ══════════════════════════════════════════════════════════════════════════════
def _nse_session():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
    })
    for url in ['https://www.nseindia.com', 'https://www.nseindia.com/market-data/bulk-deals']:
        try:
            s.headers['Referer'] = url
            s.get(url, timeout=10)
            time.sleep(0.4)
        except Exception:
            pass
    s.headers['Referer'] = 'https://www.nseindia.com/market-data/bulk-deals'
    return s

def _nse_fetch(deal_type: str):
    """deal_type: 'bulk-deals' or 'block-deals'"""
    s = _nse_session()
    to_dt   = datetime.now()
    from_dt = to_dt - timedelta(days=30)
    url = (f"https://www.nseindia.com/api/historical/{deal_type}"
           f"?from={from_dt.strftime('%d-%m-%Y')}&to={to_dt.strftime('%d-%m-%Y')}")
    r = s.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()
    deals = data.get('data', [])
    if not deals:
        return None
    df = pd.DataFrame(deals)
    col_map = {
        'symbol': 'Symbol', 'clientName': 'Client / Entity',
        'dealType': 'Buy/Sell', 'quantity': 'Quantity',
        'price': 'Price (₹)', 'exchange': 'Exchange',
        'tradeDate': 'Date', 'mktCapType': 'Segment',
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    return df

# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 2 — BSE India
# ══════════════════════════════════════════════════════════════════════════════
def _bse_fetch(deal_type: str):
    """deal_type: 'bulk' or 'block'"""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.bseindia.com/',
        'Accept': 'application/json, text/plain, */*',
    })
    try:
        s.get('https://www.bseindia.com', timeout=8)
    except Exception:
        pass

    to_dt   = datetime.now()
    from_dt = to_dt - timedelta(days=30)
    from_str = from_dt.strftime("%Y%m%d")
    to_str   = to_dt.strftime("%Y%m%d")

    if deal_type == 'bulk':
        url = f"https://api.bseindia.com/BseIndiaAPI/api/BulkDealData/w?quotetype=EQ&fromdate={from_str}&todate={to_str}"
    else:
        url = f"https://api.bseindia.com/BseIndiaAPI/api/BlockDealData/w?quotetype=EQ&fromdate={from_str}&todate={to_str}"

    r = s.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()

    rows = data.get('Table', data.get('data', []))
    if not rows:
        return None

    df = pd.DataFrame(rows)
    bse_col_map = {
        'SCRIP_CD':    'Symbol',
        'SCRIP_NAME':  'Symbol',
        'CLIENT_NAME': 'Client / Entity',
        'DEAL_TYPE':   'Buy/Sell',
        'BUY_SELL':    'Buy/Sell',
        'QUANTITY':    'Quantity',
        'PRICE':       'Price (₹)',
        'TRADE_DATE':  'Date',
        'DT_DATE':     'Date',
        'SEGMENT':     'Segment',
    }
    df = df.rename(columns={k: v for k, v in bse_col_map.items() if k in df.columns})
    df['Exchange'] = 'BSE'
    return df

# ══════════════════════════════════════════════════════════════════════════════
# SOURCE 3 — Groww (public market API)
# ══════════════════════════════════════════════════════════════════════════════
def _groww_fetch(deal_type: str):
    """deal_type: 'bulk' or 'block'"""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://groww.in/markets/bulk-deals',
        'Origin': 'https://groww.in',
    })
    try:
        s.get('https://groww.in/markets/bulk-deals', timeout=8)
    except Exception:
        pass

    if deal_type == 'bulk':
        url = "https://groww.in/v1/api/stocks_data/v1/bulk_deals?page=0&size=100&sortBy=dealDate&sortOrder=DESC"
    else:
        url = "https://groww.in/v1/api/stocks_data/v1/block_deals?page=0&size=100&sortBy=dealDate&sortOrder=DESC"

    r = s.get(url, timeout=20)
    r.raise_for_status()
    data = r.json()

    records = (data.get('content')
               or data.get('data')
               or data.get('deals')
               or (data if isinstance(data, list) else []))
    if not records:
        return None

    df = pd.DataFrame(records)
    groww_col_map = {
        'symbol':     'Symbol',
        'scripName':  'Symbol',
        'clientName': 'Client / Entity',
        'client':     'Client / Entity',
        'dealType':   'Buy/Sell',
        'buySell':    'Buy/Sell',
        'quantity':   'Quantity',
        'price':      'Price (₹)',
        'dealDate':   'Date',
        'tradeDate':  'Date',
        'exchange':   'Exchange',
    }
    df = df.rename(columns={k: v for k, v in groww_col_map.items() if k in df.columns})
    if 'Exchange' not in df.columns:
        df['Exchange'] = 'NSE/BSE'
    return df

# ══════════════════════════════════════════════════════════════════════════════
# Unified fetch with fallback chain
# ══════════════════════════════════════════════════════════════════════════════
def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if 'Quantity' in df.columns:
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
    if 'Price (₹)' in df.columns:
        df['Price (₹)'] = pd.to_numeric(df['Price (₹)'], errors='coerce')
    if 'Date' in df.columns:
        df['_sort'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True)
        df = df.sort_values('_sort', ascending=False).drop(columns=['_sort'])
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True).dt.strftime('%d %b %Y')
    if 'Buy/Sell' in df.columns:
        df['Buy/Sell'] = df['Buy/Sell'].astype(str).str.strip().str.upper()
        df['Buy/Sell'] = df['Buy/Sell'].replace({'B': 'BUY', 'S': 'SELL', 'P': 'BUY'})
    return df.reset_index(drop=True)

@st.cache_data(ttl=600)
def fetch_deals(deal_type: str):
    """
    deal_type: 'bulk' or 'block'
    Returns (df, source_name, error_msg)
    """
    nse_key = 'bulk-deals' if deal_type == 'bulk' else 'block-deals'

    sources = [
        ("NSE India", lambda: _nse_fetch(nse_key)),
        ("BSE India", lambda: _bse_fetch(deal_type)),
        ("Groww",     lambda: _groww_fetch(deal_type)),
    ]

    errors = []
    for name, fn in sources:
        try:
            df = fn()
            if df is not None and not df.empty:
                return _clean_df(df), name, None
            errors.append(f"{name}: empty response")
        except Exception as e:
            errors.append(f"{name}: {str(e)[:80]}")

    return pd.DataFrame(), None, " | ".join(errors)

# ══════════════════════════════════════════════════════════════════════════════
# Rendering helpers
# ══════════════════════════════════════════════════════════════════════════════
SOURCE_BADGE = {
    "NSE India": '<span class="source-badge src-nse">📡 NSE India</span>',
    "BSE India": '<span class="source-badge src-bse">📗 BSE India</span>',
    "Groww":     '<span class="source-badge src-groww">🌱 Groww</span>',
}

def colour_deal(val):
    if isinstance(val, str):
        v = val.strip().upper()
        if v == 'BUY':
            return 'color: #00c853; font-weight: 700'
        elif v == 'SELL':
            return 'color: #ff5252; font-weight: 700'
    return ''

def _render_table(df: pd.DataFrame):
    disp = df.copy()
    disp.index = disp.index + 1
    if 'Quantity' in disp.columns:
        disp['Quantity'] = disp['Quantity'].apply(
            lambda x: f"{int(x):,}" if pd.notna(x) else '-')
    if 'Price (₹)' in disp.columns:
        disp['Price (₹)'] = disp['Price (₹)'].apply(
            lambda x: f"₹{x:,.2f}" if pd.notna(x) else '-')
    styled = disp.style
    if 'Buy/Sell' in disp.columns:
        styled = styled.applymap(colour_deal, subset=['Buy/Sell'])
    st.dataframe(styled, use_container_width=True, height=min(60 + len(disp) * 38, 660))

def show_table(df: pd.DataFrame, stock_q: str, label: str, page_key: str):
    if df.empty:
        st.info(f"ℹ️ No {label} data available from any source.")
        return

    if stock_q:
        sym_col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        mask = df[sym_col].astype(str).str.upper().str.contains(stock_q.upper(), na=False)
        filtered = df[mask].reset_index(drop=True)
        if filtered.empty:
            st.info(f"No {label} found for **{stock_q.upper()}**.")
            return
        st.caption(f"📌 {len(filtered)} deal(s) for **{stock_q.upper()}** — showing all")
        _render_table(filtered)
        return

    # Paginated view
    total = len(df)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    page  = st.session_state[page_key]
    start = (page - 1) * PAGE_SIZE
    end   = start + PAGE_SIZE
    chunk = df.iloc[start:end].reset_index(drop=True)

    st.caption(f"Showing {start+1}–{min(end,total)} of **{total}** deals  |  Page {page}/{total_pages}")
    _render_table(chunk)

    col_prev, col_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Previous", key=f"{page_key}_prev", disabled=(page <= 1)):
            st.session_state[page_key] -= 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<p style='text-align:center;margin-top:6px;color:gray;'>Page {page} / {total_pages}</p>",
            unsafe_allow_html=True)
    with col_next:
        if st.button("Next ▶", key=f"{page_key}_next", disabled=(page >= total_pages)):
            st.session_state[page_key] += 1
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# UI Controls
# ══════════════════════════════════════════════════════════════════════════════
c1, c2 = st.columns([4, 1])
with c1:
    stock_search = st.text_input(
        "🔍 Search by stock symbol",
        placeholder="e.g. RELIANCE  (leave blank to browse all deals with pagination)",
        key="bd_stock",
    )
with c2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        for k in ['bulk_page', 'block_page']:
            st.session_state.pop(k, None)
        st.rerun()

stock_q = stock_search.strip()

# ══════════════════════════════════════════════════════════════════════════════
# Bulk Deals
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📦 Bulk Deals")
st.caption("Single entity buys/sells > 0.5% of listed shares — reported same day")

with st.spinner("Fetching bulk deals…"):
    bulk_df, bulk_src, bulk_err = fetch_deals('bulk')

if bulk_err and bulk_df.empty:
    st.error(f"⚠️ All sources failed:\n\n`{bulk_err}`")
    st.info("NSE, BSE and Groww all returned errors. Check your network or try again in a few minutes.")
else:
    badge = SOURCE_BADGE.get(bulk_src, '')
    st.markdown(f"Data source: {badge}", unsafe_allow_html=True)
    show_table(bulk_df, stock_q, "Bulk Deals", "bulk_page")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# Block Deals
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🧱 Block Deals")
st.caption("Pre-negotiated trades ≥ ₹10 Cr in the 15-min block window at market open")

with st.spinner("Fetching block deals…"):
    block_df, block_src, block_err = fetch_deals('block')

if block_err and block_df.empty:
    st.error(f"⚠️ All sources failed:\n\n`{block_err}`")
    st.info("Block deal data may be sparse outside market hours. Try again during or after market hours.")
else:
    badge = SOURCE_BADGE.get(block_src, '')
    st.markdown(f"Data source: {badge}", unsafe_allow_html=True)
    show_table(block_df, stock_q, "Block Deals", "block_page")

st.divider()

with st.expander("ℹ️ How to read this data"):
    st.markdown("""
**Bulk Deal** — Any single trade where quantity exceeds 0.5% of a company's total listed shares.
NSE mandates reporting by end of the trading day. Mutual funds and FIIs frequently appear here.

**Block Deal** — Large pre-arranged trades (minimum ₹10 crore) in a special 15-minute window
at 9:15 AM before regular market hours. Almost always institutional.

**Data Sources (tried in this order):**
- 📡 **NSE India** — Official source, most accurate, but sometimes needs a session warm-up to work
- 📗 **BSE India** — Official BSE API, good fallback, covers BSE-listed stocks
- 🌱 **Groww** — Aggregates NSE + BSE data, most reliable fallback

**Buy/Sell**
- 🟢 **BUY** — Large entity accumulated shares
- 🔴 **SELL** — Large entity exited / reduced position

**Search tip:** Type a symbol (e.g. `RELIANCE`) to see all deals for that stock across 30 days.
Leave blank to browse 20 at a time using pagination.
    """)

st.caption("📊 Sources: NSE India → BSE India → Groww  •  Last 30 days  •  Cached 10 min")
