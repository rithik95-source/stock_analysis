import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from data_sources import fetch_comex, fetch_mcx

st.set_page_config("Commodity Tracker", layout="wide")

# Auto refresh every second
st_autorefresh(interval=1000, key="refresh")

st.title("📊 Live COMEX + MCX Commodity Tracker")

# ---------------- COMEX ----------------
st.subheader("🌍 COMEX Futures")

comex_map = {
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F"
}

comex_cols = st.columns(len(comex_map))

for i, (name, symbol) in enumerate(comex_map.items()):
    with comex_cols[i]:
        df = fetch_comex(symbol)
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
            title=f"{name} (Last 60 min)"
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------- MCX ----------------
st.subheader("🇮🇳 MCX Futures (Delayed)")

mcx_df = fetch_mcx()

gold = mcx_df[mcx_df["Symbol"] == "GOLD"].iloc[0]
silver = mcx_df[mcx_df["Symbol"] == "SILVER"].iloc[0]

mcx_cols = st.columns(2)

with mcx_cols[0]:
    st.metric(
        "MCX Gold",
        value=gold["LTP"],
        delta=gold["Change"]
    )

with mcx_cols[1]:
    st.metric(
        "MCX Silver",
        value=silver["LTP"],
        delta=silver["Change"]

    )

st.caption("⚠️ Data is free-source & delayed. Not for trading.")


