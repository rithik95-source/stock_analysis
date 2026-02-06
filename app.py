import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from data_sources import fetch_comex, fetch_mcx_two_days
from datetime import datetime

# Page config must be the first Streamlit command
st.set_page_config(page_title="Commodity Dashboard", layout="wide", page_icon="📊")
st_autorefresh(interval=60000, key="refresh")

st.title("📊 Commodity Pro Dashboard")
st.sidebar.success("Select a page above for Stock Picks & News.")

# --- COMEX SECTION ---
st.subheader("🌍 COMEX Futures")
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
                m2.metric("Day High", f"${d_high:.2f}")
                m3.metric("Day Low", f"${d_low:.2f}")
                
                fig = px.line(today, x="Datetime", y="Close", height=200)
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)

# --- MCX SECTION ---
st.divider()
st.subheader("🇮🇳 MCX Futures")
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
