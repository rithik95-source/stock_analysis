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
            
            st.session_state[f'period_{symbol}'] = selected_period
            period, interval = period_options[selected_period]

            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval).reset_index()
                
                if not df.empty:
                    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
                    last_price = df['Close'].iloc[-1]
                    prev_price = df['Close'].iloc[0]
                    change = last_price - prev_price
                    pct_change = (change / prev_price) * 100
                    
                    st.metric(f"{name} (USD)", f"${last_price:,.2f}", f"{pct_change:+.2f}%")
                    fig = px.area(df, x=time_col, y="Close", height=200)
                    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), xaxis_title="", yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")

# =========================
# 🇮🇳 SECTION 2: MCX
# =========================
st.subheader("🇮🇳 MCX Futures (Domestic - Approx. INR)")
st.caption("💡 Live prices converted from international markets to INR")

mcx_commodities = [("Gold", "GOLD"), ("Silver", "SILVER"), ("Crude Oil", "CRUDEOIL"), ("Copper", "COPPER")]

def convert_to_inr(df, commodity):
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

mcx_to_yahoo = {"GOLD": "GC=F", "SILVER": "SI=F", "CRUDEOIL": "CL=F", "COPPER": "HG=F"}

for i in range(0, len(mcx_commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, mcx_commodities[i:i+2]):
        with col:
            period_options = {
                "1D": ("1d", "5m"), "1W": ("5d", "15m"), "1M": ("1mo", "1h"),
                "3M": ("3mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1d"),
                "3Y": ("3y", "1wk"), "5Y": ("5y", "1wk"), "Max": ("max", "1mo")
            }
            
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
                yahoo_symbol = mcx_to_yahoo[symbol]
                ticker = yf.Ticker(yahoo_symbol)
                
                if selected_period == "1D":
                    df_raw = ticker.history(period="5d", interval="5m").reset_index()
                    if not df_raw.empty:
                        df_raw = convert_to_inr(df_raw, symbol)
                        time_col = 'Datetime' if 'Datetime' in df_raw.columns else 'Date'
                        df_raw['TradingDate'] = df_raw[time_col].dt.date if time_col == 'Datetime' else df_raw[time_col]
                        unique_dates = sorted(df_raw['TradingDate'].unique())
                        last_trading_day = unique_dates[-1]
                        df = df_raw[df_raw['TradingDate'] == last_trading_day].copy()
                        prev_close = df_raw[df_raw['TradingDate'] == unique_dates[-2]]['Close'].iloc[-1] if len(unique_dates) >= 2 else df['Close'].iloc[0]
                    else:
                        df, prev_close = pd.DataFrame(), 0
                else:
                    df = ticker.history(period=period, interval=interval).reset_index()
                    if not df.empty:
                        df = convert_to_inr(df, symbol)
                    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
                    prev_close = df['Close'].iloc[0] if not df.empty else 0
                
                if not df.empty:
                    last_close = df['Close'].iloc[-1]
                    change = last_close - prev_close
                    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric(f"MCX {name}", f"₹{last_close:,.0f}", f"{change:,.0f} ({pct_change:+.2f}%)")
                    m2.metric("High", f"₹{df['High'].max():,.0f}")
                    m3.metric("Low", f"₹{df['Low'].min():,.0f}")
                    
                    fig = px.area(df, x=time_col, y="Close", height=200)
                    line_color = "rgba(0, 200, 83, 1)" if change >= 0 else "rgba(255, 71, 87, 1)"
                    fig.update_traces(line_color=line_color, fillcolor=line_color.replace("1)", "0.2)"))
                    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), xaxis_title="", yaxis_title="Price (₹)", hovermode='x unified', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Error loading {name}: {str(e)}")

st.divider()

# =========================
# 🚀 SECTION 3: STOCK SEARCH
# =========================
st.subheader("🔍 Search Stock Recommendations")
from data_sources import search_stock_recommendations, get_nse_stock_list

stock_options = get_nse_stock_list()
selected_stock = st.selectbox("Search by Stock Ticker or Name", options=[""] + stock_options, index=0, placeholder="Type to search...")

if selected_stock:
    ticker_input = selected_stock.split(" - ")[0].strip()
    with st.spinner(f"Searching for {ticker_input}..."):
        result = search_stock_recommendations(ticker_input)
        if result['error']:
            st.error(f"❌ {result['error']}")
        else:
            st.markdown(f"### {result['name']} ({result['symbol']})")
            st.metric("Current Market Price", f"₹{result['cmp']:,.2f}")
            st.divider()
            intra_col, long_col = st.columns(2)
            
            with intra_col:
                st.markdown("#### ⚡ Intraday Analysis")
                if result['intraday'] and result['intraday'].get('available'):
                    intra = result['intraday']
                    st.markdown(f"**{intra['recommendation']}**")
                    st.metric("Target", f"₹{intra['target']:,.2f}", f"{intra['upside_pct']:+.2f}%")
                else:
                    st.info("ℹ️ " + result['intraday'].get('message', 'Not available'))
                    
            with long_col:
                st.markdown("#### 📈 Long-term Targets")
                if result['longterm'] and result['longterm'].get('available'):
                    longterm = result['longterm']
                    st.metric("Average Target", f"₹{longterm['avg_target']:,.2f}", f"{longterm['avg_upside_pct']:+.2f}%")
                else:
                    st.info("ℹ️ " + result['longterm'].get('message', 'Not available'))

st.divider()

# =========================
# 📰 SECTION 4: MARKET NEWS
# =========================
st.subheader("📰 Live Market News & Updates")
news_col1, news_col2 = st.columns(2)
news_items = get_live_market_news()

with news_col1:
    st.markdown("#### 💡 Stock Recommendation News")
    for item in [n for n in news_items if n.get('category') == 'recommendation'][:6]:
        with st.expander(f"📌 {item['title'][:65]}..."):
            st.write(f"**Source:** {item.get('publisher')}")
            st.link_button("📰 Read Full Article", item.get('link', '#'))

with news_col2:
    st.markdown("#### 📈 General Market Headlines")
    for item in [n for n in news_items if n.get('category') == 'market'][:6]:
        with st.expander(f"📰 {item['title'][:65]}..."):
            st.write(f"**Source:** {item.get('publisher')}")
            st.link_button("📰 Read Full Article", item.get('link', '#'))

st.divider()
st.caption(f"📊 Last refresh: {datetime.now().strftime('%H:%M:%S')} | Data: Yahoo Finance, MCX India")




