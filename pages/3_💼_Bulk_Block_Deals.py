import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="Institutional Trade Tracker",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------- STYLING ----------------
st.markdown("""
<style>
body {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
}
.stSelectbox > div {
    background-color: #1e293b;
}
.stButton button {
    background-color: #2563eb;
    color: white;
    border-radius: 8px;
}
.block-container {
    padding-top: 2rem;
}
.dataframe {
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- NSE SESSION ----------------
def get_nse_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com",
        "Accept-Language": "en-US,en;q=0.9"
    })
    # Warm up
    session.get("https://www.nseindia.com", timeout=10)
    return session

# ---------------- GET FULL NSE SYMBOL LIST ----------------
@st.cache_data(ttl=86400)
def get_nse_stock_list():
    session = get_nse_session()
    try:
        url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20TOTAL%20MARKET"
        r = session.get(url, timeout=10)
        data = r.json()
        symbols = [item["symbol"] for item in data["data"]]
        return sorted(set(symbols))
    except:
        return []

# ---------------- FETCH DEAL DATA ----------------
@st.cache_data(ttl=600)
def fetch_deal_data(deal_type):
    session = get_nse_session()

    to_date = datetime.now().strftime("%d-%m-%Y")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%d-%m-%Y")

    url = f"https://www.nseindia.com/api/historical/{deal_type}?from={from_date}&to={to_date}"

    try:
        r = session.get(url, timeout=15)
        data = r.json().get("data", [])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        df = df.rename(columns={
            "tradeDate": "Date",
            "symbol": "Symbol",
            "clientName": "Client",
            "dealType": "Deal Type",
            "quantity": "Quantity",
            "price": "Price",
            "buySell": "Action"
        })

        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date", ascending=False)

        return df

    except:
        return pd.DataFrame()

# ---------------- HEADER ----------------
st.title("💼 Institutional Trade Tracker")
st.caption("Bulk & Block Deals — Last 30 Days")

# ---------------- SEARCH SECTION ----------------
symbols = get_nse_stock_list()

col1, col2 = st.columns([4,1])

with col1:
    selected_stock = st.selectbox(
        "🔍 Search NSE Symbol",
        options=["ALL STOCKS"] + symbols
    )

with col2:
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ---------------- LOAD DATA ----------------
with st.spinner("Fetching latest institutional trades..."):
    bulk_df = fetch_deal_data("bulk-deals")
    block_df = fetch_deal_data("block-deals")

# ---------------- FILTER ----------------
if selected_stock != "ALL STOCKS":
    bulk_df = bulk_df[bulk_df["Symbol"] == selected_stock]
    block_df = block_df[block_df["Symbol"] == selected_stock]

# ---------------- TABS ----------------
tab1, tab2 = st.tabs(["📦 Bulk Deals", "🧱 Block Deals"])

with tab1:
    st.markdown("### Bulk Deals (>0.5% equity)")
    if bulk_df.empty:
        st.warning("No bulk deals found for selected period.")
    else:
        st.dataframe(
            bulk_df,
            use_container_width=True,
            height=500
        )

with tab2:
    st.markdown("### Block Deals (Large Institutional Trades)")
    if block_df.empty:
        st.warning("No block deals found for selected period.")
    else:
        st.dataframe(
            block_df,
            use_container_width=True,
            height=500
        )

st.divider()
st.success("Data Source: NSE India | Auto-refresh every 10 minutes")
