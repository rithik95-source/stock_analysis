import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
from data_sources import (
    fetch_comex, 
    fetch_mcx_intraday,
    get_live_market_news
)
from datetime import datetime
import pandas as pd

# Page configuration
st.set_page_config(page_title="Market Charts", layout="wide", page_icon="📊")

# Auto-refresh every 30 seconds (30000 milliseconds)
# Returns the number of times the app has refreshed
count = st_autorefresh(interval=30000, limit=None, key="data_refresh")

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

# Header with manual refresh button
col1, col2 = st.columns([4, 1])
with col1:
    st.title("📊 Commodity Market Charts")
with col2:
    if st.button("🔄 Refresh", use_container_width=True):
        st.rerun()

st.caption("💡 Live commodity price charts • Auto-refreshes every 30 seconds")
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
            # Time period selector - Mobile friendly dropdown
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
            
            # Use session state to track selected period per commodity
            if f'period_{symbol}' not in st.session_state:
                st.session_state[f'period_{symbol}'] = "1D"
            
            # Dropdown selector instead of buttons
            selected_period = st.selectbox(
                "Time Range",
                options=list(period_options.keys()),
                index=list(period_options.keys()).index(st.session_state[f'period_{symbol}']),
                key=f"select_{symbol}",
                label_visibility="collapsed"
            )
            
            # Update session state
            st.session_state[f'period_{symbol}'] = selected_period
            
            period, interval = period_options[selected_period]
            
            # Fetch data
            try:
                ticker = yf.Ticker(symbol)
                
                # Special handling ONLY for 1D view
                if selected_period == "1D":
                    # Get last 5 days to ensure we have data even on weekends
                    df_raw = ticker.history(period="5d", interval="5m").reset_index()
                    
                    if not df_raw.empty:
                        time_col = 'Datetime' if 'Datetime' in df_raw.columns else 'Date'
                        
                        # Get unique trading dates
                        if time_col == 'Datetime':
                            df_raw['TradingDate'] = df_raw['Datetime'].dt.date
                        else:
                            df_raw['TradingDate'] = df_raw['Date']
                        
                        unique_dates = sorted(df_raw['TradingDate'].unique())
                        
                        # Get last trading day data
                        last_trading_day = unique_dates[-1]
                        df = df_raw[df_raw['TradingDate'] == last_trading_day].copy()
                        
                        # Get previous trading day close for comparison
                        if len(unique_dates) >= 2:
                            prev_trading_day = unique_dates[-2]
                            prev_day_data = df_raw[df_raw['TradingDate'] == prev_trading_day]
                            prev_close = prev_day_data['Close'].iloc[-1]
                        else:
                            prev_close = df['Close'].iloc[0]
                    else:
                        df = pd.DataFrame()
                        prev_close = 0
                else:
                    # For all other periods, use normal fetching
                    df = ticker.history(period=period, interval=interval).reset_index()
                    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
                    prev_close = df['Close'].iloc[0] if not df.empty else 0
                
                if not df.empty:
                    # Calculate metrics
                    last_close = df['Close'].iloc[-1]
                    change = last_close - prev_close
                    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                    is_positive = change >= 0
                    
                    # Get high/low for the displayed period
                    d_high = df['High'].max()
                    d_low = df['Low'].min()
                    
                    # Display metrics with percentage
                    m1, m2, m3 = st.columns(3)
                    m1.metric(
                        name, 
                        f"${last_close:.2f}", 
                        f"{change:.2f} ({pct_change:+.2f}%)", 
                        delta_color="normal"
                    )
                    m2.metric("High", f"${d_high:.2f}")
                    m3.metric("Low", f"${d_low:.2f}")
                    
                    # Create area chart with conditional coloring
                    # Mobile-optimized height
                    chart_height = 200
                    fig = px.area(df, x=time_col, y="Close", height=chart_height)
                    
                    # Set color based on positive/negative
                    if is_positive:
                        line_color = "rgba(0, 200, 83, 1)"  # Green
                        fill_color = "rgba(0, 200, 83, 0.2)"  # Green with transparency
                    else:
                        line_color = "rgba(255, 71, 87, 1)"  # Red
                        fill_color = "rgba(255, 71, 87, 0.2)"  # Red with transparency
                    
                    fig.update_traces(
                        line_color=line_color,
                        fillcolor=fill_color,
                        hovertemplate='<b>Price</b>: $%{y:.2f}<br><b>Time</b>: %{x}<extra></extra>'
                    )
                    
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=0, b=0),
                        xaxis_title="",
                        yaxis_title="Price ($)",
                        hovermode='x unified',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(size=10)  # Smaller font for mobile
                    )
                    
                    # Auto-adjust Y-axis with padding
                    y_min = df['Low'].min()
                    y_max = df['High'].max()
                    y_range = y_max - y_min
                    y_padding = y_range * 0.1  # 10% padding on each side
                    
                    fig.update_yaxes(
                        range=[y_min - y_padding, y_max + y_padding],
                        fixedrange=False
                    )
                    
                    # Add previous close line for 1D view
                    if selected_period == "1D":
                        fig.add_hline(
                            y=prev_close, 
                            line_dash="dot", 
                            line_color="gray",
                            opacity=0.5,
                            annotation_text=f"Prev: ${prev_close:.2f}",
                            annotation_position="right",
                            annotation_font_size=9
                        )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"No data available for {name}")
            except Exception as e:
                st.error(f"Error loading {name} data: {str(e)}")

st.divider()

# =========================
# 🇮🇳 SECTION 2: MCX
# =========================
st.subheader("🇮🇳 MCX India (Converted to INR)")

# MCX commodities with Yahoo Finance mapping
mcx_commodities = [
    ("Gold", "GOLD"),
    ("Silver", "SILVER"),
    ("Crude Oil", "CRUDEOIL"),
    ("Copper", "COPPER")
]

# Mapping to Yahoo Finance symbols
mcx_to_yahoo = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "CRUDEOIL": "CL=F",
    "COPPER": "HG=F"
}

# Conversion function for MCX
def convert_to_inr(df, commodity):
    """Convert international prices to INR"""
    if commodity == "GOLD":
        # USD/oz to INR/10g
        df['Close'] = df['Close'] * (10 / 31.1035) * 83
        df['High'] = df['High'] * (10 / 31.1035) * 83
        df['Low'] = df['Low'] * (10 / 31.1035) * 83
        df['Open'] = df['Open'] * (10 / 31.1035) * 83
    elif commodity == "SILVER":
        # USD/oz to INR/kg
        df['Close'] = df['Close'] * 32.15 * 83
        df['High'] = df['High'] * 32.15 * 83
        df['Low'] = df['Low'] * 32.15 * 83
        df['Open'] = df['Open'] * 32.15 * 83
    elif commodity == "CRUDEOIL":
        # USD/barrel to INR/barrel
        df['Close'] = df['Close'] * 83
        df['High'] = df['High'] * 83
        df['Low'] = df['Low'] * 83
        df['Open'] = df['Open'] * 83
    elif commodity == "COPPER":
        # USD/lb to INR/kg
        df['Close'] = df['Close'] * 2.205 * 83
        df['High'] = df['High'] * 2.205 * 83
        df['Low'] = df['Low'] * 2.205 * 83
        df['Open'] = df['Open'] * 2.205 * 83
    return df

for i in range(0, len(mcx_commodities), 2):
    cols = st.columns(2)
    for col, (name, symbol) in zip(cols, mcx_commodities[i:i+2]):
        with col:
            # Time period selector
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
            
            # Use session state
            if f'mcx_period_{symbol}' not in st.session_state:
                st.session_state[f'mcx_period_{symbol}'] = "1D"
            
            selected_period = st.selectbox(
                "Time Range",
                options=list(period_options.keys()),
                index=list(period_options.keys()).index(st.session_state[f'mcx_period_{symbol}']),
                key=f"mcx_select_{symbol}",
                label_visibility="collapsed"
            )
            
            # Update session state
            st.session_state[f'mcx_period_{symbol}'] = selected_period
            
            period, interval = period_options[selected_period]
            
            # Fetch data
            try:
                yahoo_symbol = mcx_to_yahoo[symbol]
                ticker = yf.Ticker(yahoo_symbol)
                
                # Special handling ONLY for 1D view
                if selected_period == "1D":
                    # Get last 5 days to ensure we have data even on weekends
                    df_raw = ticker.history(period="5d", interval="5m").reset_index()
                    
                    if not df_raw.empty:
                        # Convert to INR
                        df_raw = convert_to_inr(df_raw, symbol)
                        
                        time_col = 'Datetime' if 'Datetime' in df_raw.columns else 'Date'
                        
                        # Get unique trading dates
                        if time_col == 'Datetime':
                            df_raw['TradingDate'] = df_raw['Datetime'].dt.date
                        else:
                            df_raw['TradingDate'] = df_raw['Date']
                        
                        unique_dates = sorted(df_raw['TradingDate'].unique())
                        
                        # Get last trading day data
                        last_trading_day = unique_dates[-1]
                        df = df_raw[df_raw['TradingDate'] == last_trading_day].copy()
                        
                        # Get previous trading day close for comparison
                        if len(unique_dates) >= 2:
                            prev_trading_day = unique_dates[-2]
                            prev_day_data = df_raw[df_raw['TradingDate'] == prev_trading_day]
                            prev_close = prev_day_data['Close'].iloc[-1]
                        else:
                            prev_close = df['Close'].iloc[0]
                    else:
                        df = pd.DataFrame()
                        prev_close = 0
                else:
                    # For all other periods, use normal fetching
                    df = ticker.history(period=period, interval=interval).reset_index()
                    if not df.empty:
                        df = convert_to_inr(df, symbol)
                    time_col = 'Datetime' if 'Datetime' in df.columns else 'Date'
                    prev_close = df['Close'].iloc[0] if not df.empty else 0
                
                if not df.empty:
                    # Calculate metrics
                    last_close = df['Close'].iloc[-1]
                    change = last_close - prev_close
                    pct_change = (change / prev_close) * 100 if prev_close != 0 else 0
                    is_positive = change >= 0
                    
                    # Get high/low for the displayed period
                    d_high = df['High'].max()
                    d_low = df['Low'].min()
                    
                    # Display metrics with percentage
                    m1, m2, m3 = st.columns(3)
                    m1.metric(
                        f"MCX {name}", 
                        f"₹{last_close:,.0f}", 
                        f"{change:,.0f} ({pct_change:+.2f}%)", 
                        delta_color="normal"
                    )
                    m2.metric("High", f"₹{d_high:,.0f}")
                    m3.metric("Low", f"₹{d_low:,.0f}")
                    
                    # Create area chart with conditional coloring
                    # Mobile-optimized height
                    chart_height = 200
                    fig = px.area(df, x=time_col, y="Close", height=chart_height)
                    
                    # Set color based on positive/negative
                    if is_positive:
                        line_color = "rgba(0, 200, 83, 1)"  # Green
                        fill_color = "rgba(0, 200, 83, 0.2)"  # Green with transparency
                    else:
                        line_color = "rgba(255, 71, 87, 1)"  # Red
                        fill_color = "rgba(255, 71, 87, 0.2)"  # Red with transparency
                    
                    fig.update_traces(
                        line_color=line_color,
                        fillcolor=fill_color,
                        hovertemplate='<b>Price</b>: ₹%{y:,.0f}<br><b>Time</b>: %{x}<extra></extra>'
                    )
                    
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=0, b=0),
                        xaxis_title="",
                        yaxis_title="Price (₹)",
                        hovermode='x unified',
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(size=10)  # Smaller font for mobile
                    )
                    
                    # Auto-adjust Y-axis with padding
                    y_min = df['Low'].min()
                    y_max = df['High'].max()
                    y_range = y_max - y_min
                    y_padding = y_range * 0.1  # 10% padding on each side
                    
                    fig.update_yaxes(
                        range=[y_min - y_padding, y_max + y_padding],
                        fixedrange=False
                    )
                    
                    # Add previous close line for 1D view
                    if selected_period == "1D":
                        fig.add_hline(
                            y=prev_close, 
                            line_dash="dot", 
                            line_color="gray",
                            opacity=0.5,
                            annotation_text=f"Prev: ₹{prev_close:,.0f}",
                            annotation_position="right",
                            annotation_font_size=9
                        )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning(f"No data available for {name}")
            except Exception as e:
                st.error(f"Error loading {name} data: {str(e)}")

st.divider()

# =========================
# 📰 SECTION 3: MARKET NEWS
# =========================
st.subheader("📰 Market News & Headlines")
st.caption("Latest updates from Economic Times, Moneycontrol, and more")

try:
    news_items = get_live_market_news()
    
    # Separate recommendation news and general news
    reco_news = [item for item in news_items if item.get('category') == 'recommendation']
    market_news = [item for item in news_items if item.get('category') != 'recommendation']
    
    # Create two columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 💼 Stock Recommendations")
        for item in reco_news[:6]:
            with st.expander(f"📌 {item['title'][:80]}..."):
                st.markdown(f"**Source:** {item['publisher']}")
                pub_time = datetime.fromtimestamp(item['provider_publish_time'])
                st.caption(f"Published: {pub_time.strftime('%d %b, %H:%M')}")
                if item.get('link') and item['link'] != '#':
                    st.markdown(f"[Read Full Article]({item['link']})")
    
    with col2:
        st.markdown("#### 📊 General Headlines")
        for item in market_news[:6]:
            with st.expander(f"📰 {item['title'][:80]}..."):
                st.markdown(f"**Source:** {item['publisher']}")
                pub_time = datetime.fromtimestamp(item['provider_publish_time'])
                st.caption(f"Published: {pub_time.strftime('%d %b, %H:%M')}")
                if item.get('link') and item['link'] != '#':
                    st.markdown(f"[Read Full Article]({item['link']})")
except Exception as e:
    st.warning("Unable to load news at this time. Please try again later.")

st.divider()

# Footer
col1, col2 = st.columns(2)
with col1:
    st.caption(f"📊 Last refresh: {datetime.now().strftime('%d %b %Y, %H:%M:%S')} • Refresh #{count}")
with col2:
    st.caption("📈 Data from Yahoo Finance, MCX India, Economic Times & Moneycontrol")
