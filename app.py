import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from data_sources import fetch_comex, fetch_mcx_two_days, get_dynamic_recos, get_live_market_news
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Commodity & Stock Dashboard", layout="wide", page_icon="📊")
st_autorefresh(interval=60000, key="refresh")

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
                
                m1, m2, m3 = st.columns(3)
                m1.metric(name, f"${ltp:.2f}", f"{ltp-yday_close:.2f}")
                m2.metric("High", f"${d_high:.2f}")
                m3.metric("Low", f"${d_low:.2f}")
                
                fig = px.line(today, x="Datetime", y="Close", height=200)
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)

st.divider()

# =========================
# 🇮🇳 SECTION 2: MCX
# =========================
st.subheader("🇮🇳 MCX Futures (Domestic)")
t_df, y_df = fetch_mcx_two_days()
if not t_df.empty:
    for sym in ["GOLD", "SILVER", "CRUDEOIL", "COPPER"]:
        tr = t_df[t_df["SYMBOL"] == sym]
        yr = y_df[y_df["SYMBOL"] == sym]
        if not tr.empty:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns(4)
                ltp, y_c = float(tr.iloc[0]["CLOSE"]), float(yr.iloc[0]["CLOSE"])
                c1.metric(f"MCX {sym}", f"₹{ltp:,.0f}", f"{ltp-y_c:,.2f}")
                c2.metric("Prev Close", f"₹{y_c:,.0f}")
                c3.metric("High", f"₹{float(tr.iloc[0]['HIGH']):,.0f}")
                c4.metric("Low", f"₹{float(tr.iloc[0]['LOW']):,.0f}")
else:
    st.info("Searching for latest MCX Bhavcopy files...")

st.divider()

# =========================
# 🚀 SECTION 3: STOCK PICKS & NEWS
# =========================
st.subheader("🚀 Live Stock Picks & Market News")
reco_col, news_col = st.columns([1, 1])

with reco_col:
    st.markdown("#### 💡 Weekly Recommendations")
    recos = get_dynamic_recos()
    if recos is not None and not recos.empty:
        st.dataframe(
            recos[["Stock", "Date", "Buy_Rate", "CMP", "Target", "Upside %"]],
            use_container_width=True, hide_index=True,
            column_config={
                "CMP": "Price", 
                "Target": "Goal", 
                "Upside %": st.column_config.NumberColumn(format="%.1f%%")
            }
        )
    else:
        st.warning("Unable to fetch recommendations at the moment.")
    
    # Add recommendation news
    st.markdown("#### 📈 Stock Recommendation News")
    reco_news = get_live_market_news()
    if reco_news:
        for item in reco_news[:5]:
            if isinstance(item, dict) and 'title' in item:
                title = item.get('title', 'No title')
                with st.expander(f"📌 {title[:60]}..."):
                    st.write(f"**Source:** {item.get('publisher', 'Unknown')}")
                    if 'provider_publish_time' in item:
                        try:
                            st.write(f"**Published:** {datetime.fromtimestamp(item['provider_publish_time']).strftime('%Y-%m-%d %H:%M')}")
                        except:
                            st.write(f"**Published:** Recent")
                    if 'link' in item:
                        st.link_button("Read Full Article", item['link'])
    else:
        st.info("No recent recommendation news available.")

with news_col:
    st.markdown("#### 📰 Live Market Headlines")
    news_items = get_live_market_news()
    if news_items:
        for item in news_items[:8]:
            if isinstance(item, dict) and 'title' in item:
                title = item.get('title', 'No title')
                with st.expander(f"📰 {title[:70]}..."):
                    st.write(f"**Source:** {item.get('publisher', 'Finance News')}")
                    if 'provider_publish_time' in item:
                        try:
                            st.write(f"**Published:** {datetime.fromtimestamp(item['provider_publish_time']).strftime('%Y-%m-%d %H:%M')}")
                        except:
                            st.write(f"**Published:** Recent")
                    if 'link' in item:
                        st.link_button("Read Full Article", item['link'])
    else:
        st.info("Fetching latest market news...")

st.caption(f"Last sync: {datetime.now().strftime('%H:%M:%S')} | Data from Yahoo Finance & MCX India")


