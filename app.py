import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from data_sources import (
    fetch_comex, 
    fetch_mcx_intraday,
    get_intraday_recommendations,
    get_longterm_recommendations,
    get_live_market_news
)
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Commodity & Stock Dashboard", layout="wide", page_icon="📊")
st_autorefresh(interval=60000, key="refresh")

# Custom CSS for Montserrat font
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Montserrat', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
    }
    
    .stMetric {
        font-family: 'Montserrat', sans-serif;
    }
    
    .stMetric > label {
        font-family: 'Montserrat', sans-serif;
        font-weight: 500;
    }
    
    .stMetric > div {
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
    }
    
    div[data-testid="stDataFrame"] {
        font-family: 'Montserrat', sans-serif;
    }
    
    .stMarkdown {
        font-family: 'Montserrat', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Multi-Asset Market Dashboard")

# =========================
# 🌍 SECTION 1: COMEX
# =========================
st.subheader("🌍 COMEX Futures (International)")
commodities = [("Gold", "GC=F"), ("Silver", "SI=F"), ("Crude Oil", "CL=F"), ("Copper", "HG=F")]

for i in range(0, len(commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, commodities[i:i+2]):
        with col:
            df = fetch_comex(symbol)
            if not df.empty:
                df['Date'] = df['Datetime'].dt.date
                dates = sorted(df['Date'].unique())
                today = df[df['Date'] == dates[-1]]
                yday_close = df[df['Date'] == dates[-2]]["Close"].iloc[-1] if len(dates) > 1 else today["Close"].iloc[0]
                
                ltp, d_high, d_low = today["Close"].iloc[-1], today["High"].max(), today["Low"].min()
                change = ltp - yday_close
                
                m1, m2, m3 = st.columns(3)
                m1.metric(name, f"${ltp:.2f}", f"{change:.2f}", delta_color="normal")
                m2.metric("High", f"${d_high:.2f}")
                m3.metric("Low", f"${d_low:.2f}")
                
                fig = px.line(today, x="Datetime", y="Close", height=200)
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)

st.divider()

# =========================
# 🇮🇳 SECTION 2: MCX
# =========================
st.subheader("🇮🇳 MCX Futures (Domestic - Approx. INR)")
st.caption("💡 Live prices converted from international markets to INR")

mcx_commodities = [("Gold", "GOLD"), ("Silver", "SILVER"), ("Crude Oil", "CRUDEOIL"), ("Copper", "COPPER")]

for i in range(0, len(mcx_commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, mcx_commodities[i:i+2]):
        with col:
            df = fetch_mcx_intraday(symbol)
            if not df.empty:
                df['Date'] = df['Datetime'].dt.date
                dates = sorted(df['Date'].unique())
                today = df[df['Date'] == dates[-1]]
                yday_close = df[df['Date'] == dates[-2]]["Close"].iloc[-1] if len(dates) > 1 else today["Close"].iloc[0]
                
                ltp = today["Close"].iloc[-1]
                d_high = today["High"].max()
                d_low = today["Low"].min()
                change = ltp - yday_close
                
                m1, m2, m3 = st.columns(3)
                m1.metric(f"MCX {name}", f"₹{ltp:,.0f}", f"{change:,.0f}", delta_color="normal")
                m2.metric("High", f"₹{d_high:,.0f}")
                m3.metric("Low", f"₹{d_low:,.0f}")
                
                fig = px.line(today, x="Datetime", y="Close", height=200)
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                fig.update_yaxes(title_text="Price (₹)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"Unable to fetch {name} data")

st.divider()

# =========================
# 🚀 SECTION 3: STOCK RECOMMENDATIONS
# =========================
st.subheader("🚀 Live Stock Recommendations")

# Create tabs for Intraday and Long-term
tab1, tab2 = st.tabs(["⚡ Intraday Picks", "📈 Long-term Picks"])

with tab1:
    st.markdown("#### ⚡ Intraday Trading Recommendations")
    st.caption("For today's trading session • Auto-refreshes every minute")
    
    intraday_df = get_intraday_recommendations()
    
    if intraday_df is not None and not intraday_df.empty:
        # Display dataframe with nice formatting
        st.dataframe(
            intraday_df[["Stock", "CMP", "Target", "Stop Loss", "Upside %", "Type", "Date"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Stock": st.column_config.TextColumn("Stock Name", width="medium"),
                "CMP": st.column_config.NumberColumn("Current Price", format="₹%.2f"),
                "Target": st.column_config.NumberColumn("Target", format="₹%.2f"),
                "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="₹%.2f"),
                "Upside %": st.column_config.NumberColumn("Upside", format="%.2f%%"),
                "Type": st.column_config.TextColumn("Strategy", width="small"),
                "Date": st.column_config.TextColumn("Updated", width="medium")
            }
        )
        
        st.info("⚠️ **Disclaimer:** These are momentum-based picks. Always use stop losses and trade with proper risk management.")
    else:
        st.warning("🔄 Fetching intraday recommendations... Please wait.")

with tab2:
    st.markdown("#### 📈 Long-term Investment Ideas")
    st.caption("Swing & Positional trades • Timeframe: 2 weeks to 3 months")
    
    longterm_df = get_longterm_recommendations()
    
    if longterm_df is not None and not longterm_df.empty:
        st.dataframe(
            longterm_df[["Stock", "CMP", "Target", "Stop Loss", "Upside %", "Timeframe", "Source", "Date"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Stock": st.column_config.TextColumn("Stock Name", width="medium"),
                "CMP": st.column_config.NumberColumn("Current Price", format="₹%.2f"),
                "Target": st.column_config.NumberColumn("Target", format="₹%.0f"),
                "Stop Loss": st.column_config.NumberColumn("Stop Loss", format="₹%.2f"),
                "Upside %": st.column_config.NumberColumn("Potential Upside", format="%.2f%%"),
                "Timeframe": st.column_config.TextColumn("Duration", width="small"),
                "Source": st.column_config.TextColumn("Source", width="medium"),
                "Date": st.column_config.TextColumn("Published", width="small")
            }
        )
        
        st.info("📊 **Note:** Targets are from analyst recommendations and public sources. Do your own research before investing.")
    else:
        st.warning("🔄 Fetching analyst recommendations... Please wait.")

st.divider()

# =========================
# 📰 SECTION 4: MARKET NEWS
# =========================
st.subheader("📰 Live Market News & Updates")

news_col1, news_col2 = st.columns(2)

with news_col1:
    st.markdown("#### 💡 Stock Recommendation News")
    news_items = get_live_market_news()
    
    # Filter recommendation news
    reco_news = [n for n in news_items if n.get('category') == 'recommendation']
    
    if reco_news:
        for item in reco_news[:6]:
            if isinstance(item, dict) and 'title' in item:
                title = item.get('title', 'No title')
                with st.expander(f"📌 {title[:65]}..."):
                    st.write(f"**Source:** {item.get('publisher', 'Unknown')}")
                    if 'provider_publish_time' in item:
                        try:
                            pub_time = datetime.fromtimestamp(item['provider_publish_time'])
                            st.write(f"**Published:** {pub_time.strftime('%d %b, %H:%M')}")
                        except:
                            st.write(f"**Published:** Recent")
                    if 'link' in item and item['link'] != '#':
                        st.link_button("📰 Read Full Article", item['link'])
    else:
        st.info("📡 Loading recommendation news...")

with news_col2:
    st.markdown("#### 📈 General Market Headlines")
    
    # Filter market news
    market_news = [n for n in news_items if n.get('category') == 'market']
    
    if market_news:
        for item in market_news[:6]:
            if isinstance(item, dict) and 'title' in item:
                title = item.get('title', 'No title')
                with st.expander(f"📰 {title[:65]}..."):
                    st.write(f"**Source:** {item.get('publisher', 'Finance News')}")
                    if 'provider_publish_time' in item:
                        try:
                            pub_time = datetime.fromtimestamp(item['provider_publish_time'])
                            st.write(f"**Published:** {pub_time.strftime('%d %b, %H:%M')}")
                        except:
                            st.write(f"**Published:** Recent")
                    if 'link' in item and item['link'] != '#':
                        st.link_button("📰 Read Full Article", item['link'])
    else:
        st.info("📡 Loading market headlines...")

st.divider()

# Footer
col1, col2 = st.columns(2)
with col1:
    st.caption(f"🔄 Last updated: {datetime.now().strftime('%d %b %Y, %H:%M:%S')}")
with col2:
    st.caption("📊 Data from Yahoo Finance, MCX India, Economic Times & Moneycontrol")

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #888; font-size: 12px;'>
        ⚠️ <b>Disclaimer:</b> This dashboard is for informational purposes only. Not financial advice. 
        Always do your own research and consult a financial advisor before making investment decisions.
    </div>
    """,
    unsafe_allow_html=True
)




