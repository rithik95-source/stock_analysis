import streamlit as st
from data_sources import get_stock_recommendation_multi_source, get_all_nse_stocks
import time

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

# Initialize session state for caching
if 'last_search' not in st.session_state:
    st.session_state.last_search = None
if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'last_search_time' not in st.session_state:
    st.session_state.last_search_time = 0

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
    
    # Check if we can use cached result (within 2 minutes)
    current_time = time.time()
    use_cache = (
        st.session_state.last_search == ticker_input and 
        st.session_state.last_result is not None and
        (current_time - st.session_state.last_search_time) < 120  # 2 minutes cache
    )
    
    if use_cache:
        result = st.session_state.last_result
        st.info("📌 Using cached data (refreshes every 2 minutes)")
    else:
        with st.spinner(f"Fetching recommendations for {ticker_input}..."):
            result = get_stock_recommendation_multi_source(ticker_input)
            
            # Cache the result
            st.session_state.last_search = ticker_input
            st.session_state.last_result = result
            st.session_state.last_search_time = current_time
    
    if result['error']:
        st.error(f"❌ {result['error']}")
        
        # Provide helpful troubleshooting
        with st.expander("🔧 Troubleshooting Tips"):
            st.markdown("""
            **Why am I seeing this error?**
            - Rate limiting from data providers
            - Stock ticker may not be found
            - Network connectivity issues
            
            **What can I do?**
            1. Wait 1-2 minutes and try again
            2. Try a different stock
            3. Check if the ticker is correct
            4. Use popular stocks (less likely to be rate limited)
            
            **Popular stocks that usually work:**
            - RELIANCE, TCS, INFY, HDFCBANK
            - ICICIBANK, SBIN, BHARTIARTL, ITC
            """)
    else:
        # Stock Header
        st.markdown(f"### {result['name']} ({result['symbol']})")
        
        # Display data source info
        col1, col2 = st.columns([3, 1])
        with col1:
            st.metric("Current Market Price", f"₹{result['cmp']:,.2f}")
        with col2:
            st.caption(f"📊 Data source: {result.get('data_source', 'Yahoo Finance')}")
        
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
        
        # Additional stock information
        st.divider()
        
        with st.expander("📋 Additional Stock Information"):
            info_col1, info_col2, info_col3 = st.columns(3)
            
            with info_col1:
                if result.get('volume'):
                    st.metric("Volume", f"{result['volume']:,.0f}")
                if result.get('market_cap'):
                    st.metric("Market Cap", f"₹{result['market_cap']:,.0f} Cr")
            
            with info_col2:
                if result.get('pe_ratio'):
                    st.metric("P/E Ratio", f"{result['pe_ratio']:.2f}")
                if result.get('52w_high'):
                    st.metric("52W High", f"₹{result['52w_high']:,.2f}")
            
            with info_col3:
                if result.get('52w_low'):
                    st.metric("52W Low", f"₹{result['52w_low']:,.2f}")
                if result.get('dividend_yield'):
                    st.metric("Div Yield", f"{result['dividend_yield']:.2f}%")

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
        
        **Data Sources:**
        - Primary: Yahoo Finance
        - Fallback: Multiple providers
        - Cache: 2-minute refresh
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
        
        **Tips:**
        - Popular stocks have better data
        - Results cached for 2 minutes
        - Wait if you see rate limit errors
        """)
    
    # Show recently popular stocks
    st.divider()
    st.markdown("### 🔥 Quick Access - Popular Stocks")
    
    popular_stocks = [
        "RELIANCE - Reliance Industries Ltd.",
        "TCS - Tata Consultancy Services Ltd.",
        "INFY - Infosys Ltd.",
        "HDFCBANK - HDFC Bank Ltd.",
        "ICICIBANK - ICICI Bank Ltd.",
        "SBIN - State Bank of India",
        "BHARTIARTL - Bharti Airtel Ltd.",
        "ITC - ITC Ltd.",
    ]
    
    cols = st.columns(4)
    for idx, stock in enumerate(popular_stocks):
        with cols[idx % 4]:
            ticker = stock.split(" - ")[0]
            if st.button(ticker, use_container_width=True):
                st.session_state.selected_popular = stock
                st.rerun()

st.divider()

# Footer
st.caption("📊 Multi-source stock data • Recommendations are for informational purposes only • Data cached for 2 minutes")
