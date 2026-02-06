import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from data_sources import fetch_comex, fetch_mcx_two_days
from datetime import datetime

# =========================
# Page config
# =========================
st.set_page_config(page_title="Commodity Dashboard", layout="wide")
st_autorefresh(interval=60000, key="refresh") # Refresh every 60s to avoid rate limits

st.title("📊 Commodity Dashboard")

# =========================
# COMEX SECTION
# =========================
st.subheader("🌍 COMEX Futures (vs Prev. Close)")

commodities = [
    ("Gold", "GC=F"),
    ("Silver", "SI=F"),
    ("Copper", "HG=F"),
    ("Crude Oil", "CL=F"),
    ("Aluminium", "ALI=F"),
    ("Zinc", "ZNC=F"),
]

for i in range(0, len(commodities), 2):
    col1, col2 = st.columns(2)

    for col, (name, symbol) in zip([col1, col2], commodities[i:i+2]):
        with col:
            df = fetch_comex(symbol)

            if df.empty:
                st.warning(f"{name} data unavailable")
                continue

            # Identify 'Today' and 'Yesterday' groups
            df['Date'] = df['Datetime'].dt.date
            unique_dates = sorted(df['Date'].unique())

            if len(unique_dates) < 2:
                # If only 1 day of data is available, compare to first row
                ltp = df["Close"].iloc[-1]
                prev_close = df["Close"].iloc[0]
            else:
                # Last price of the previous date in the data
                yday_close = df[df['Date'] == unique_dates[-2]]["Close"].iloc[-1]
                ltp = df["Close"].iloc[-1]
                prev_close = yday_close

            change = ltp - prev_close
            pct = (change / prev_close) * 100

            st.metric(
                name,
                f"{ltp:.2f}",
                f"{change:.2f} ({pct:.2f}%)"
            )

            # Chart: Show only today's data for clarity
            today_only = df[df['Date'] == unique_dates[-1]]
            fig = px.line(today_only, x="Datetime", y="Close", height=280)
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

# =========================
# MCX SECTION
# =========================
st.subheader("🇮🇳 MCX Futures (vs Yesterday Close)")

today_df, yday_df = fetch_mcx_two_days()

if today_df.empty or yday_df.empty:
    st.info("Searching for latest MCX Bhavcopy files...")
else:
    mcx_symbols = ["GOLD", "SILVER", "COPPER", "CRUDEOIL"]
    cols = st.columns(len(mcx_symbols))

    for col, symbol in zip(cols, mcx_symbols):
        with col:
            t_row = today_df[today_df["SYMBOL"] == symbol]
            y_row = yday_df[yday_df["SYMBOL"] == symbol]

            if not t_row.empty and not y_row.empty:
                # Usually MCX Bhavcopy uses 'CP' or 'SETTLE_PR'
                price_col = "SETTLE_PR" if "SETTLE_PR" in t_row.columns else t_row.columns[-1]
                
                today_val = float(t_row.iloc[0][price_col])
                yday_val = float(y_row.iloc[0][price_col])

                change = today_val - yday_val
                pct = (change / yday_val) * 100

                st.metric(f"MCX {symbol}", f"{today_val:,.0f}", f"{change:,.2f} ({pct:.2f}%)")
                st.link_button("View on MCX", "https://www.mcxindia.com")

# =========================
# Footer
# =========================
st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Data: Yahoo Finance & MCX India")
