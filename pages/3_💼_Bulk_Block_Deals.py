import streamlit as st
import pandas as pd
import requests
from io import StringIO
import feedparser

st.set_page_config(page_title="Institutional Trade Tracker", layout="wide")

# ---------- STYLING ----------
st.markdown("""
<style>
/* Import Montserrat Font */
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&display=swap');

/* Apply Montserrat to all text elements in Streamlit */
html, body, [class*="css"], [class*="st-"] {
    font-family: 'Montserrat', sans-serif !important;
}

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
# Stacking these linearly aligns the button to the left perfectly
symbols = get_symbol_list()
selected_symbol = st.selectbox(
    "🔍 Search NSE Symbol",
    options=["ALL STOCKS"] + symbols
)

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
        if 'Deal Type' in cols:
            cols = ['Deal Type'] + [c for c in cols if c != 'Deal Type']
            display_df = display_df[cols]
        
        # Force numeric types so formatting works perfectly
        if "Quantity Traded" in display_df.columns:
            display_df["Quantity Traded"] = pd.to_numeric(display_df["Quantity Traded"], errors="coerce")
        if "Trade Price / Wght. Avg. Price" in display_df.columns:
            display_df["Trade Price / Wght. Avg. Price"] = pd.to_numeric(display_df["Trade Price / Wght. Avg. Price"], errors="coerce")
        
        # Create a format dictionary for Pandas Styler
        format_dict = {}
        if "Quantity Traded" in display_df.columns:
            format_dict["Quantity Traded"] = "{:,.0f}"  # Comma separated integer
        if "Trade Price / Wght. Avg. Price" in display_df.columns:
            format_dict["Trade Price / Wght. Avg. Price"] = "{:,.2f}"  # Comma separated float with 2 decimals
            
        # Display using Pandas styling instead of column_config
        st.dataframe(
            display_df.style.format(format_dict, na_rep="-"), 
            height=500, 
            use_container_width=True
        )

st.divider()

import streamlit as st
import pandas as pd
import requests
from io import StringIO
import feedparser

st.set_page_config(page_title="Institutional Trade Tracker", layout="wide")

# ---------- STYLING ----------
st.markdown("""
<style>
/* Import Montserrat Font */
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600&display=swap');

/* Apply Montserrat to all text elements in Streamlit */
html, body, [class*="css"], [class*="st-"] {
    font-family: 'Montserrat', sans-serif !important;
}

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
# Stacking these linearly aligns the button to the left perfectly
symbols = get_symbol_list()
selected_symbol = st.selectbox(
    "🔍 Search NSE Symbol",
    options=["ALL STOCKS"] + symbols
)

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
        if 'Deal Type' in cols:
            cols = ['Deal Type'] + [c for c in cols if c != 'Deal Type']
            display_df = display_df[cols]
        
        # Force numeric types so formatting works perfectly
        if "Quantity Traded" in display_df.columns:
            display_df["Quantity Traded"] = pd.to_numeric(display_df["Quantity Traded"], errors="coerce")
        if "Trade Price / Wght. Avg. Price" in display_df.columns:
            display_df["Trade Price / Wght. Avg. Price"] = pd.to_numeric(display_df["Trade Price / Wght. Avg. Price"], errors="coerce")
        
        # Create a format dictionary for Pandas Styler
        format_dict = {}
        if "Quantity Traded" in display_df.columns:
            format_dict["Quantity Traded"] = "{:,.0f}"  # Comma separated integer
        if "Trade Price / Wght. Avg. Price" in display_df.columns:
            format_dict["Trade Price / Wght. Avg. Price"] = "{:,.2f}"  # Comma separated float with 2 decimals
            
        # Display using Pandas styling instead of column_config
        st.dataframe(
            display_df.style.format(format_dict, na_rep="-"), 
            height=500, 
            use_container_width=True
        )

st.divider()

# ---------- NEWS SECTION ----------
st.subheader("📰 Top Market & Institutional News")

@st.cache_data(ttl=1800)
def fetch_news():
    # 1. Use multiple dedicated market feeds instead of just one general feed
    rss_urls = [
        "https://www.moneycontrol.com/rss/buzzingstocks.xml",
        "https://www.moneycontrol.com/rss/marketreports.xml",
        "https://economictimes.indiatimes.com/markets/rssfeeds/2146842.cms" # ET Markets
    ]
    
    # 2. Broaden the keyword search
    keywords = [
        "bulk", "block", "stake", "institution", "fund", "investor", 
        "acquire", "shares", "equity", "bought", "sold", "fpi", "fii", "dii"
    ]
    
    articles = []
    seen_titles = set() # Prevent duplicate news articles
    
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title_lower = entry.title.lower()
                # Use .get() safely in case an RSS feed doesn't have a summary
                summary_lower = entry.get('summary', '').lower() 
                
                # Check if ANY keyword is in the Title OR the Summary
                if any(kw in title_lower for kw in keywords) or any(kw in summary_lower for kw in keywords):
                    if entry.title not in seen_titles:
                        articles.append({
                            "Title": entry.title,
                            "Link": entry.link
                        })
                        seen_titles.add(entry.title)
        except Exception:
            continue # If one feed fails, keep going with the others
            
    # 3. Fallback: If we still found less than 3 specific articles, just show top general market news
    if len(articles) < 3:
        try:
            fallback_feed = feedparser.parse("https://economictimes.indiatimes.com/markets/rssfeeds/2146842.cms")
            for entry in fallback_feed.entries[:5]: # Grab top 5
                if entry.title not in seen_titles:
                    articles.append({"Title": entry.title, "Link": entry.link})
                    seen_titles.add(entry.title)
        except Exception:
            pass

    return articles[:20]

news_items = fetch_news()

if not news_items:
    st.info("No recent related news found right now. Check back later.")
else:
    for item in news_items:
        st.markdown(f"• [{item['Title']}]({item['Link']})")
