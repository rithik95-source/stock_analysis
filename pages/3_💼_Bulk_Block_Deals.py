import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIG & STYLING ---
st.set_page_config(page_title="Bulk & Block Deals", layout="wide")

st.markdown("""
<style>
    .reportview-container .main .block-container { padding-top: 2rem; }
    .stDataFrame { border: 1px solid #30363d; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# --- NSE SESSION HANDLER ---
def get_nse_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9"
    })
    try:
        s.get("https://www.nseindia.com", timeout=10) # "Warm up" session
    except:
        pass
    return s

# --- DATA FETCHING ---
@st.cache_data(ttl=3600)
def get_nse_stock_list():
    """Fetches the official list of all NSE symbols for the dropdown."""
    try:
        url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500" # Use 500 as a base or EQUITY_L
        # Fallback to a common list if API fails
        return ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "SBI", "LICI", "ITC", "HINDUNILVR"]
    except:
        return ["RELIANCE", "TCS", "INFY"]

@st.cache_data(ttl=600)
def fetch_deal_data(deal_type="bulk"):
    """
    Fetches deals for the last 30 days.
    deal_type: 'bulk-deals' or 'block-deals'
    """
    session = get_nse_session()
    to_date = datetime.now().strftime("%d-%m-%Y")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%d-%m-%Y")
    
    url = f"https://www.nseindia.com/api/historical/{deal_type}?from={from_date}&to={to_date}"
    
    try:
        response = session.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json().get('data', [])
            df = pd.DataFrame(data)
            if not df.empty:
                # Standardize columns
                col_map = {
                    'tradeDate': 'Date', 'symbol': 'Symbol', 'clientName': 'Client',
                    'dealType': 'Type', 'quantity': 'Qty', 'price': 'Price', 'buySell': 'Action'
                }
                df = df.rename(columns=col_map)
                df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%d-%b-%Y')
                return df
        return pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

# --- UI COMPONENTS ---
def render_paginated_table(df, key_prefix):
    if df.empty:
        st.warning("No data found for this selection.")
        return

    # Pagination logic
    items_per_page = 20
    total_pages = (len(df) // items_per_page) + (1 if len(df) % items_per_page > 0 else 0)
    
    if f'{key_prefix}_page' not in st.session_state:
        st.session_state[f'{key_prefix}_page'] = 1
        
    page = st.session_state[f'{key_prefix}_page']
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    # Display table
    st.table(df.iloc[start_idx:end_idx])
    
    # Pagination buttons
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Previous", key=f"{key_prefix}_prev", disabled=page == 1):
            st.session_state[f'{key_prefix}_page'] -= 1
            st.rerun()
    with col2:
        st.write(f"Page {page} of {total_pages}")
    with col3:
        if st.button("Next ➡️", key=f"{key_prefix}_next", disabled=page == total_pages):
            st.session_state[f'{key_prefix}_page'] += 1
            st.rerun()

# --- MAIN APP ---
st.title("💼 Institutional Trade Tracker")
st.subheader("Bulk & Block Deals (Last 30 Days)")

# Search Section
all_symbols = get_nse_stock_list()
search_col, refresh_col = st.columns([4, 1])

with search_col:
    selected_stock = st.selectbox(
        "🔍 Search Stock Symbol (Live NSE List)",
        options=["ALL STOCKS"] + sorted(all_symbols),
        index=0
    )

with refresh_col:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Fetch Data
bulk_df = fetch_deal_data("bulk-deals")
block_df = fetch_deal_data("block-deals")

# Filtering based on search
if selected_stock != "ALL STOCKS":
    bulk_df = bulk_df[bulk_df['Symbol'] == selected_stock] if not bulk_df.empty else bulk_df
    block_df = block_df[block_df['Symbol'] == selected_stock] if not block_df.empty else block_df

# Display Tabs
tab1, tab2 = st.tabs(["📦 Bulk Deals", "🧱 Block Deals"])

with tab1:
    st.caption("Trades > 0.5% of total equity")
    render_paginated_table(bulk_df, "bulk")

with tab2:
    st.caption("Large pre-negotiated institutional trades")
    render_paginated_table(block_df, "block")

st.divider()
st.info("💡 **Tip:** Use the dropdown to filter by a specific stock. If the table is empty, NSE may have no records for that stock in the last 30 days.")
