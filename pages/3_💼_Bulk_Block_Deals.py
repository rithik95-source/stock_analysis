import streamlit as st
import pandas as pd
import requests
from io import StringIO

st.set_page_config(page_title="Institutional Trade Tracker", layout="wide")

# ---------- Styling ----------
st.markdown("""
<style>
.block-container { padding-top: 2rem; }
.stButton>button {
    border-radius: 8px;
    background-color: #2563eb;
    color: white;
}
</style>
""", unsafe_allow_html=True)

st.title("💼 Institutional Trade Tracker")
st.caption("Live Bulk & Block Deals")

# ---------- Fetch CSV Data ----------
@st.cache_data(ttl=600)
def fetch_bulk_deals():
    try:
        url = "https://archives.nseindia.com/content/equities/bulk.csv"
        r = requests.get(url, timeout=10)
        df = pd.read_csv(StringIO(r.text))
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_block_deals():
    try:
        url = "https://archives.nseindia.com/content/equities/block.csv"
        r = requests.get(url, timeout=10)
        df = pd.read_csv(StringIO(r.text))
        return df
    except:
        return pd.DataFrame()

# ---------- Layout ----------
top_col1, top_col2 = st.columns([6,1])

with top_col2:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ---------- Two Wide Widgets ----------
col1, col2 = st.columns(2)

# BULK DEALS WIDGET
with col1:
    st.subheader("📦 Bulk Deals")
    bulk_df = fetch_bulk_deals()

    if bulk_df.empty:
        st.warning("No bulk deals data available.")
    else:
        search_bulk = st.text_input("Filter Bulk by Symbol", key="bulk_search")
        if search_bulk:
            bulk_df = bulk_df[
                bulk_df["Symbol"].str.contains(search_bulk.upper(), na=False)
            ]
        st.dataframe(bulk_df, height=500, use_container_width=True)

# BLOCK DEALS WIDGET
with col2:
    st.subheader("🧱 Block Deals")
    block_df = fetch_block_deals()

    if block_df.empty:
        st.warning("No block deals data available.")
    else:
        search_block = st.text_input("Filter Block by Symbol", key="block_search")
        if search_block:
            block_df = block_df[
                block_df["Symbol"].str.contains(search_block.upper(), na=False)
            ]
        st.dataframe(block_df, height=500, use_container_width=True)

st.divider()
st.success("Data Source: NSE Archives (CSV)")
