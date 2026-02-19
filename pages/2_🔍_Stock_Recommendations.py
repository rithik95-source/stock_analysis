import sys
import os

# Fix import path so data_sources.py in the project root is found when
# this file runs from the pages/ sub-directory on Streamlit Cloud
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from data_sources import get_stock_recommendation_multi_source, get_all_nse_stocks
import time

# Page configuration
st.set_page_config(page_title="Stock Recommendations", layout="wide", page_icon="🔍")

# Custom CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 Stock Recommendations")
st.caption("Search any NSE stock to get intraday and long-term analyst targets")
st.divider()

# ── Session state ──────────────────────────────────────────────────────────────
if 'last_search' not in st.session_state:
    st.session_state.last_search = None
if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'last_search_time' not in st.session_state:
    st.session_state.last_search_time = 0
if 'all_stocks' not in st.session_state:
    with st.spinner("Loading NSE stock list..."):
        st.session_state.all_stocks = get_all_nse_stocks()

all_stocks = st.session_state.all_stocks  # ["TICKER - Company Name", ...]

# ── Search: text input filters the dropdown ────────────────────────────────────
search_query = st.text_input(
    "Search Stock",
    placeholder="Type ticker or company name  (e.g. RELIANCE  or  Tata Consultancy)",
    label_visibility="collapsed",
)

query = search_query.strip().lower()
filtered = [s for s in all_stocks if query in s.lower()] if query else all_stocks

if filtered:
    selected_stock = st.selectbox(
        "Select a stock",
        options=[""] + filtered,
        index=0,
        label_visibility="collapsed",
    )
else:
    st.warning("No stocks matched your search. Try a different keyword.")
    selected_stock = ""

# ── Result display ─────────────────────────────────────────────────────────────
if selected_stock:
    ticker_input = selected_stock.split(" - ")[0].strip()

    current_time = time.time()
    use_cache = (
        st.session_state.last_search == ticker_input
        and st.session_state.last_result is not None
        and (current_time - st.session_state.last_search_time) < 120  # 2-min cache
    )

    if use_cache:
        result = st.session_state.last_result
        st.info("📌 Showing cached data (auto-refreshes every 2 minutes)")
    else:
        with st.spinner(f"Fetching recommendations for {ticker_input}..."):
            result = get_stock_recommendation_multi_source(ticker_input)
            st.session_state.last_search = ticker_input
            st.session_state.last_result = result
            st.session_state.last_search_time = current_time

    if result.get('error'):
        st.error(f"❌ {result['error']}")
        with st.expander("🔧 Troubleshooting Tips"):
            st.markdown("""
**Why am I seeing this error?**
- Rate limiting from data providers
- Stock ticker may not be found
- Network connectivity issues

**What can I do?**
1. Wait 1–2 minutes and try again
2. Try a different stock
3. Verify the ticker is correct (use NSE symbol, e.g. `RELIANCE`, `TCS`)

**Popular stocks that usually work:** RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, SBIN, BHARTIARTL, ITC
""")
    else:
        # ── Header ──
        st.markdown(f"### {result['name']} ({result['symbol']})")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.metric("Current Market Price", f"₹{result['cmp']:,.2f}")
        with col2:
            st.caption(f"📊 Source: {result.get('data_source', 'Yahoo Finance')}")

        st.divider()

        intra_col, long_col = st.columns(2)

        # ── Intraday ──
        with intra_col:
            st.markdown("#### ⚡ Intraday Analysis")
            intra = result.get('intraday') or {}
            if intra.get('available'):
                rec = intra['recommendation']
                icon = "🟢" if rec == "BUY" else "🟡" if rec == "NEUTRAL" else "🔵"
                st.markdown(f"{icon} **{rec}**")
                st.caption(intra['signal'])

                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Target", f"₹{intra['target']:,.2f}", f"{intra['upside_pct']:+.2f}%")
                with c2:
                    st.metric("Stop Loss", f"₹{intra['stop_loss']:,.2f}")

                st.markdown("**Today's Range**")
                st.caption(f"High: ₹{intra['day_high']:,.2f}  |  Low: ₹{intra['day_low']:,.2f}")
                st.caption(f"Momentum: {intra['momentum_pct']:+.2f}%")
                st.info("⚠️ **Note:** Intraday recommendations are for today's trading session only. Use proper risk management.")
            else:
                st.info("ℹ️ " + intra.get('message', 'Intraday data not available'))

        # ── Long-term ──
        with long_col:
            st.markdown("#### 📈 Long-term Analyst Targets")
            lt = result.get('longterm') or {}
            if lt.get('available'):
                rec = lt['recommendation']
                icon = "🟢" if rec == "BUY" else "🔴" if rec == "SELL" else "🟡"
                st.markdown(f"{icon} **{rec}**")
                analysts_label = f"{lt['num_analysts']} analyst(s)" if lt['num_analysts'] else "Technical analysis"
                st.caption(f"Based on {analysts_label}  •  {lt['timeframe']}")

                st.metric(
                    "Average Target",
                    f"₹{lt['avg_target']:,.2f}",
                    f"{lt['avg_upside_pct']:+.2f}%",
                )

                if lt.get('min_target') and lt.get('max_target'):
                    st.markdown("**Analyst Target Range**")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption(f"**Min:** ₹{lt['min_target']:,.2f}")
                        st.caption(f"Upside: {lt['min_upside_pct']:+.2f}%")
                    with c2:
                        st.caption(f"**Max:** ₹{lt['max_target']:,.2f}")
                        st.caption(f"Upside: {lt['max_upside_pct']:+.2f}%")

                st.info("📊 **Note:** Analyst targets are consensus estimates. Always do your own research before investing.")
            else:
                st.info("ℹ️ " + lt.get('message', 'Long-term data not available'))

        # ── Additional info ──
        st.divider()
        with st.expander("📋 Additional Stock Information"):
            i1, i2, i3 = st.columns(3)
            with i1:
                if result.get('volume'):
                    st.metric("Volume", f"{result['volume']:,.0f}")
                if result.get('market_cap'):
                    st.metric("Market Cap", f"₹{result['market_cap']:,.0f} Cr")
            with i2:
                if result.get('pe_ratio'):
                    st.metric("P/E Ratio", f"{result['pe_ratio']:.2f}")
                if result.get('52w_high'):
                    st.metric("52W High", f"₹{result['52w_high']:,.2f}")
            with i3:
                if result.get('52w_low'):
                    st.metric("52W Low", f"₹{result['52w_low']:,.2f}")
                if result.get('dividend_yield'):
                    st.metric("Div Yield", f"{result['dividend_yield']:.2f}%")

else:
    # ── Quick-access buttons ──
    st.info("💡 Type a stock name or ticker above, then select from the dropdown")
    st.divider()
    st.markdown("### 🔥 Quick Access — Popular Stocks")

    popular = ["RELIANCE", "TCS", "INFY", "HDFCBANK",
               "ICICIBANK", "SBIN", "BHARTIARTL", "ITC"]

    cols = st.columns(4)
    for idx, ticker in enumerate(popular):
        with cols[idx % 4]:
            if st.button(ticker, use_container_width=True):
                # Pre-fill the search box by storing in session state
                st.session_state["_qs"] = ticker
                st.rerun()

    # Apply quick-select pre-fill on next run
    if "_qs" in st.session_state:
        qs = st.session_state.pop("_qs")
        # Patch: inject via query params to set text_input on rerun
        st.query_params["search"] = qs

st.divider()
st.caption("📊 Multi-source stock data  •  Recommendations are for informational purposes only  •  Data cached for 2 minutes")
