import streamlit as st
import pandas as pd
import requests
import datetime
from io import StringIO
import feedparser

st.set_page_config(page_title="Institutional Trade Tracker", layout="wide")

# ---------- GLOBAL STYLING ----------
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
html, body, [class*="css"]  {
    font-family: 'Montserrat', sans-serif;
}

.block-container { 
    padding-top: 2rem; 
}

.stButton>button {
    border-radius: 8px;
    background-color: #2563eb;
    color: white;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

st.title("💼 Institutional Trade Tracker")
st.caption("Historical Bulk & Block Deals + Related News")

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

date_filter = st.selectbox(
    "📅 Select Date Range",
    ["1D", "1W", "1M", "3M", "6M", "1Y"]
)

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.divider()

# ---------- FETCH HISTORICAL BULK + BLOCK ----------
@st.cache_data(ttl=600)
def fetch_historical_deals(date_range):

    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }

    try:
        # Important: establish NSE session
        session.get("https://www.nseindia.com", headers=headers, timeout=10)

        end_date = datetime.date.today()

        if date_range == "1D":
            start_date = end_date - datetime.timedelta(days=1)
        elif date_range == "1W":
            start_date = end_date - datetime.timedelta(weeks=1)
        elif date_range == "1M":
            start_date = end_date - datetime.timedelta(days=30)
        elif date_range == "3M":
            start_date = end_date - datetime.timedelta(days=90)
        elif date_range == "6M":
            start_date = end_date - datetime.timedelta(days=180)
        else:
            start_date = end_date - datetime.timedelta(days=365)

        params = {
            "from": start_date.strftime("%d-%m-%Y"),
            "to": end_date.strftime("%d-%m-%Y")
        }

        bulk_url = "https://www.nseindia.com/api/historical/bulk-deals"
        block_url = "https://www.nseindia.com/api/historical/block-deals"

        bulk = session.get(bulk_url, headers=headers, params=params, timeout=10).json()
        block = session.get(block_url, headers=headers, params=params, timeout=10).json()

        bulk_df = pd.DataFrame(bulk.get("data", []))
        block_df = pd.DataFrame(block.get("data", []))

        if bulk_df.empty and block_df.empty:
            return pd.DataFrame()

        bulk_df["Deal Type"] = "Bulk"
        block_df["Deal Type"] = "Block"

        df = pd.concat([bulk_df, block_df], ignore_index=True)

        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        return df.sort_values("date", ascending=False)

    except:
        return pd.DataFrame()

combined_df = fetch_historical_deals(date_filter)

st.subheader("📊 Institutional Deals (Bulk + Block)")

# ---------- FILTER + DISPLAY ----------
if combined_df.empty:
    st.warning("No deals available for selected period.")
else:

    # Filter by symbol
    if selected_symbol != "ALL STOCKS":
        combined_df = combined_df[
            combined_df["symbol"] == selected_symbol
        ]

    # Convert numeric columns safely
    if "quantityTraded" in combined_df.columns:
        combined_df["quantityTraded"] = pd.to_numeric(
            combined_df["quantityTraded"], errors="coerce"
        )

    if "price" in combined_df.columns:
        combined_df["price"] = pd.to_numeric(
            combined_df["price"], errors="coerce"
        )

    # Formatting rules
    format_dict = {}

    if "quantityTraded" in combined_df.columns:
        format_dict["quantityTraded"] = "{:,.0f}"

    if "price" in combined_df.columns:
        format_dict["price"] = "{:,.2f}"

    st.dataframe(
        combined_df.style.format(format_dict),
        height=600,
        use_container_width=True
    )

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
