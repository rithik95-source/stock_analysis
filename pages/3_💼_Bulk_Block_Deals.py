import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
import time

st.set_page_config(page_title="Bulk & Block Deals", layout="wide", page_icon="💼")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
    div[data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("💼 Bulk & Block Deals")
st.caption("Institutional & large trades reported to NSE")
st.divider()

# ── NSE Session ────────────────────────────────────────────────────────────────
NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
}

def get_nse_session():
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    pages = [
        'https://www.nseindia.com',
        'https://www.nseindia.com/market-data/bulk-deals',
    ]
    for url in pages:
        try:
            session.headers['Referer'] = url
            session.get(url, timeout=12)
            time.sleep(0.5)
        except Exception:
            pass
    session.headers['Referer'] = 'https://www.nseindia.com/market-data/bulk-deals'
    return session

# ── Fetch Functions ────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_bulk_deals():
    """Fetch the latest bulk deals from NSE (no date filter — latest available)."""
    session = get_nse_session()
    # Use a wide 30-day window so we always get data; we'll show latest 20
    from datetime import datetime, timedelta
    to_dt   = datetime.now()
    from_dt = to_dt - timedelta(days=30)
    from_str = from_dt.strftime("%d-%m-%Y")
    to_str   = to_dt.strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/historical/bulk-deals?from={from_str}&to={to_str}"
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        deals = data.get('data', [])
        if not deals:
            return pd.DataFrame(), "No bulk deals found in the last 30 days."
        df = pd.DataFrame(deals)
        col_map = {
            'symbol':     'Symbol',
            'clientName': 'Client / Entity',
            'dealType':   'Buy/Sell',
            'quantity':   'Quantity',
            'price':      'Price (₹)',
            'exchange':   'Exchange',
            'tradeDate':  'Date',
            'mktCapType': 'Segment',
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
        if 'Price (₹)' in df.columns:
            df['Price (₹)'] = pd.to_numeric(df['Price (₹)'], errors='coerce')
        if 'Date' in df.columns:
            df['_sort_date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.sort_values('_sort_date', ascending=False).drop(columns=['_sort_date'])
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%d %b %Y')
        df = df.reset_index(drop=True)
        return df, None
    except ValueError as e:
        return pd.DataFrame(), f"NSE returned non-JSON response (session issue). Try clicking Refresh. [{str(e)[:80]}]"
    except Exception as e:
        return pd.DataFrame(), f"Connection error: {str(e)[:120]}"

@st.cache_data(ttl=600)
def fetch_block_deals():
    """Fetch the latest block deals from NSE."""
    session = get_nse_session()
    from datetime import datetime, timedelta
    to_dt   = datetime.now()
    from_dt = to_dt - timedelta(days=30)
    from_str = from_dt.strftime("%d-%m-%Y")
    to_str   = to_dt.strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/historical/block-deals?from={from_str}&to={to_str}"
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        deals = data.get('data', [])
        if not deals:
            return pd.DataFrame(), "No block deals found in the last 30 days."
        df = pd.DataFrame(deals)
        col_map = {
            'symbol':     'Symbol',
            'clientName': 'Client / Entity',
            'dealType':   'Buy/Sell',
            'quantity':   'Quantity',
            'price':      'Price (₹)',
            'exchange':   'Exchange',
            'tradeDate':  'Date',
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
        if 'Price (₹)' in df.columns:
            df['Price (₹)'] = pd.to_numeric(df['Price (₹)'], errors='coerce')
        if 'Date' in df.columns:
            df['_sort_date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.sort_values('_sort_date', ascending=False).drop(columns=['_sort_date'])
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%d %b %Y')
        df = df.reset_index(drop=True)
        return df, None
    except ValueError as e:
        return pd.DataFrame(), f"NSE returned non-JSON response (session issue). Try clicking Refresh. [{str(e)[:80]}]"
    except Exception as e:
        return pd.DataFrame(), f"Connection error: {str(e)[:120]}"

# ── Styling ────────────────────────────────────────────────────────────────────
def colour_deal(val):
    if isinstance(val, str):
        v = val.strip().upper()
        if v in ('BUY', 'B'):
            return 'color: #00c853; font-weight: 700'
        elif v in ('SELL', 'S'):
            return 'color: #ff5252; font-weight: 700'
    return ''

# ── Table with Pagination ──────────────────────────────────────────────────────
PAGE_SIZE = 20

def show_table(df: pd.DataFrame, stock_q: str, label: str, page_key: str):
    if df.empty:
        st.info(f"ℹ️ No {label} data available.")
        return

    # --- Filter by stock symbol ---
    if stock_q:
        sym_col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
        mask = df[sym_col].astype(str).str.upper().str.contains(stock_q.upper(), na=False)
        filtered = df[mask].reset_index(drop=True)
        if filtered.empty:
            st.info(f"No {label} found for **{stock_q.upper()}**.")
            return
        total = len(filtered)
        st.caption(f"📌 {total} deal(s) found for **{stock_q.upper()}** — showing all")
        _render_table(filtered)
        return

    # --- Paginated view (no search) ---
    total = len(df)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    page = st.session_state[page_key]
    start = (page - 1) * PAGE_SIZE
    end   = start + PAGE_SIZE
    chunk = df.iloc[start:end].reset_index(drop=True)

    st.caption(f"Showing {start+1}–{min(end, total)} of **{total}** deals  |  Page {page} of {total_pages}")
    _render_table(chunk)

    # Pagination controls
    col_prev, col_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀ Previous", key=f"{page_key}_prev", disabled=(page <= 1)):
            st.session_state[page_key] -= 1
            st.rerun()
    with col_info:
        st.markdown(
            f"<p style='text-align:center; margin-top:6px; color:gray;'>Page {page} / {total_pages}</p>",
            unsafe_allow_html=True
        )
    with col_next:
        if st.button("Next ▶", key=f"{page_key}_next", disabled=(page >= total_pages)):
            st.session_state[page_key] += 1
            st.rerun()

def _render_table(df: pd.DataFrame):
    disp = df.copy()
    disp.index = disp.index + 1
    if 'Quantity' in disp.columns:
        disp['Quantity'] = disp['Quantity'].apply(
            lambda x: f"{int(x):,}" if pd.notna(x) else '-'
        )
    if 'Price (₹)' in disp.columns:
        disp['Price (₹)'] = disp['Price (₹)'].apply(
            lambda x: f"₹{x:,.2f}" if pd.notna(x) else '-'
        )
    if 'Buy/Sell' in disp.columns:
        styled = disp.style.applymap(colour_deal, subset=['Buy/Sell'])
    else:
        styled = disp.style
    st.dataframe(styled, use_container_width=True, height=min(60 + len(disp) * 38, 660))

# ── Controls ───────────────────────────────────────────────────────────────────
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
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

stock_q = stock_search.strip()

# ── Bulk Deals ─────────────────────────────────────────────────────────────────
st.markdown("### 📦 Bulk Deals")
st.caption("Single entity buys/sells > 0.5% of listed shares — reported same day")

with st.spinner("Fetching bulk deals from NSE..."):
    bulk_df, bulk_err = fetch_bulk_deals()

if bulk_err and bulk_df.empty:
    st.warning(f"⚠️ {bulk_err}")
    st.info("💡 **Tip:** NSE requires a browser-like session. Click **Refresh** once or twice — it usually resolves on the 2nd attempt.")
else:
    show_table(bulk_df, stock_q, "Bulk Deals", "bulk_page")

st.divider()

# ── Block Deals ────────────────────────────────────────────────────────────────
st.markdown("### 🧱 Block Deals")
st.caption("Large pre-negotiated trades (≥ ₹10 Cr) in the 15-min block window at market open")

with st.spinner("Fetching block deals from NSE..."):
    block_df, block_err = fetch_block_deals()

if block_err and block_df.empty:
    st.warning(f"⚠️ {block_err}")
    st.info("💡 **Tip:** Block deal data may be sparse outside market hours. Click **Refresh** to retry.")
else:
    show_table(block_df, stock_q, "Block Deals", "block_page")

st.divider()

with st.expander("ℹ️ How to read this data"):
    st.markdown("""
**Bulk Deal** — Any single trade where quantity exceeds 0.5% of a company's total listed shares.
NSE mandates reporting by end of the trading day. Mutual funds and FIIs frequently appear here.

**Block Deal** — Large pre-arranged trades (minimum ₹10 crore) done in a special 15-minute window
at 9:15 AM before regular market hours. Almost always institutional.

**Buy/Sell**
- 🟢 **BUY** — Large entity accumulated shares
- 🔴 **SELL** — Large entity exited / reduced position

**Search tip:** Type a symbol (e.g. `RELIANCE`) to see **all** deals for that stock across the last 30 days.
Leave the search blank to browse all deals 20 at a time using the pagination controls.
    """)

st.caption("📊 Source: NSE India official API  •  Last 30 days  •  Cached 10 minutes")
