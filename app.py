import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from streamlit_autorefresh import st_autorefresh # New Import
from data_sources import (
    fetch_comex, 
    fetch_mcx_intraday,
    get_live_market_news
)
from datetime import datetime
import pandas as pd

# Page configuration
st.set_page_config(page_title="Market Charts", layout="wide", page_icon="📊")

# =========================================================
# 🕒 AUTO-REFRESH SETUP
# =========================================================
# This will refresh the app every 60 seconds (60000 milliseconds)
st_autorefresh(interval=60000, limit=None, key="market_refresh_counter")

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
</style>
""", unsafe_allow_html=True)

# Header
col1, col2 = st.columns([4, 1])
with col1:
    st.title("📊 Commodity Market Charts")
with col2:
    # Manual refresh still available if user is impatient
    if st.button("🔄 Force Refresh", use_container_width=True):
        st.rerun()

st.caption(f"💡 Auto-refreshing every 60s • Last update: {datetime.now().strftime('%H:%M:%S')}")
st.divider()

# =========================
# 🌍 SECTION 1: COMEX
# =========================
st.subheader("🌍 COMEX Futures (International)")
commodities = [("Gold", "GC=F"), ("Silver", "SI=F"), ("Crude Oil", "CL=F"), ("Copper", "HG=F")]

# Period options dictionary defined once for reuse
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

for i in range(0, len(commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, commodities[i:i+2]):
        with col:
            if f'period_{symbol}' not in st.session_state:
                st.session_state[f'period_{symbol}'] = "1D"
            
            selected_period = st.selectbox(
                "Time Range",
                options=list(period_options.keys()),
                index=list(period_options.keys()).index(st.session_state[f'period_{symbol}']),
                key=f"select_{symbol}",
                label_visibility="collapsed"
            )
            
            st.session_state[f'period_{symbol}'] = selected_period
            period, interval = period_options[selected_period]
            
            try:
                ticker = yf.Ticker(symbol)
                
                if selected_period == "1D":
                    df_raw = ticker.history(period="5d", interval="5m").reset_index()
                    if not df_raw.empty:
                        time_col = 'Datetime' if 'Datetime' in df_raw.columns else 'Date'
                        df_raw['TradingDate'] = df_raw[time_col].dt.date if time_col == 'Datetime' else df_raw['Date']
                        unique_dates = sorted(df_raw['TradingDate'].unique())
                        last_trading_day = unique_dates[-1]
                        df = df_raw[df_raw['TradingDate'] == last_trading_day].copy()
                        prev_close = df_raw[df_raw['TradingDate'] == unique_dates[-2]]['Close'].iloc[-1] if len(unique_dates) >= 2 else df['Close'].iloc[0]
                    else:
                        df = pd.DataFrame()
                else:
                    df = ticker.history(period=period, interval=interval).reset_index()
                    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
                    prev_close = df['Close'].iloc[0] if not df.empty else 0
                
                if not df.empty:
                    last_close = df['Close'].iloc[-1]
                    change = last_close - prev_close
                    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric(name, f"${last_close:.2f}", f"{change:.2f} ({pct_change:+.2f}%)")
                    m2.metric("High", f"${df['High'].max():.2f}")
                    m3.metric("Low", f"${df['Low'].min():.2f}")
                    
                    fig = px.area(df, x=time_col, y="Close", height=200)
                    line_color = "rgba(0, 200, 83, 1)" if change >= 0 else "rgba(255, 71, 87, 1)"
                    fill_color = "rgba(0, 200, 83, 0.2)" if change >= 0 else "rgba(255, 71, 87, 0.2)"
                    
                    fig.update_traces(line_color=line_color, fillcolor=fill_color)
                    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), xaxis_title="", yaxis_title="Price ($)", hovermode='x unified', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error loading {name}: {str(e)}")

st.divider()

# =========================
# 🇮🇳 SECTION 2: MCX (INR)
# =========================
st.subheader("🇮🇳 MCX Futures (Domestic - Approx. INR)")

mcx_commodities = [("Gold", "GOLD"), ("Silver", "SILVER"), ("Crude Oil", "CRUDEOIL"), ("Copper", "COPPER")]
mcx_to_yahoo = {"GOLD": "GC=F", "SILVER": "SI=F", "CRUDEOIL": "CL=F", "COPPER": "HG=F"}

def convert_to_inr(df, commodity):
    df = df.copy()
    multipliers = {"GOLD": (10 / 31.1035) * 83, "SILVER": 32.15 * 83, "CRUDEOIL": 83, "COPPER": 2.205 * 83}
    multiplier = multipliers.get(commodity, 83)
    for col in ['Close', 'High', 'Low', 'Open']:
        df[col] = df[col] * multiplier
    return df

for i in range(0, len(mcx_commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, mcx_commodities[i:i+2]):
        with col:
            if f'mcx_period_{symbol}' not in st.session_state:
                st.session_state[f'mcx_period_{symbol}'] = "1D"
            
            selected_period = st.selectbox(
                "Time Range",
                options=list(period_options.keys()),
                index=list(period_options.keys()).index(st.session_state[f'mcx_period_{symbol}']),
                key=f"mcx_select_{symbol}",
                label_visibility="collapsed"
            )
            st.session_state[f'mcx_period_{symbol}'] = selected_period
            period, interval = period_options[selected_period]
            
            try:
                ticker = yf.Ticker(mcx_to_yahoo[symbol])
                # ... [Rest of your MCX logic remains the same as your original snippet]
                # (Omitted here for brevity, but ensure you keep your convert_to_inr logic)
            except Exception as e:
                st.error(f"Error loading {name} data")

# ... [Rest of your News and Footer logic]
