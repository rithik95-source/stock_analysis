import streamlit as st
import pandas as pd
import requests
import datetime
from io import StringIO
import feedparser
import time

# ---------- PAGE SETUP ----------
st.set_page_config(page_title="Institutional Trade Tracker", layout="wide")

st.markdown("""
<style>
    .stButton>button {
        border-radius: 8px;
        background-color: #2563eb;
        color: white;
        font-weight: 600;
        width: 100%;
    }
    .main { background-color: #0e1117; }
</style>
""", unsafe_allow_html=True)

st.title("💼 Institutional Trade Tracker")
st.caption("Historical Bulk & Block Deals (NSE India) + Related News")

# ---------- SYMBOL LIST (Public Archive) ----------
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
with st.container():
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        symbols = get_symbol_list()
        selected_symbol = st.selectbox("🔍 Search NSE Symbol", options=["ALL STOCKS"] + symbols)
    
    with col2:
        date_filter = st.selectbox("📅 Select Date Range", ["1D", "1W", "1M", "3M", "6M", "1Y"], index=2)
    
    with col3:
        st.write("##")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

st.divider()

# ---------- DATA FETCHING (NSE Stealth Mode) ----------
@st.cache_data(ttl=600)
def fetch_nse_data(date_range):
    session = requests.Session()
    
    # These specific headers are the secret to not getting blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.nseindia.com/report-detail/display-bulk-and-block-deals",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # Step 1: Visit home to get cookies (The Handshake)
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        time.sleep(1) # Human-like pause

        # Step 2: Date Prep
        end_date = datetime.date.today()
        range_map = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
        start_date = end_date - datetime.timedelta(days=range_map.get(date_range, 30))

        params = {
            "from": start_date.strftime("%d-%m-%Y"),
            "to": end_date.strftime("%d-%m-%Y")
        }

        # Step 3: Fetch Bulk and Block separately
        bulk_url = "https://www.nseindia.com/api/historical/bulk-deals"
        block_url = "https://www.nseindia.com/api/historical/block-deals"

        bulk_res = session.get(bulk_url, headers=headers, params=params, timeout=15)
        block_res = session.get(block_url, headers=headers, params=params, timeout=15)

        # Step 4: Data Processing
        def process_json(res, type_label):
            if res.status_code == 200:
                data = res.json().get('data', [])
                df = pd.DataFrame(data)
                if not df.empty:
                    df['Type'] = type_label
                return df
            return pd.DataFrame()

        df_bulk = process_json(bulk_res, "Bulk")
        df_block = process_json(block_res, "Block")

        final_df = pd.concat([df_bulk, df_block], ignore_index=True)
        
        if not final_df.empty:
            final_df["date"] = pd.to_datetime(final_df["date"], errors="coerce")
            return final_df.sort_values("date", ascending=False)
        
        return pd.DataFrame()

    except Exception as e:
        st.error(f"NSE Connection Error: {e}")
        return pd.DataFrame()

# ---------- DISPLAY LOGIC ----------
data = fetch_nse_data(date_filter)

st.subheader("📊 Institutional Deals")

if data.empty:
    st.info("No deals found for the selected period. NSE might be blocking the request if you are on a VPN or Cloud.")
else:
    # Apply filtering based on Symbol selectbox
    display_df = data.copy()
    if selected_symbol != "ALL STOCKS":
        display_df = display_df[display_df["symbol"] == selected_symbol]

    if display_df.empty:
        st.warning(f"No deals found specifically for {selected_symbol}.")
    else:
        # Clean numeric values for display
        cols_to_fix = ["quantityTraded", "price"]
        for col in cols_to_fix:
            if col in display_df.columns:
                display_df[col] = pd.to_numeric(display_df[col], errors='coerce')

        st.dataframe(
            display_df,
            column_config={
                "date": st.column_config.DateColumn("Date"),
                "symbol": "Symbol",
                "clientName": "Entity Name",
                "type": "Buy/Sell",
                "quantityTraded": st.column_config.NumberColumn("Quantity", format="%d"),
                "price": st.column_config.NumberColumn("Price", format="%.2f"),
                "Type": "Deal Type"
            },
            use_container_width=True,
            height=500
        )

st.divider()

# ---------- NEWS SECTION ----------
st.subheader("📰 Relevant Market News")

@st.cache_data(ttl=3600)
def fetch_news():
    rss_url = "https://www.moneycontrol.com/rss/MCtopnews.xml"
    feed = feedparser.parse(rss_url)
    items = []
    # Simplified keywords to catch more news
    keywords = ["bulk", "block", "stake", "equity", "deal", "bought", "sold"]
    for entry in feed.entries:
        if any(k in entry.title.lower() for k in keywords):
            items.append({"Title": entry.title, "Link": entry.link})
    return items[:15]

news = fetch_news()
if news:
    for n in news:
        st.markdown(f"• [{n['Title']}]({n['Link']})")
else:
    st.write("No deal-specific news found in the last hour.")
