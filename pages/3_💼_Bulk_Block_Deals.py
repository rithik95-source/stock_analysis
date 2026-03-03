import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import urllib.parse

st.set_page_config(page_title="F&O Sentiment", layout="wide", page_icon="📊")

# 1. Strict Montserrat Font Enforcement
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"], [class*="st-"], .stDataFrame, .stSelectbox { 
        font-family: 'Montserrat', sans-serif !important; 
    }
    h1, h2, h3, h4, h5, h6 { 
        font-family: 'Montserrat', sans-serif !important; 
        font-weight: 600 !important; 
    }
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
                df.columns = [c.strip() for c in df.columns]
                return df, None
        return pd.DataFrame(), f"NSE returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=86400) # Caches for 24 hours
def fetch_live_fno_symbols():
    try:
        # Fetch live list of tradable instruments from Zerodha's open API
        df = pd.read_csv("https://api.kite.trade/instruments")
        # Filter for NSE Futures segment to get unique F&O underlying names
        live_symbols = df[df['segment'] == 'NFO-FUT']['name'].unique().tolist()
        return sorted(live_symbols)
    except Exception:
        # Fallback list if the request fails
        return ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'RELIANCE', 'HDFCBANK', 'ITC', 'INFY', 'TCS']

@st.cache_data(ttl=600)
def fetch_option_chain(symbol):
    s = nse_session()
    sym = symbol.upper().strip()
    index_syms = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NIFTYNXT50']
    
    if sym in index_syms:
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}"
    else:
        # Safely encode symbols like M&M
        sym_encoded = urllib.parse.quote(sym)
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={sym_encoded}"
        
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
        title={'text': label, 'font': {'size': 14, 'family': 'Montserrat'}},
        number={'suffix': '', 'font': {'size': 24, 'family': 'Montserrat'}},
        gauge={
            'axis': {'range': [-100, 100], 'tickfont': {'family': 'Montserrat'}},
            'bar': {'color': color},
            'steps': [
                {'range': [-100, -20], 'color': 'rgba(255, 82, 82, 0.2)'},
                {'range': [-20,  20], 'color': 'rgba(255, 214, 0, 0.2)'},
                {'range': [20,  100], 'color': 'rgba(0, 200, 83, 0.2)'},
            ],
        },
    ))
    fig.update_layout(height=210, margin=dict(l=20,r=20,t=50,b=10),
                      paper_bgcolor='rgba(0,0,0,0)', font_color='white')
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — FII / DII Cash Activity
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🌍 FII / DII Cash Market Activity")
st.caption("Note: The free NSE API currently returns provisional data for the latest trading day.")

with st.spinner("Loading FII/DII data..."):
    fii_df, fii_err = fetch_fii_dii()

if fii_err and fii_df.empty:
    st.warning(f"⚠️ {fii_err}")
    st.info("NSE data may be unavailable right now. Try again after 6 PM IST on trading days.")
elif not fii_df.empty:
    cols = list(fii_df.columns)

    date_col   = next((c for c in cols if 'date' in c.lower()), None)
    cat_col    = next((c for c in cols if 'category' in c.lower() or 'type' in c.lower()), None)
    buy_col    = next((c for c in cols if 'buy' in c.lower()), None)
    sell_col   = next((c for c in cols if 'sell' in c.lower()), None)
    net_col    = next((c for c in cols if 'net' in c.lower()), None)

    for c in [buy_col, sell_col, net_col]:
        if c and c in fii_df.columns:
            fii_df[c] = pd.to_numeric(
                fii_df[c].astype(str).str.replace(',', '').str.replace('(', '-').str.replace(')', ''),
                errors='coerce'
            )

    if date_col:
        fii_df[date_col] = pd.to_datetime(fii_df[date_col], errors='coerce')

    # Data Table Format
    display_df = fii_df.copy()
    st.dataframe(
        display_df,
        column_config={
            cat_col: "Category",
            date_col: st.column_config.DateColumn("Date", format="DD-MMM-YYYY"),
            buy_col: st.column_config.NumberColumn("Buy Value (₹ Cr)", format="%,.2f"),
            sell_col: st.column_config.NumberColumn("Sell Value (₹ Cr)", format="%,.2f"),
            net_col: st.column_config.NumberColumn("Net Value (₹ Cr)", format="%,.2f"),
        },
        hide_index=True,
        use_container_width=True
    )

    # Net Activity Summary
    if net_col:
        st.markdown("**Latest Net Activity**")
        metric_cols = st.columns(2)
        if cat_col:
            categories = fii_df[cat_col].dropna().unique()
            for i, cat in enumerate(categories[:2]):
                cat_val = fii_df[fii_df[cat_col] == cat][net_col].sum()
                with metric_cols[i]:
                    st.metric(f"{cat} Net Value", f"₹ {cat_
