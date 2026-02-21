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
st.caption("Live Bulk & Block Deals + Related News")

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

symbols = get_symbol_list()

selected_symbol = st.selectbox(
    "🔍 Search NSE Symbol",
    options=["ALL STOCKS"] + symbols
)

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.divider()

# ---------- BULK DEALS ----------
@st.cache_data(ttl=600)
def fetch_bulk():
    try:
        url = "https://archives.nseindia.com/content/equities/bulk.csv"
        r = requests.get(url, timeout=10)
        df = pd.read_csv(StringIO(r.text))
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

bulk_df = fetch_bulk()

st.subheader("📦 Bulk Deals")

if bulk_df.empty:
    st.warning("No bulk deals available.")
else:
    bulk_df["Symbol"] = bulk_df["Symbol"].astype(str)

    if selected_symbol != "ALL STOCKS":
        bulk_df = bulk_df[bulk_df["Symbol"] == selected_symbol]

    st.dataframe(bulk_df, height=500, use_container_width=True)

st.divider()

# ---------- BLOCK DEALS ----------
@st.cache_data(ttl=600)
def fetch_block():
    try:
        url = "https://archives.nseindia.com/content/equities/block.csv"
        r = requests.get(url, timeout=10)
        df = pd.read_csv(StringIO(r.text))
        df.columns = df.columns.str.strip()
        return df
    except:
        return pd.DataFrame()

block_df = fetch_block()

st.subheader("🧱 Block Deals")

if block_df.empty:
    st.warning("No block deals available.")
else:
    block_df["Symbol"] = block_df["Symbol"].astype(str)

    if selected_symbol != "ALL STOCKS":
        block_df = block_df[block_df["Symbol"] == selected_symbol]

    st.dataframe(block_df, height=500, use_container_width=True)

st.divider()

# ---------- NEWS SECTION ----------
st.subheader("📰 Top 20 News Related to Bulk & Block Deals")

@st.cache_data(ttl=1800)
def fetch_news():
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

news_items = fetch_news()

if not news_items:
    st.info("No recent related news found.")
else:
    for item in news_items:
        st.markdown(f"• [{item['Title']}]({item['Link']})")
