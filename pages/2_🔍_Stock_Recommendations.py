import streamlit as st
from data_sources import search_stock_recommendations, get_all_nse_stocks

# Page configuration
st.set_page_config(page_title="Stock Recommendations", layout="wide", page_icon="🔍")

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
</style>
""", unsafe_allow_html=True)

st.title("🔍 Stock Recommendations")
st.caption("Search any NSE stock to get intraday and long-term analyst targets")
st.divider()

# Get complete NSE stock list (500+ stocks)
stock_options = get_all_nse_stocks()

# Search with autocomplete
selected_stock = st.selectbox(
    "Search by Stock Ticker or Company Name",
    options=[""] + stock_options,
    index=0,
    placeholder="Type to search (e.g., RELIANCE or Reliance Industries Ltd.)",
    help="Start typing the stock ticker or company name - we have 500+ NSE stocks"
)

# Display results when a stock is selected
if selected_stock:
    # Extract ticker from selection (format: "TICKER - Company Name")
    ticker_input = selected_stock.split(" - ")[0].strip()
    
    with st.spinner(f"Fetching recommendations for {ticker_input}..."):
        result = search_stock_recommendations(ticker_input)
        
        if result['error']:
            st.error(f"❌ {result['error']}")
        else:
            # Stock Header
            st.markdown(f"### {result['name']} ({result['symbol']})")
            st.metric("Current Market Price", f"₹{result['cmp']:,.2f}")
            
            st.divider()
            
            # Create two columns for Intraday and Long-term
            intra_col, long_col = st.columns(2)
            
            # INTRADAY RECOMMENDATIONS
            with intra_col:
                st.markdown("#### ⚡ Intraday Analysis")
                
                if result['intraday'] and result['intraday'].get('available'):
                    intra = result['intraday']
                    
                    # Recommendation badge
                    rec_color = "🟢" if intra['recommendation'] == "BUY" else "🟡" if intra['recommendation'] == "NEUTRAL" else "🔵"
                    st.markdown(f"{rec_color} **{intra['recommendation']}**")
                    st.caption(intra['signal'])
                    
                    # Metrics
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Target", f"₹{intra['target']:,.2f}", f"{intra['upside_pct']:+.2f}%")
                    with col2:
                        st.metric("Stop Loss", f"₹{intra['stop_loss']:,.2f}")
                    
                    # Range
                    st.markdown("**Today's Range**")
                    st.caption(f"High: ₹{intra['day_high']:,.2f} | Low: ₹{intra['day_low']:,.2f}")
                    st.caption(f"Momentum: {intra['momentum_pct']:+.2f}%")
                    
                    st.info("⚠️ **Note:** Intraday recommendations are for today's trading session only. Use proper risk management.")
                    
                else:
                    st.info("ℹ️ " + result['intraday'].get('message', 'Not available'))
            
            # LONG-TERM RECOMMENDATIONS
            with long_col:
                st.markdown("#### 📈 Long-term Analyst Targets")
                
                if result['longterm'] and result['longterm'].get('available'):
                    longterm = result['longterm']
                    
                    # Recommendation badge
                    rec_color = "🟢" if longterm['recommendation'] == "BUY" else "🔴" if longterm['recommendation'] == "SELL" else "🟡"
                    st.markdown(f"{rec_color} **{longterm['recommendation']}**")
                    st.caption(f"Based on {longterm['num_analysts']} analyst(s) • {longterm['timeframe']}")
                    
                    # Average Target
                    st.metric(
                        "Average Target", 
                        f"₹{longterm['avg_target']:,.2f}",
                        f"{longterm['avg_upside_pct']:+.2f}%"
                    )
                    
                    # Min/Max Targets
                    if longterm['min_target'] and longterm['max_target']:
                        st.markdown("**Analyst Target Range**")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption(f"**Min:** ₹{longterm['min_target']:,.2f}")
                            st.caption(f"Upside: {longterm['min_upside_pct']:+.2f}%")
                        with col2:
                            st.caption(f"**Max:** ₹{longterm['max_target']:,.2f}")
                            st.caption(f"Upside: {longterm['max_upside_pct']:+.2f}%")
                    
                    st.info("📊 **Note:** Analyst targets are consensus estimates. Always do your own research before investing.")
                else:
                    st.info("ℹ️ " + result['longterm'].get('message', 'Not available'))
else:
    # Helpful information when no stock is selected
    st.info("💡 Select a stock from the dropdown above to see recommendations")
    
    st.markdown("### 📋 How to Use:")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Search Options:**
        - Search by ticker (e.g., `RELIANCE`)
        - Search by company name (e.g., `Reliance Industries`)
        - We have **500+ NSE stocks** available
        
        **Intraday Analysis:**
        - Momentum-based signals
        - Target & stop loss prices
        - Today's high/low range
        """)
    
    with col2:
        st.markdown("""
        **Long-term Targets:**
        - Analyst consensus ratings
        - Average target price
        - Min/Max target range
        - Number of analysts covering
        
        **Popular Searches:**
        - RELIANCE, TCS, INFY, HDFCBANK
        - ICICIBANK, SBIN, BHARTIARTL, ITC
        - TATACONSUM, ADANIPORTS, ZOMATO
        """)

st.divider()

# Footer
st.caption("📊 Stock data powered by Yahoo Finance • Recommendations are for informational purposes only")
