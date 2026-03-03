import streamlit as st
import pandas as pd
import requests
from io import StringIO
import feedparser

st.set_page_config(page_title="Institutional Trade Tracker", layout="wide")

# ---------- STYLING ----------
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
st.caption("Live Bulk & Block Deals (Latest Available Day) + Related News")

# ---------- NSE SYMBOL LIST ----------
@st.cache_data(ttl=86400)
def get_symbol_list():
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        r = requests.get(url, timeout=10)
        df = pd.read_csv(StringIO(r.text))
        return sorted(df["SYMBOL"].dropna().unique().tolist())
    except:
        return []

# ---------- UI INPUTS ----------
col1, col2 = st.columns([2, 1])

with col1:
    symbols = get_symbol_list()
    selected_symbol = st.selectbox(
        "🔍 Search NSE Symbol",
        options=["ALL STOCKS"] + symbols
    )

with col2:
    st.write("##") # Alignment spacing
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ---------- COMBINED BULK & BLOCK DEALS ----------
@st.cache_data(ttl=600)
def fetch_combined_deals():
    # 1. Fetch Bulk
    try:
        bulk_url = "https://archives.nseindia.com/content/equities/bulk.csv"
        r_bulk = requests.get(bulk_url, timeout=10)
        bulk_df = pd.read_csv(StringIO(r_bulk.text))
        bulk_df.columns = bulk_df.columns.str.strip()
        bulk_df["Deal Type"] = "Bulk"
    except:
        bulk_df = pd.DataFrame()

    # 2. Fetch Block
    try:
        block_url = "https://archives.nseindia.com/content/equities/block.csv"
        r_block = requests.get(block_url, timeout=10)
        block_df = pd.read_csv(StringIO(r_block.text))
        block_df.columns = block_df.columns.str.strip()
        block_df["Deal Type"] = "Block"
    except:
        block_df = pd.DataFrame()

    # 3. Combine Them
    combined_df = pd.concat([bulk_df, block_df], ignore_index=True)
    return combined_df

deals_df = fetch_combined_deals()

st.subheader("📊 Combined Deals (Bulk + Block)")

if deals_df.empty:
    st.warning("No deals available at the moment.")
else:
    # Ensure Symbol is string for safe filtering
    if "Symbol" in deals_df.columns:
        deals_df["Symbol"] = deals_df["Symbol"].astype(str)
        
    # Apply filtering
    display_df = deals_df.copy()
    if selected_symbol != "ALL STOCKS":
        if "Symbol" in display_df.columns:
            display_df = display_df[display_df["Symbol"] == selected_symbol]

    if display_df.empty:
        st.info(f"No recent deals found for {selected_symbol}.")
    else:
        # Move 'Deal Type' to the front for better visibility
        cols = display_df.columns.tolist()
        cols = ['Deal Type'] + [c for c in cols if c != 'Deal Type']
        display_df = display_df[cols]
        
        st.dataframe(display_df, height=500, use_container_width=True)

st.divider()

# ---------- NEWS SECTION ----------
st.subheader("📰 Top 20 News Related to Deals")

@st.cache_data(ttl=1800)
def fetch_news():
    try:
        rss_url = "https://www.moneycontrol.com/rss/MCtopnews.xml"
        feed = feedparser.parse(rss_url)
        articles = []
        for entry in feed.entries:
            if ("bulk" in entry.title.lower() or 
                "block deal" in entry.title.lower() or 
                "institution" in entry.title.lower()):
                articles.append({
                    "Title": entry.title,
                    "Link": entry.link
                })
        return articles[:20]
    except:
        return []

news_items = fetch_news()

if not news_items:
    st.info("No recent related news found.")
else:
    for item in news_items:
        st.markdown(f"• [{item['Title']}]({item['Link']})")
