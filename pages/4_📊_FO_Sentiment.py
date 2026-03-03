import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import urllib.parse
import time

st.set_page_config(page_title="F&O Sentiment", layout="wide", page_icon="📊")

# 1. CSS Fix: Added protection for Material Icons to stop the _arrow_right_ overlap
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
    
    /* Protect Streamlit's native icons from the font override */
    .material-symbols-rounded, .material-symbols-outlined {
        font-family: 'Material Symbols Rounded' !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 F&O Sentiment")
st.caption("FII/DII cash flows + stock/index option chain OI — updated daily after market hours")
st.divider()

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# 2. Enhanced Session Generator to bypass weekend/holiday bot blocks
def nse_session():
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        # Step 1: Hit homepage to get initial cookies
        s.get('https://www.nseindia.com', timeout=10)
        time.sleep(0.5)
        # Step 2: Hit option chain page to get specific API clearance cookies
        s.get('https://www.nseindia.com/option-chain', timeout=10)
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

@st.cache_data(ttl=86400) 
def fetch_fno_mapping():
    try:
        df = pd.read_csv("https://api.kite.trade/instruments")
        
        fno_underlyings = set(df[df['segment'] == 'NFO-FUT']['name'].dropna().unique())
        
        nse_df = df[df['segment'] == 'NSE'][['tradingsymbol', 'name']].dropna()
        fno_df = nse_df[nse_df['tradingsymbol'].isin(fno_underlyings)]
        
        mapping = []
        for _, row in fno_df.iterrows():
            mapping.append(f"{row['tradingsymbol']} - {row['name']}")
            
        # 3. Explicitly adding Indian Indices
        indices = [
            'NIFTY - NIFTY 50 INDEX', 
            'BANKNIFTY - NIFTY BANK INDEX', 
            'FINNIFTY - NIFTY FIN SERVICE INDEX', 
            'MIDCPNIFTY - NIFTY MIDCAP SELECT INDEX', 
            'NIFTYNXT50 - NIFTY NEXT 50 INDEX'
        ]
        
        return sorted(indices) + sorted(mapping)
    except Exception:
        return ['NIFTY - NIFTY 50', 'BANKNIFTY - NIFTY BANK', 'RELIANCE - RELIANCE INDUSTRIES LTD']

@st.cache_data(ttl=600)
def fetch_option_chain(symbol):
    s = nse_session()
    sym = symbol.upper().strip()
    index_syms = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NIFTYNXT50']
    
    if sym in index_syms:
        url = f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}"
    else:
        sym_encoded = urllib.parse.quote(sym)
        url = f"https://www.nseindia.com/api/option-chain-equities?symbol={sym_encoded}"
        
    try:
        r = s.get(url, timeout=15)
        
        # Retry mechanism if unauthorized or blocked initially
        if r.status_code in [401, 403]:
            s = nse_session() 
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
            return pd.DataFrame(), 0.0, "No option chain data returned. (Holiday/Weekend filter check)"
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

    # Net Activity Summary
    if net_col and cat_col:
        dii_net = fii_df[fii_df[cat_col].str.contains('DII', case=False, na=False)][net_col].sum()
        fii_net = fii_df[fii_df[cat_col].str.contains('FII|FPI', case=False, na=False)][net_col].sum()
        overall_net = dii_net + fii_net
        
        st.markdown("**Latest Daily Net Activity**")
        metric_cols = st.columns(3)
        
        with metric_cols[0]:
            st.metric("DII Net Value", f"₹ {dii_net:,.2f} Cr", 
                      delta="Net Buying" if dii_net > 0 else "Net Selling",
                      delta_color="normal")
        with metric_cols[1]:
            st.metric("FII/FPI Net Value", f"₹ {fii_net:,.2f} Cr", 
                      delta="Net Buying" if fii_net > 0 else "Net Selling",
                      delta_color="normal")
        with metric_cols[2]:
            st.metric("Overall Day Net", f"₹ {overall_net:,.2f} Cr", 
                      delta="Net Inflow" if overall_net > 0 else "Net Outflow",
                      delta_color="normal")

    # Flow Chart
    if date_col and net_col and cat_col:
        categories = fii_df[cat_col].dropna().unique()
        fig_flow = go.Figure()
        for cat in categories:
            cat_df = fii_df[fii_df[cat_col] == cat].dropna(subset=[date_col, net_col])
            cat_df = cat_df.sort_values(date_col)
            colors = ['#00c853' if v >= 0 else '#ff5252' for v in cat_df[net_col]]
            
            fig_flow.add_bar(
                x=cat_df[date_col], 
                y=cat_df[net_col],
                name=str(cat), 
                marker_color=colors,
                marker_line_width=1.5,
                marker_line_color='rgba(255,255,255,0.2)',
                hovertemplate="<b>%{x|%d %b %Y}</b><br>Net Value: ₹%{y:,.2f} Cr<extra></extra>"
            )
            
        fig_flow.add_hline(y=0, line_color='white', line_width=1, opacity=0.5)
        fig_flow.update_layout(
            title={'text': "FII / DII Net Flow (₹ Cr)", 'font': {'family': 'Montserrat', 'size': 18}},
            barmode='group', height=400,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white', family='Montserrat'),
            xaxis=dict(showgrid=False, title=""),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title="₹ Crores"),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_flow, use_container_width=True)

st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Stock / Index Option Chain
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("### 🎯 Stock / Index Option Chain Sentiment")

# Dynamic F&O Mapping (Ticker - Company Name)
fno_options = fetch_fno_mapping()

selected_option = st.selectbox(
    "Search by Ticker or Company Name",
    options=[""] + fno_options,
    index=0,
    placeholder="Start typing to search (e.g., NIFTY, RELIANCE, ABCAPITAL)...",
)

if selected_option:
    selected_sym = selected_option.split(" - ")[0].strip()
    
    with st.spinner(f"Fetching complete option chain for {selected_sym}..."):
        oc_df, underlying, oc_err = fetch_option_chain(selected_sym)

    if oc_err and oc_df.empty:
        st.warning(f"⚠️ {oc_err}")
        st.info("Data could not be fetched. This often happens on weekends when NSE resets the F&O data tables or blocks API access.")
    elif not oc_df.empty:
        st.markdown(f"#### **{selected_option}** — Spot Price: ₹ {underlying:,.2f}")

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
            st.metric("Put-Call Ratio (PCR)", f"{pcr:.2f}", delta=pcr_label)
        with m4:
            st.plotly_chart(gauge("Market Mood", sentiment_score), use_container_width=True)

        # OI bar chart around ATM
        oc_sorted = oc_df.sort_values('Strike').reset_index(drop=True)
        if underlying > 0:
            atm_idx = (oc_sorted['Strike'] - underlying).abs().idxmin()
            window = oc_sorted.iloc[max(0, atm_idx - 10): atm_idx + 11]
        else:
            window = oc_sorted.tail(20)

        fig_oi = go.Figure()
        fig_oi.add_bar(x=window['Strike'].astype(str), y=window['CE OI'],
                       name='Call OI (Resistance)', marker_color='rgba(255, 82, 82, 0.8)',
                       hovertemplate="Strike: %{x}<br>Call OI: %{y:,}<extra></extra>")
        fig_oi.add_bar(x=window['Strike'].astype(str), y=window['PE OI'],
                       name='Put OI (Support)', marker_color='rgba(0, 200, 83, 0.8)',
                       hovertemplate="Strike: %{x}<br>Put OI: %{y:,}<extra></extra>")
        
        if underlying > 0:
            fig_oi.add_vline(x=str(int(window.iloc[atm_idx - window.index[0]]['Strike'])), 
                             line_dash='dash', line_color='white', 
                             annotation_text='ATM ▲', annotation_position='top')
            
        fig_oi.update_layout(
            title={'text': f"Open Interest Profile (Spot: ₹{underlying:,.2f})", 'font': {'family': 'Montserrat'}},
            barmode='group', height=450,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white', family='Montserrat'),
            xaxis=dict(title='Strike Price', showgrid=False, type='category'),
            yaxis=dict(title='Open Interest (Contracts)', showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
            legend=dict(orientation='h', yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        st.plotly_chart(fig_oi, use_container_width=True)

        # Top Strikes Table (Formatted)
        st.markdown("**Top 20 Strikes by Trading Activity (Total OI)**")
        top20 = oc_df.copy()
        top20['Total OI'] = top20['CE OI'] + top20['PE OI']
        top20 = top20.sort_values('Total OI', ascending=False).head(20).reset_index(drop=True)
        
        st.dataframe(
            top20,
            column_config={
                "Strike": st.column_config.NumberColumn("Strike Price", format="₹ %,.2f"),
                "CE OI": st.column_config.NumberColumn("Call OI", format="%,.0f"),
                "PE OI": st.column_config.NumberColumn("Put OI", format="%,.0f"),
                "CE LTP": st.column_config.NumberColumn("Call LTP", format="₹ %,.2f"),
                "PE LTP": st.column_config.NumberColumn("Put LTP", format="₹ %,.2f"),
                "Total OI": st.column_config.NumberColumn("Total Open Interest", format="%,.0f"),
                "CE Chg OI": None, 
                "PE Chg OI": None
            },
            hide_index=True,
            use_container_width=True
        )

else:
    st.info("💡 Search and select a symbol above to view the option chain data.")

st.divider()
with st.expander("ℹ️ How to interpret F&O sentiment"):
    st.markdown("""
    **PCR (Put-Call Ratio) = Total PE OI ÷ Total CE OI**
    - **PCR > 1.2** → Bullish (More put writing means the market expects a strong support base).
    - **PCR < 0.8** → Bearish (More call writing means the market expects heavy resistance above).
    - **PCR 0.8–1.2** → Neutral / Sideways.

    **Open Interest (OI) Support & Resistance**
    - **Highest Call (CE) OI Strike** = Strongest Resistance (Price may struggle to break above this).
    - **Highest Put (PE) OI Strike** = Strongest Support (Price is likely to bounce from this level).
    """)
