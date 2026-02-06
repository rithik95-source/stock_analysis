import streamlit as st
from data_sources import get_live_market_news, get_dynamic_recos
from datetime import datetime

st.set_page_config(page_title="Live Picks", layout="wide", page_icon="🚀")

st.title("🚀 Live Market Intelligence")
st.write("Real-time news and stock recommendations from the last 7 days.")

# --- STOCK RECOMMENDATIONS ---
st.subheader("💡 Stock Picks (Last 7 Days)")
recos = get_dynamic_recos()
if not recos.empty:
    st.dataframe(
        recos[["Stock", "Date", "Buy_Rate", "CMP", "Target", "Upside %"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "CMP": st.column_config.NumberColumn("Current Rate", format="₹%.2f"),
            "Target": st.column_config.NumberColumn("Target Rate", format="₹%.2f"),
            "Upside %": st.column_config.NumberColumn(format="%.2f%%")
        }
    )
else:
    st.info("No new recommendations in the last week.")

st.divider()

# --- MARKET NEWS ---
st.subheader("📰 Latest News")
news = get_live_market_news()
for item in news:
    with st.container(border=True):
        col1, col2 = st.columns([1, 4])
        with col1:
            st.caption(f"📅 {datetime.fromtimestamp(item['provider_publish_time']).strftime('%Y-%m-%d %H:%M')}")
        with col2:
            st.markdown(f"**[{item['title']}]({item['link']})**")
            st.write(f"Source: {item.get('publisher', 'Finance News Source')}")
