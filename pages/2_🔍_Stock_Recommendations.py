import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from data_sources import get_stock_recommendation_multi_source, get_all_nse_stocks
import time

st.set_page_config(page_title="Stock Recommendations", layout="wide", page_icon="🔍")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("Stock Recommendations")
st.caption("Search any NSE stock to get intraday and long-term analyst targets")
st.divider()

for key, default in [('rec_result', None), ('rec_ticker', None), ('rec_time', 0)]:
    if key not in st.session_state:
        st.session_state[key] = default

if 'all_stocks' not in st.session_state:
    with st.spinner("Loading NSE stock list..."):
        st.session_state.all_stocks = get_all_nse_stocks()

all_stocks = st.session_state.all_stocks

# Single search — type to filter, pick from dropdown. No second bar shown until something typed.
search_text = st.text_input(
    "Search",
    placeholder="Type ticker or company name (e.g. RELIANCE or Tata Consultancy)",
    label_visibility="collapsed",
    key="rec_search_input",
)

query = search_text.strip().lower()
filtered = [s for s in all_stocks if query in s.lower()] if query else []

selected_stock = ""
if query:
    if filtered:
        selected_stock = st.selectbox(
            "Select",
            options=[""] + filtered,
            index=0,
            label_visibility="collapsed",
            key="rec_select",
        )
        # Clear old result whenever the dropdown resets to blank (new search started)
        if not selected_stock and st.session_state.rec_result is not None:
            st.session_state.rec_result = None
            st.session_state.rec_ticker = None
    else:
        st.warning("No stocks matched your search. Try a different keyword.")
else:
    st.info("💡 Start typing a stock name or ticker above to search")

if selected_stock:
    ticker_input = selected_stock.split(" - ")[0].strip()
    current_time = time.time()
    use_cache = (
        st.session_state.rec_ticker == ticker_input
        and st.session_state.rec_result is not None
        and (current_time - st.session_state.rec_time) < 120
    )

    if not use_cache:
        with st.spinner(f"Fetching recommendations for {ticker_input}..."):
            result = get_stock_recommendation_multi_source(ticker_input)
            st.session_state.rec_result = result
            st.session_state.rec_ticker = ticker_input
            st.session_state.rec_time = current_time
    else:
        result = st.session_state.rec_result
        st.info("📌 Showing cached data (auto-refreshes every 2 minutes)")

    if result.get('error'):
        st.error(f"❌ {result['error']}")
        with st.expander("🔧 Troubleshooting"):
            st.markdown("""
- Rate limiting from data providers — wait 1–2 min and retry
- Try the exact NSE symbol (e.g. `RELIANCE`, `TCS`, `HDFCBANK`)
- Some smaller stocks may have limited data availability
""")
    else:
        st.markdown(f"### {result['name']} ({result['symbol']})")
        c1, c2 = st.columns([3, 1])
        with c1:
            st.metric("Current Market Price", f"₹{result['cmp']:,.2f}")
        with c2:
            st.caption(f"{result.get('data_source', 'Yahoo Finance')}")

        st.divider()
        intra_col, long_col = st.columns(2)

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
                st.info("⚠️ Intraday recommendations are for today's session only. Use proper risk management.")
            else:
                st.info("ℹ️ " + intra.get('message', 'Intraday data not available'))

        with long_col:
            st.markdown("#### 📈 Long-term Analyst Targets")
            lt = result.get('longterm') or {}
            if lt.get('available'):
                rec = lt['recommendation']
                icon = "🟢" if rec == "BUY" else "🔴" if rec == "SELL" else "🟡"
                st.markdown(f"{icon} **{rec}**")
                label = f"{lt['num_analysts']} analyst(s)" if lt.get('num_analysts') else "Technical analysis"
                st.caption(f"Based on {label}  •  {lt['timeframe']}")
                st.metric("Average Target", f"₹{lt['avg_target']:,.2f}", f"{lt['avg_upside_pct']:+.2f}%")
                if lt.get('min_target') and lt.get('max_target'):
                    st.markdown("**Target Range**")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption(f"**Min:** ₹{lt['min_target']:,.2f}  ({lt['min_upside_pct']:+.2f}%)")
                    with c2:
                        st.caption(f"**Max:** ₹{lt['max_target']:,.2f}  ({lt['max_upside_pct']:+.2f}%)")
                st.info("📊 Analyst targets are consensus estimates. Always do your own research.")
            else:
                st.info("ℹ️ " + lt.get('message', 'Long-term data not available'))

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

st.divider()
st.caption("Multi-source stock data  •  Recommendations are for informational purposes only  •  Data cached for 2 minutes")

