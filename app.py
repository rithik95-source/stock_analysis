import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from data_sources import (
    fetch_comex, 
    fetch_mcx_intraday,
    get_live_market_news
)
from datetime import datetime
import pandas as pd

# Page configuration
st.set_page_config(page_title="Market Charts", layout="wide", page_icon="📊")

# =========================
# 🔄 AUTO REFRESH (Every 15 seconds)
# =========================
st_autorefresh(
    interval=15 * 1000,  # 15 seconds
    key="market_autorefresh"
)

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

# Header
st.title("📊 Commodity Market Charts")
st.caption("💡 Live commodity price charts • Auto refresh every 15 seconds")
st.divider()

# =========================
# 🌍 SECTION 1: COMEX
# =========================
st.subheader("🌍 COMEX Futures (International)")
commodities = [("Gold", "GC=F"), ("Silver", "SI=F"), ("Crude Oil", "CL=F"), ("Copper", "HG=F")]

for i in range(0, len(commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, commodities[i:i+2]):
        with col:
            period_options = {
                "1D": ("1d", "5m"),
                "1W": ("5d", "15m"),
                "1M": ("1mo", "1h"),
                "3M": ("3mo", "1d"),
                "6M": ("6mo", "1d"),
                "1Y": ("1y", "1d"),
                "3Y": ("3y", "1wk"),
                "5Y": ("5y", "1wk"),
                "Max": ("max", "1mo")
            }

            if f'period_{symbol}' not in st.session_state:
                st.session_state[f'period_{symbol}'] = "1D"

            selected_period = st.selectbox(
                "Time Range",
                options=list(period_options.keys()),
                index=list(period_options.keys()).index(st.session_state[f'period_{symbol}']),
                key=f"select_{symbol}",
                label_visibility="collapsed"
            )

            # --- FIXED LOGIC START ---
            st.session_state[f'period_{symbol}'] = selected_period
            period, interval = period_options[selected_period]

            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval).reset_index()
                
                if not df.empty:
                    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
                    last_price = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[0]
                    change = last_price - prev_close
                    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric(f"{name} (USD)", f"${last_price:,.2f}", f"{pct_change:+.2f}%")
                    m2.metric("High", f"${df['High'].max():,.2f}")
                    m3.metric("Low", f"${df['Low'].min():,.2f}")

                    fig = px.area(df, x=time_col, y="Close", height=200)
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=0, b=0),
                        xaxis_title="", yaxis_title="",
                        hovermode='x unified',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")
            # --- FIXED LOGIC END ---

# =========================
# 🇮🇳 SECTION 2: MCX
# =========================
st.subheader("🇮🇳 MCX Futures (Domestic - Approx. INR)")
st.caption("💡 Live prices converted from international markets to INR")

mcx_commodities = [("Gold", "GOLD"), ("Silver", "SILVER"), ("Crude Oil", "CRUDEOIL"), ("Copper", "COPPER")]

# Conversion functions
def convert_to_inr(df, commodity):
    """Convert international prices to MCX INR equivalent"""
    df = df.copy()
    if commodity == "GOLD":
        multiplier = (10 / 31.1035) * 83
    elif commodity == "SILVER":
        multiplier = 32.15 * 83
    elif commodity == "CRUDEOIL":
        multiplier = 83
    elif commodity == "COPPER":
        multiplier = 2.205 * 83
    else:
        multiplier = 83
    
    df['Close'] = df['Close'] * multiplier
    df['High'] = df['High'] * multiplier
    df['Low'] = df['Low'] * multiplier
    df['Open'] = df['Open'] * multiplier
    return df

# MCX symbol mapping
mcx_to_yahoo = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "CRUDEOIL": "CL=F",
    "COPPER": "HG=F"
}

for i in range(0, len(mcx_commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, mcx_commodities[i:i+2]):
        with col:
            period_options = {
                "1D": ("1d", "5m"),
                "1W": ("5d", "15m"),
                "1M": ("1mo", "1h"),
                "3M": ("3mo", "1d"),
                "6M": ("6mo", "1d"),
                "1Y": ("1y", "1d"),
                "3Y": ("3y", "1wk


