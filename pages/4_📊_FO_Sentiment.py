import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="F&O Sentiment", layout="wide", page_icon="📊")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("📊 F&O Sentiment")
st.caption("FII/DII cash flows + stock/index option chain OI — updated daily after market hours")
st.divider()

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/',
    'Connection': 'keep-alive',
}

def nse_session():
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get('https://www.nseindia.com', timeout=10)
    except Exception:
        pass
    return s

# ── Data fetchers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def fetch_fii_dii():
    s = nse_session()
    today = datetime.now()
    from_d = (today - timedelta(days=30)).strftime("%d-%m-%Y")
    to_d = today.strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/fiidiiTradeReact?from={from_d}&to={to_d}"
    try:
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            raw = r.json()
            rows = raw if isinstance(raw, list) else raw.get('data', [])
            if rows:
                df = pd.DataFrame(rows)
                # Normalise column names
                df.columns = [c.strip() for c in df.columns]
                return df, None
        return pd.DataFrame(), f"NSE returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=600)
def fetch_option_chain(symbol):
    s = nse_session()
    sym = symbol.upper().strip()
    # indices use different endpoint
    index_syms = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NIFTYNXT50']
    if sym in index_syms:
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}"
    else:
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={sym}"
    try:
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            records = data.get('records', {})
            oc_data = records.get('data', [])
            underlying = records.get('underlyingValue', 0)
            if oc_data:
                rows = []
                for item in oc_data:
                    strike = item.get('strikePrice', 0)
                    ce = item.get('CE', {})
                    pe = item.get('PE', {})
                    rows.append({
                        'Strike': strike,
                        'CE OI': ce.get('openInterest', 0) if ce else 0,
                        'CE Chg OI': ce.get('changeinOpenInterest', 0) if ce else 0,
                        'CE LTP': ce.get('lastPrice', 0) if ce else 0,
                        'PE OI': pe.get('openInterest', 0) if pe else 0,
                        'PE Chg OI': pe.get('changeinOpenInterest', 0) if pe else 0,
                        'PE LTP': pe.get('lastPrice', 0) if pe else 0,
                    })
                return pd.DataFrame(rows), float(underlying), None
            return pd.DataFrame(), 0.0, "No option chain data returned."
        return pd.DataFrame(), 0.0, f"NSE returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), 0.0, str(e)

def gauge(label, score):
    color = '#00c853' if score >= 20 else '#ff5252' if score <= -20 else '#ffd600'
    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=score,
        title={'text': label, 'font': {'size': 13}},
        number={'suffix': '', 'font': {'size': 22}},
        gauge={
            'axis': {'range': [-100, 100]},
            'bar': {'color': color},
            'steps': [
                {'range': [-100, -20], 'color': '#1a0000'},
                {'range': [-20,  20], 'color': '#0d0d1a'},
                {'range': [20,  100], 'color': '#001a00'},
            ],
        },
    ))
    fig.update_layout(height=210, margin=dict(l=20,r=20,t=50,b=10),
                      paper_bgcolor='rgba(0,0,0,0)', font_color='white')
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — FII / DII Cash Activity
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🌍 FII / DII Cash Market Activity — Last 30 Days")
st.caption("Net buy/sell in cash segment. Updates daily after market close.")

with st.spinner("Loading FII/DII data..."):
    fii_df, fii_err = fetch_fii_dii()

if fii_err and fii_df.empty:
    st.warning(f"⚠️ {fii_err}")
    st.info("NSE data may be unavailable right now. Try again after 6 PM IST on trading days.")
elif not fii_df.empty:
    cols = list(fii_df.columns)

    # Find key columns robustly
    date_col   = next((c for c in cols if 'date' in c.lower()), None)
    cat_col    = next((c for c in cols if 'category' in c.lower() or 'type' in c.lower()), None)
    buy_col    = next((c for c in cols if 'buy' in c.lower()), None)
    sell_col   = next((c for c in cols if 'sell' in c.lower()), None)
    net_col    = next((c for c in cols if 'net' in c.lower()), None)

    # Convert numeric cols
    for c in [buy_col, sell_col, net_col]:
        if c and c in fii_df.columns:
            fii_df[c] = pd.to_numeric(
                fii_df[c].astype(str).str.replace(',', '').str.replace('(', '-').str.replace(')', ''),
                errors='coerce'
            )

    # Convert date
    if date_col:
        fii_df[date_col] = pd.to_datetime(fii_df[date_col], errors='coerce')

    # ── Raw table (always show) ──
    display_df = fii_df.copy()
    st.dataframe(display_df.head(30), use_container_width=True)

    # ── Summary metrics — safely handle any number of net columns ──
    net_cols_found = [c for c in cols if 'net' in c.lower()]
    if net_cols_found:
        st.markdown("**30-Day Net Activity**")
        metric_cols = st.columns(min(len(net_cols_found), 4))
        for i, c in enumerate(net_cols_found[:4]):
            fii_df[c] = pd.to_numeric(
                fii_df[c].astype(str).str.replace(',', '').str.replace('(', '-').str.replace(')', ''),
                errors='coerce'
            )
            total = fii_df[c].sum()
            with metric_cols[i]:
                st.metric(c, f"₹{total:,.0f} Cr",
                          delta="Net Buying" if total > 0 else "Net Selling")

    # ── Chart ──
    if date_col and net_col and cat_col:
        categories = fii_df[cat_col].dropna().unique()
        fig_flow = go.Figure()
        for cat in categories:
            cat_df = fii_df[fii_df[cat_col] == cat].dropna(subset=[date_col, net_col])
            cat_df = cat_df.sort_values(date_col)
            colors = ['#00c853' if v >= 0 else '#ff5252' for v in cat_df[net_col]]
            fig_flow.add_bar(x=cat_df[date_col], y=cat_df[net_col],
                             name=str(cat), marker_color=colors)
        fig_flow.add_hline(y=0, line_color='white', line_width=0.8)
        fig_flow.update_layout(
            title="FII / DII Net Daily Flow (₹ Cr)",
            barmode='group', height=360,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color='white', xaxis_title='', yaxis_title='₹ Cr',
        )
        st.plotly_chart(fig_flow, use_container_width=True)
    elif date_col and net_col:
        net_by_day = fii_df.groupby(date_col)[net_col].sum().reset_index().sort_values(date_col)
        colors = ['#00c853' if v >= 0 else '#ff5252' for v in net_by_day[net_col]]
        fig2 = go.Figure(go.Bar(x=net_by_day[date_col], y=net_by_day[net_col], marker_color=colors))
        fig2.add_hline(y=0, line_color='white', line_width=0.8)
        fig2.update_layout(
            title="Net Daily Flow (₹ Cr)", height=320,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color='white',
        )
        st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Stock / Index Option Chain
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🎯 Stock / Index Option Chain Sentiment")
st.caption("Type a symbol below — works for indices (NIFTY, BANKNIFTY) and F&O stocks (RELIANCE, INFY, etc.)")

fo_query = st.text_input(
    "Search",
    placeholder="e.g. NIFTY, BANKNIFTY, RELIANCE, INFY",
    label_visibility="collapsed",
    key="fo_search",
)

fo_symbols = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY',
              'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK',
              'SBIN', 'BHARTIARTL', 'ITC', 'WIPRO', 'AXISBANK',
              'KOTAKBANK', 'LT', 'MARUTI', 'TITAN', 'SUNPHARMA',
              'TATAMOTORS', 'ADANIENT', 'BAJFINANCE', 'ZOMATO']

q = fo_query.strip().upper()
filtered_syms = [s for s in fo_symbols if q in s] if q else fo_symbols

selected_sym = st.selectbox(
    "Select",
    options=[""] + filtered_syms,
    index=0,
    label_visibility="collapsed",
    key="fo_select",
)

if selected_sym:
    with st.spinner(f"Fetching option chain for {selected_sym}..."):
        oc_df, underlying, oc_err = fetch_option_chain(selected_sym)

    if oc_err and oc_df.empty:
        st.warning(f"⚠️ {oc_err}")
        st.info("F&O data is available only for stocks in the F&O segment. Try NIFTY or BANKNIFTY.")
    elif not oc_df.empty:
        st.markdown(f"**{selected_sym}** — Spot: ₹{underlying:,.2f}")

        total_ce = oc_df['CE OI'].sum()
        total_pe = oc_df['PE OI'].sum()
        pcr = round(total_pe / total_ce, 2) if total_ce > 0 else 0
        sentiment_score = round(min(max((pcr - 1) * 100, -100), 100), 1)
        pcr_label = "🟢 Bullish" if pcr > 1.2 else "🔴 Bearish" if pcr < 0.8 else "🟡 Neutral"

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total CE OI", f"{int(total_ce):,}")
        with m2:
            st.metric("Total PE OI", f"{int(total_pe):,}")
        with m3:
            st.metric("PCR", f"{pcr:.2f}", delta=pcr_label)
        with m4:
            st.plotly_chart(gauge(f"{selected_sym} Mood", sentiment_score),
                            use_container_width=True)

        # OI bar chart around ATM
        oc_sorted = oc_df.sort_values('Strike').reset_index(drop=True)
        if underlying > 0:
            atm_idx = (oc_sorted['Strike'] - underlying).abs().idxmin()
            window = oc_sorted.iloc[max(0, atm_idx - 8): atm_idx + 9]
        else:
            window = oc_sorted.tail(20)

        fig_oi = go.Figure()
        fig_oi.add_bar(x=window['Strike'].astype(str), y=window['CE OI'],
                       name='CE OI (Resistance)', marker_color='#ff5252')
        fig_oi.add_bar(x=window['Strike'].astype(str), y=window['PE OI'],
                       name='PE OI (Support)', marker_color='#00c853')
        if underlying > 0:
            fig_oi.add_vline(x=str(int(underlying)), line_dash='dash',
                             line_color='white', annotation_text='ATM ▲',
                             annotation_position='top')
        fig_oi.update_layout(
            title=f"{selected_sym} — OI Around ATM (spot ₹{underlying:,.0f})",
            barmode='group', height=380,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color='white', legend=dict(orientation='h', y=1.1),
            xaxis_title='Strike Price', yaxis_title='Open Interest',
        )
        st.plotly_chart(fig_oi, use_container_width=True)

        # Top strikes table
        st.markdown("**Top 20 Strikes by Total OI**")
        top20 = oc_df.copy()
        top20['Total OI'] = top20['CE OI'] + top20['PE OI']
        top20 = top20.sort_values('Total OI', ascending=False).head(20).reset_index(drop=True)
        top20.index += 1
        st.dataframe(top20, use_container_width=True)
else:
    st.info("💡 Type a symbol above or pick from the dropdown to see option chain sentiment")

st.divider()
with st.expander("ℹ️ How to interpret F&O sentiment"):
    st.markdown("""
**PCR (Put-Call Ratio) = Total PE OI ÷ Total CE OI**
- PCR > 1.2 → Bullish (more put writing = market expects support)
- PCR < 0.8 → Bearish (more call writing = market expects resistance)
- PCR 0.8–1.2 → Neutral / sideways

**Highest CE OI strike** = strongest resistance (market may struggle to break above)
**Highest PE OI strike** = strongest support (market likely to bounce from here)

**FII/DII Cash Flow**
- FII net buyers for 5+ consecutive days → strong institutional confidence
- DII buying while FII sells → domestic absorption (often marks a bottom)

Data refreshes 30 min for FII/DII, 10 min for option chains.
    """)

st.caption("📊 Source: NSE India  •  FII/DII every 30 min, option chain every 10 min")
