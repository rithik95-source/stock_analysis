import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from data_sources import fetch_comex, fetch_mcx
from datetime import datetime

# =========================
# Page config
# =========================
st.set_page_config(
    page_title="Live Commodity Tracker",
    layout="wide"
)

# Auto refresh every 1 second
st_autorefresh(interval=1000, key="refresh")

st.title("📊 Live COMEX + MCX Commodity Tracker")

# =========================
# COMEX SECTION
# =========================
st.subheader("🌍 COMEX Futures (Free – Near Real-Time)")

comex_map = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Crude Oil": "CL=F"
}

comex_cols = st.columns(len(comex_map))

for idx, (name, symbol) in enumerate(comex_map.items()):
    with comex_cols[idx]:
        df = fetch_comex(symbol)

        if df.empty or len(df) < 2:
            st.warning(f"{name} data unavailable")
            continue

        ltp = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2]
        delta = ltp - prev

        st.metric(
            label=name,
            value=f"{ltp:.2f}",
            delta=f"{delta:.2f}"
        )

        fig = px.line(
            df,
            x="Datetime",
            y="Close",
            height=250
        )
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

# =========================
# MCX SECTION
# =========================
st.subheader("🇮🇳 MCX Futures (Free – Delayed Bhavcopy)")

mcx_df = fetch_mcx()

if mcx_df.empty:
    st.warning("MCX bhavcopy not available yet.")
else:
    mcx_map = {
        "MCX Gold": "GOLD",
        "MCX Silver": "SILVER"
    }

    mcx_cols = st.columns(len(mcx_map))

    for idx, (label, symbol) in enumerate(mcx_map.items()):
        with mcx_cols[idx]:
            row = mcx_df[mcx_df["SYMBOL"] == symbol]

            if row.empty:
                st.warning(f"{label} not found")
                continue

            row = row.iloc[0]

            price = row.get("SETTLE_PR", row.get("CLOSE", 0))
            change = row.get("NET_CHANGE", 0)

            st.metric(
                label=label,
                value=f"{price}",
                delta=f"{change}"
            )

# =========================
# Footer
# =========================
st.caption(
    f"Last refreshed: {datetime.now().strftime('%H:%M:%S')} | "
    "Free data sources. Not for trading."
)
