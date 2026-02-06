import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from data_sources import fetch_comex, fetch_mcx_two_days
from datetime import datetime

# =========================
# Page config
# =========================
st.set_page_config(page_title="Commodity Dashboard", layout="wide")
st_autorefresh(interval=1000, key="refresh")

st.title("📊 Commodity Dashboard")

# =========================
# COMEX SECTION
# =========================
st.subheader("🌍 COMEX Futures (Intraday)")

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

            if df.empty or len(df) < 2:
                st.warning(f"{name} data unavailable")
                continue

            ltp = df["Close"].iloc[-1]
            prev = df["Close"].iloc[-2]

            st.metric(
                name,
                f"{ltp:.2f}",
                f"{ltp - prev:.2f}"
            )

            fig = px.line(df, x="Datetime", y="Close", height=280)
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

# =========================
# MCX SECTION
# =========================
st.subheader("🇮🇳 MCX Futures (vs Yesterday Close)")

today_df, yday_df = fetch_mcx_two_days()

if today_df.empty or yday_df.empty:
    st.warning("MCX data not available yet.")
else:
    mcx_symbols = ["GOLD", "SILVER", "COPPER", "CRUDEOIL"]

    cols = st.columns(len(mcx_symbols))

    for col, symbol in zip(cols, mcx_symbols):
        with col:
            today_row = today_df[today_df["SYMBOL"] == symbol]
            yday_row = yday_df[yday_df["SYMBOL"] == symbol]

            if today_row.empty or yday_row.empty:
                st.warning(symbol)
                continue

            today_price = today_row.iloc[0]["SETTLE_PR"]
            yday_price = yday_row.iloc[0]["SETTLE_PR"]

            change = today_price - yday_price
            pct = (change / yday_price) * 100

            st.metric(
                f"MCX {symbol}",
                f"{today_price}",
                f"{change:.2f} ({pct:.2f}%)"
            )

            # Click-through to MCX
            st.link_button(
                "Open on MCX",
                "https://www.mcxindia.com/market-data/commodity-futures-market-watch"
            )

# =========================
# Footer
# =========================
st.caption(
    f"Last updated: {datetime.now().strftime('%H:%M:%S')} | "
    "Free data. MCX prices vs previous close."
)
