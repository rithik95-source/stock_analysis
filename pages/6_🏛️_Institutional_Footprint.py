import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Institutional Footprint", layout="wide", page_icon="🏛️")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
    .metric-card { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("🏛️ Institutional Footprint")
st.caption("Delivery %, volume spikes, FII/DII flows — proxy signals for institutional activity")
st.divider()

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/',
}

# ── Data fetchers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_stock_delivery(symbol):
    """Fetch delivery percentage and volume data from NSE equity history."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    today = datetime.now()
    from_d = (today - timedelta(days=60)).strftime("%d-%m-%Y")
    to_d = today.strftime("%d-%m-%Y")

    url = f"https://www.nseindia.com/api/historical/securityArchives?from={from_d}&to={to_d}&symbol={symbol.upper()}&dataType=priceVolumeDeliverable&series=EQ"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            rows = data.get('data', [])
            if rows:
                df = pd.DataFrame(rows)
                # Standardise columns
                col_map = {
                    'CH_TIMESTAMP': 'Date',
                    'CH_CLOSING_PRICE': 'Close',
                    'CH_TOT_TRADED_QTY': 'Volume',
                    'CH_DELIV_QTY': 'Delivery Qty',
                    'CH_DELIV_PER': 'Delivery %',
                    'CH_OPENING_PRICE': 'Open',
                    'CH_TRADE_HIGH_PRICE': 'High',
                    'CH_TRADE_LOW_PRICE': 'Low',
                }
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                for col in ['Close', 'Volume', 'Delivery Qty', 'Delivery %', 'Open', 'High', 'Low']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df = df.sort_values('Date')
                return df, None
            return pd.DataFrame(), "No price/delivery data found."
        return pd.DataFrame(), f"NSE returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=1800)
def fetch_institutional_bulk_history(symbol, days=90):
    """Fetch all bulk/block deals for a stock over past N days."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    today = datetime.now()
    from_d = (today - timedelta(days=days)).strftime("%d-%m-%Y")
    to_d = today.strftime("%d-%m-%Y")

    results = []
    for endpoint in ['bulk-deals', 'block-deals']:
        url = f"https://www.nseindia.com/api/historical/{endpoint}?from={from_d}&to={to_d}&symbol={symbol.upper()}"
        try:
            r = session.get(url, headers=NSE_HEADERS, timeout=15)
            if r.status_code == 200:
                data = r.json()
                deals = data.get('data', [])
                for d in deals:
                    d['deal_type_source'] = endpoint.replace('-deals', '').title()
                results.extend(deals)
        except Exception:
            continue

    if results:
        df = pd.DataFrame(results)
        return df, None
    return pd.DataFrame(), f"No bulk/block deals found for {symbol} in last {days} days."

@st.cache_data(ttl=1800)
def fetch_top_delivery_stocks():
    """Fetch top stocks by delivery % from NSE (institutional buying proxy)."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    url = "https://www.nseindia.com/api/live-analysis-variations?index=gainers"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            rows = data.get('NIFTY', {}).get('data', []) or data.get('data', [])
            if rows:
                return pd.DataFrame(rows), None
    except Exception:
        pass

    # Alternative: securities in F&O with high delivery
    url2 = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20500"
    try:
        r2 = session.get(url2, headers=NSE_HEADERS, timeout=15)
        if r2.status_code == 200:
            data = r2.json()
            rows = data.get('data', [])
            if rows:
                return pd.DataFrame(rows), None
    except Exception as e:
        return pd.DataFrame(), str(e)

    return pd.DataFrame(), "Could not fetch top delivery stocks."

@st.cache_data(ttl=1800)
def fetch_fii_dii_trend():
    """Fetch FII/DII 30-day trend from NSE."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    today = datetime.now()
    from_d = (today - timedelta(days=30)).strftime("%d-%m-%Y")
    to_d = today.strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/fiidiiTradeReact?from={from_d}&to={to_d}"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            rows = data if isinstance(data, list) else data.get('data', [])
            if rows:
                df = pd.DataFrame(rows)
                return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)
    return pd.DataFrame(), "FII/DII trend not available."

def signal_badge(value, thresholds=(40, 60)):
    """Return colour-coded signal based on delivery %."""
    lo, hi = thresholds
    if value >= hi:
        return "🟢 High Institutional Activity", "#00c853"
    elif value >= lo:
        return "🟡 Moderate", "#ffd600"
    else:
        return "⚪ Retail-dominated", "#9e9e9e"

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Stock-wise Deep Dive
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🔍 Stock-wise Institutional Footprint")

search_inst = st.text_input(
    "Search",
    placeholder="Type NSE symbol (e.g. RELIANCE, INFY, ZOMATO)",
    label_visibility="collapsed",
    key="inst_search",
)

if search_inst.strip():
    sym = search_inst.strip().upper()

    col_del, col_bulk = st.columns([3, 2])

    # ── Delivery % Analysis ──────────────────────────────────────────────────
    with col_del:
        st.markdown(f"#### 📦 Delivery % — {sym}")
        st.caption("Delivery > 60% on high volume = strong institutional participation")
        with st.spinner("Fetching delivery data..."):
            del_df, del_err = fetch_stock_delivery(sym)

        if del_err and del_df.empty:
            st.warning(f"⚠️ {del_err}")
        elif not del_df.empty and 'Delivery %' in del_df.columns:
            # Latest stats
            latest = del_df.iloc[-1]
            avg_del = del_df['Delivery %'].mean()
            latest_del = latest.get('Delivery %', 0)
            avg_vol = del_df['Volume'].mean() if 'Volume' in del_df.columns else 0
            latest_vol = latest.get('Volume', 0)

            badge, color = signal_badge(latest_del)
            st.markdown(f"**Signal:** <span style='color:{color};font-weight:600'>{badge}</span>", unsafe_allow_html=True)

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Latest Delivery %", f"{latest_del:.1f}%",
                          delta=f"{latest_del - avg_del:+.1f}% vs avg")
            with m2:
                vol_delta = ((latest_vol - avg_vol) / avg_vol * 100) if avg_vol else 0
                st.metric("Today's Volume", f"{int(latest_vol):,}",
                          delta=f"{vol_delta:+.1f}% vs avg")
            with m3:
                if 'Close' in del_df.columns:
                    prev_close = del_df.iloc[-2]['Close'] if len(del_df) >= 2 else latest['Close']
                    chg = ((latest['Close'] - prev_close) / prev_close * 100) if prev_close else 0
                    st.metric("Close", f"₹{latest['Close']:,.2f}", delta=f"{chg:+.2f}%")

            # Delivery % chart
            fig_del = go.Figure()
            if 'Date' in del_df.columns:
                fig_del.add_bar(
                    x=del_df['Date'], y=del_df['Delivery %'],
                    marker_color=[
                        '#00c853' if v >= 60 else '#ffd600' if v >= 40 else '#9e9e9e'
                        for v in del_df['Delivery %']
                    ],
                    name='Delivery %'
                )
                fig_del.add_hline(y=60, line_dash='dash', line_color='#00c853',
                                  annotation_text='60% (Institutional)')
                fig_del.add_hline(y=40, line_dash='dot', line_color='#ffd600',
                                  annotation_text='40% (Moderate)')
                fig_del.update_layout(
                    title=f"{sym} — Delivery % (60 Days)",
                    height=300, paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)', font_color='white',
                    yaxis_title='Delivery %', xaxis_title='',
                    showlegend=False,
                )
                st.plotly_chart(fig_del, use_container_width=True)

            # Volume vs delivery scatter
            if 'Volume' in del_df.columns and 'Date' in del_df.columns:
                fig_vol = go.Figure()
                fig_vol.add_scatter(
                    x=del_df['Date'], y=del_df['Volume'],
                    mode='lines', line=dict(color='#00b4d8', width=1.5),
                    fill='tozeroy', fillcolor='rgba(0,180,216,0.08)',
                    name='Volume'
                )
                fig_vol.update_layout(
                    title=f"{sym} — Volume (60 Days)",
                    height=220, paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)', font_color='white',
                    yaxis_title='Volume', showlegend=False,
                )
                st.plotly_chart(fig_vol, use_container_width=True)
        else:
            st.info("Delivery data not available for this symbol.")

    # ── Institutional Deals Timeline ─────────────────────────────────────────
    with col_bulk:
        st.markdown(f"#### 🏦 Institutional Deals — {sym} (Last 90 Days)")
        st.caption("All bulk & block deals involving large entities")
        with st.spinner("Fetching institutional deals..."):
            inst_df, inst_err = fetch_institutional_bulk_history(sym)

        if inst_err and inst_df.empty:
            st.warning(f"⚠️ {inst_err}")
        elif not inst_df.empty:
            rename = {
                'tradeDate': 'Date', 'clientName': 'Entity',
                'dealType': 'Buy/Sell', 'quantity': 'Qty',
                'price': 'Price (₹)', 'deal_type_source': 'Deal Kind',
            }
            show_df = inst_df.rename(columns={k: v for k, v in rename.items() if k in inst_df.columns})

            if 'Qty' in show_df.columns:
                show_df['Qty'] = pd.to_numeric(show_df['Qty'], errors='coerce').apply(
                    lambda x: f"{int(x):,}" if pd.notna(x) else '-')
            if 'Price (₹)' in show_df.columns:
                show_df['Price (₹)'] = pd.to_numeric(show_df['Price (₹)'], errors='coerce').apply(
                    lambda x: f"₹{x:,.2f}" if pd.notna(x) else '-')

            display_cols = [c for c in ['Date', 'Entity', 'Buy/Sell', 'Qty', 'Price (₹)', 'Deal Kind'] if c in show_df.columns]
            st.dataframe(show_df[display_cols].head(20).reset_index(drop=True), use_container_width=True)

            # Buy vs Sell breakdown
            if 'Buy/Sell' in show_df.columns:
                counts = inst_df['dealType'].str.upper().value_counts()
                buys = counts.get('BUY', counts.get('B', 0))
                sells = counts.get('SELL', counts.get('S', 0))
                if buys + sells > 0:
                    st.markdown("**Deal Breakdown (90 days)**")
                    b1, b2 = st.columns(2)
                    with b1:
                        st.metric("🟢 Buys", int(buys))
                    with b2:
                        st.metric("🔴 Sells", int(sells))
        else:
            st.info(f"No institutional bulk/block deals found for **{sym}** in the last 90 days.")
else:
    st.info("💡 Enter an NSE symbol above to analyse its institutional footprint")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Market-wide FII/DII Trend
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🌍 Market-wide FII / DII Flow Trend (Last 30 Days)")
st.caption("Net buy/sell in the cash segment — shows broad institutional mood")

with st.spinner("Fetching FII/DII trend..."):
    fii_trend_df, fii_trend_err = fetch_fii_dii_trend()

if fii_trend_err and fii_trend_df.empty:
    st.warning(f"⚠️ {fii_trend_err}")
else:
    if not fii_trend_df.empty:
        cols = fii_trend_df.columns.tolist()

        # Try to find date and net columns
        date_col = next((c for c in cols if 'date' in c.lower()), None)
        fii_net_col = next((c for c in cols if 'fii' in c.lower() and 'net' in c.lower()), None)
        dii_net_col = next((c for c in cols if 'dii' in c.lower() and 'net' in c.lower()), None)

        if date_col and (fii_net_col or dii_net_col):
            fii_trend_df[date_col] = pd.to_datetime(fii_trend_df[date_col], errors='coerce')
            if fii_net_col:
                fii_trend_df[fii_net_col] = pd.to_numeric(
                    fii_trend_df[fii_net_col].astype(str).str.replace(',', ''), errors='coerce')
            if dii_net_col:
                fii_trend_df[dii_net_col] = pd.to_numeric(
                    fii_trend_df[dii_net_col].astype(str).str.replace(',', ''), errors='coerce')

            fig_flow = go.Figure()
            if fii_net_col:
                fig_flow.add_bar(
                    x=fii_trend_df[date_col], y=fii_trend_df[fii_net_col],
                    name='FII Net',
                    marker_color=[('#00c853' if v >= 0 else '#ff5252') for v in fii_trend_df[fii_net_col].fillna(0)]
                )
            if dii_net_col:
                fig_flow.add_bar(
                    x=fii_trend_df[date_col], y=fii_trend_df[dii_net_col],
                    name='DII Net',
                    marker_color=[('#00b4d8' if v >= 0 else '#ff9800') for v in fii_trend_df[dii_net_col].fillna(0)]
                )

            fig_flow.add_hline(y=0, line_color='white', line_width=0.8)
            fig_flow.update_layout(
                title="FII / DII Net Activity (₹ Cr)",
                barmode='group', height=380,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color='white', xaxis_title='', yaxis_title='Net ₹ Cr',
            )
            st.plotly_chart(fig_flow, use_container_width=True)

            # Summary metrics
            if fii_net_col:
                total_fii = fii_trend_df[fii_net_col].sum()
                consec = 0
                for v in fii_trend_df[fii_net_col].dropna().iloc[::-1]:
                    if (total_fii > 0 and v > 0) or (total_fii < 0 and v < 0):
                        consec += 1
                    else:
                        break

                sm1, sm2 = st.columns(2)
                with sm1:
                    st.metric("FII 30-Day Net", f"₹{total_fii:,.0f} Cr",
                              delta="Net Buyer" if total_fii > 0 else "Net Seller")
                with sm2:
                    st.metric("Consecutive Sessions", f"{consec}",
                              delta="Buying streak" if total_fii > 0 else "Selling streak")
        else:
            # Show raw table if columns not recognised
            st.dataframe(fii_trend_df.head(20), use_container_width=True)
    else:
        st.info("FII/DII data not returned. NSE data may be unavailable outside market hours.")

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — High Delivery Screener
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 📋 High Delivery % Stocks (Institutional Buying Proxy)")
st.caption("Stocks where delivery % is unusually high today — likely institutional accumulation")

with st.spinner("Fetching high delivery stocks..."):
    top_df, top_err = fetch_top_delivery_stocks()

if top_err and top_df.empty:
    st.warning(f"⚠️ {top_err}")
    st.info("You can check Chartink.com or Trendlyne for high-delivery screeners if NSE data is unavailable.")
else:
    if not top_df.empty:
        # Try to find delivery column
        del_cols = [c for c in top_df.columns if 'deliv' in c.lower() or 'delivery' in c.lower()]
        sym_col = next((c for c in top_df.columns if 'symbol' in c.lower()), None)

        if del_cols and sym_col:
            show = top_df[[sym_col] + del_cols].copy()
            for c in del_cols:
                show[c] = pd.to_numeric(show[c], errors='coerce')
            show = show.sort_values(del_cols[0], ascending=False).head(20).reset_index(drop=True)
            show.index += 1
            st.dataframe(show, use_container_width=True)
        else:
            st.dataframe(top_df.head(20), use_container_width=True)
    else:
        st.info("No screener data available.")

# ── Explainer ──────────────────────────────────────────────────────────────────
st.divider()
with st.expander("ℹ️ How to use the Institutional Footprint page"):
    st.markdown("""
**Delivery %**
Delivery percentage = shares actually taken delivery of ÷ total traded shares × 100.
High delivery % means people are holding, not day-trading.
- **> 60%** on above-average volume → Strong institutional accumulation signal
- **< 30%** → Mostly speculative / intraday activity

**Institutional Deals (Bulk/Block)**
Any single trade > 0.5% of equity is a bulk deal. Shows exactly who bought/sold and how much.
Filter for MF names, FII custodian names (Citibank NA, HSBC etc.), and insurance companies.

**FII/DII Flow**
- FII = Foreign Institutional Investors (overseas funds, hedge funds)
- DII = Domestic Institutional Investors (LIC, domestic MFs, banks)
- When both buy simultaneously → very strong market signal
- When FII sells but DII buys → domestic absorption (often marks bottom)

**Pro Tip:** Stocks showing high delivery % + institutional bulk deal buys + FII buying in the same week = highest conviction signal.
    """)

st.caption("📊 Sources: NSE India  •  Delivery data every 10 min, FII/DII every 30 min")
