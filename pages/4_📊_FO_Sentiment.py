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
st.caption("FII / DII / Pro participant-wise open interest — 1-day lag after market hours")
st.divider()

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/',
    'Connection': 'keep-alive',
}

# ── Data fetchers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def fetch_participant_oi():
    """Participant-wise F&O OI from NSE (updates daily after market hours)."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass
    url = "https://www.nseindia.com/api/historical/fiiDiiData"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return pd.DataFrame(data), None
    except Exception as e:
        pass

    # Alternative: participant-wise OI
    url2 = "https://www.nseindia.com/api/participantOI"
    try:
        r2 = session.get(url2, headers=NSE_HEADERS, timeout=15)
        if r2.status_code == 200:
            data = r2.json()
            return pd.DataFrame(data.get('data', data)), None
    except Exception as e:
        return pd.DataFrame(), str(e)
    return pd.DataFrame(), "Could not fetch participant OI data."

@st.cache_data(ttl=1800)
def fetch_fii_dii_activity():
    """FII/DII cash market activity — daily net buy/sell in cash segment."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    # Try NSE FII/DII endpoint
    today = datetime.now()
    date_str = today.strftime("%d-%m-%Y")
    from_date = (today - timedelta(days=30)).strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/fiidiiTradeReact?from={from_date}&to={date_str}"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            rows = data if isinstance(data, list) else data.get('data', [])
            if rows:
                df = pd.DataFrame(rows)
                return df, None
    except Exception:
        pass

    # Try alternate endpoint
    url2 = "https://www.nseindia.com/api/fiidiiTradeReact"
    try:
        r2 = session.get(url2, headers=NSE_HEADERS, timeout=15)
        if r2.status_code == 200:
            data = r2.json()
            rows = data if isinstance(data, list) else data.get('data', [])
            if rows:
                return pd.DataFrame(rows), None
    except Exception as e:
        return pd.DataFrame(), str(e)

    return pd.DataFrame(), "FII/DII data not available right now."

@st.cache_data(ttl=600)
def fetch_stock_oi(symbol):
    """Fetch option chain OI for a specific stock from NSE."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass
    url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol.upper()}"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            records = data.get('records', {})
            oc_data = records.get('data', [])
            if oc_data:
                rows = []
                for item in oc_data:
                    strike = item.get('strikePrice', 0)
                    ce = item.get('CE', {})
                    pe = item.get('PE', {})
                    if ce or pe:
                        rows.append({
                            'Strike': strike,
                            'CE OI': ce.get('openInterest', 0),
                            'CE Chg OI': ce.get('changeinOpenInterest', 0),
                            'CE LTP': ce.get('lastPrice', 0),
                            'PE OI': pe.get('openInterest', 0),
                            'PE Chg OI': pe.get('changeinOpenInterest', 0),
                            'PE LTP': pe.get('lastPrice', 0),
                        })
                df = pd.DataFrame(rows)
                underlying = records.get('underlyingValue', 0)
                return df, underlying, None
            return pd.DataFrame(), 0, "No option chain data."
        return pd.DataFrame(), 0, f"NSE returned {r.status_code}."
    except Exception as e:
        return pd.DataFrame(), 0, str(e)

def gauge_chart(label, value, min_val=-100, max_val=100):
    """Render a simple sentiment gauge."""
    color = "#00c853" if value >= 20 else "#ff5252" if value <= -20 else "#ffd600"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': label, 'font': {'size': 14}},
        gauge={
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': color},
            'steps': [
                {'range': [min_val, -20], 'color': '#2d0a0a'},
                {'range': [-20, 20], 'color': '#1a1a2e'},
                {'range': [20, max_val], 'color': '#0a2d0a'},
            ],
            'threshold': {'line': {'color': 'white', 'width': 2}, 'thickness': 0.75, 'value': value},
        },
        number={'suffix': '%', 'font': {'size': 20}},
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10), paper_bgcolor='rgba(0,0,0,0)', font_color='white')
    return fig

# ── FII/DII Overview ───────────────────────────────────────────────────────────
st.markdown("### 🌍 FII / DII Cash Market Activity (Last 30 Days)")

with st.spinner("Fetching FII/DII data..."):
    fii_df, fii_err = fetch_fii_dii_activity()

if fii_err and fii_df.empty:
    st.warning(f"⚠️ {fii_err}")
    st.info("NSE may require a cookie session. Try refreshing or check NSE website directly.")
else:
    if not fii_df.empty:
        # Try to identify FII/DII columns
        cols = fii_df.columns.tolist()
        st.dataframe(fii_df.head(20), use_container_width=True)

        # If we have numeric net columns, compute totals
        net_cols = [c for c in cols if 'net' in c.lower() or 'NET' in c]
        if net_cols:
            for c in net_cols:
                fii_df[c] = pd.to_numeric(fii_df[c].astype(str).str.replace(',', ''), errors='coerce')
            st.markdown("**30-Day Net Activity**")
            nc1, nc2 = st.columns(len(net_cols))
            for i, c in enumerate(net_cols[:2]):
                total = fii_df[c].sum()
                with [nc1, nc2][i]:
                    st.metric(c, f"₹{total:,.0f} Cr", delta=f"{'Buying' if total > 0 else 'Selling'}")
    else:
        st.info("No FII/DII data returned. NSE data may be unavailable outside market hours.")

st.divider()

# ── Stock-wise Option Chain ────────────────────────────────────────────────────
st.markdown("### 🎯 Stock-wise F&O Sentiment")
st.caption("Option chain OI — high PE OI = support, high CE OI = resistance. PCR > 1 = bullish.")

search_fo = st.text_input(
    "Search F&O stock",
    placeholder="Type NSE symbol (e.g. RELIANCE, BANKNIFTY, NIFTY)",
    label_visibility="collapsed",
    key="fo_search",
)

if search_fo.strip():
    sym = search_fo.strip().upper()
    with st.spinner(f"Fetching option chain for {sym}..."):
        oc_df, underlying, oc_err = fetch_stock_oi(sym)

    if oc_err and oc_df.empty:
        st.warning(f"⚠️ {oc_err}")
        st.info("Try index symbols like **NIFTY**, **BANKNIFTY**, or F&O stocks like **RELIANCE**, **INFY**.")
    else:
        st.markdown(f"**{sym}** — Underlying: ₹{underlying:,.2f}")

        # PCR
        total_ce_oi = oc_df['CE OI'].sum()
        total_pe_oi = oc_df['PE OI'].sum()
        pcr = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0
        sentiment_score = min(max((pcr - 1) * 100, -100), 100)

        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total CE OI", f"{total_ce_oi:,.0f}")
        with m2:
            st.metric("Total PE OI", f"{total_pe_oi:,.0f}")
        with m3:
            pcr_delta = "Bullish" if pcr > 1 else "Bearish" if pcr < 0.8 else "Neutral"
            st.metric("Put-Call Ratio (PCR)", f"{pcr:.2f}", delta=pcr_delta)

        st.plotly_chart(gauge_chart(f"{sym} Sentiment", round(sentiment_score, 1)), use_container_width=False)

        # OI chart around ATM
        if underlying > 0 and not oc_df.empty:
            oc_sorted = oc_df.sort_values('Strike').reset_index(drop=True)
            atm_idx = (oc_sorted['Strike'] - underlying).abs().idxmin()
            window = oc_sorted.iloc[max(0, atm_idx - 10): atm_idx + 11]

            fig_oi = go.Figure()
            fig_oi.add_bar(x=window['Strike'], y=window['CE OI'], name='CE OI', marker_color='#ff5252')
            fig_oi.add_bar(x=window['Strike'], y=window['PE OI'], name='PE OI', marker_color='#00c853')
            fig_oi.add_vline(x=underlying, line_dash='dash', line_color='white', annotation_text='ATM')
            fig_oi.update_layout(
                title=f"{sym} — Open Interest Around ATM (₹{underlying:,.0f})",
                barmode='group', height=380,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font_color='white', legend=dict(orientation='h'),
                xaxis_title='Strike Price', yaxis_title='Open Interest',
            )
            st.plotly_chart(fig_oi, use_container_width=True)

        # Top OI strikes table
        st.markdown("**Top 20 Strikes by Open Interest**")
        top_oi = oc_df.copy()
        top_oi['Total OI'] = top_oi['CE OI'] + top_oi['PE OI']
        top_oi = top_oi.sort_values('Total OI', ascending=False).head(20).reset_index(drop=True)
        top_oi.index += 1
        st.dataframe(top_oi, use_container_width=True)
else:
    st.info("💡 Enter an F&O stock or index symbol above to see option chain sentiment")

st.divider()

# ── Explainer ──────────────────────────────────────────────────────────────────
with st.expander("ℹ️ How to interpret F&O sentiment"):
    st.markdown("""
**Put-Call Ratio (PCR)**
- PCR > 1.2 → Bullish (more PEs bought = institutions hedging downside, but also retail buying protection)
- PCR < 0.8 → Bearish (more CEs sold = resistance building)
- PCR 0.8–1.2 → Neutral

**Open Interest**
- Highest **CE OI** strike = strong resistance (market may struggle to cross)
- Highest **PE OI** strike = strong support (market likely to bounce from here)

**Change in OI**
- Rising CE OI at a strike → fresh short positions / resistance building
- Rising PE OI at a strike → fresh support / institutional protection

**FII/DII Cash Activity**
- FII net buyers over 5+ consecutive sessions → strong institutional conviction
- DII buying while FII sells → domestic institutions absorbing FII outflows (often supportive)

Data updates daily after market close (~6 PM IST).
    """)

st.caption("📊 Data source: NSE India  •  F&O data refreshed every 30 minutes")
