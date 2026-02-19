import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Mutual Fund Activity", layout="wide", page_icon="🏦")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    h1, h2, h3, h4, h5, h6 { font-family: 'Montserrat', sans-serif; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("🏦 Mutual Fund Activity")
st.caption("Monthly MF portfolio disclosures — ~10 day lag (released by 10th of following month)")
st.divider()

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/',
}
MFAPI_BASE = "https://api.mfapi.in"

# ── Data fetchers ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_mf_schemes():
    """Fetch all MF scheme list from mfapi.in (free public API)."""
    try:
        r = requests.get(f"{MFAPI_BASE}/mf", timeout=15)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data)
            return df, None
        return pd.DataFrame(), f"API returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=3600)
def fetch_scheme_nav_history(scheme_code, days=90):
    """Fetch NAV history for a scheme."""
    try:
        r = requests.get(f"{MFAPI_BASE}/mf/{scheme_code}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            nav_data = data.get('data', [])
            meta = data.get('meta', {})
            df = pd.DataFrame(nav_data)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y')
                df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
                df = df.sort_values('date').tail(days)
            return df, meta, None
        return pd.DataFrame(), {}, f"API returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), {}, str(e)

@st.cache_data(ttl=1800)
def fetch_nse_mf_bulk_deals_for_stock(symbol):
    """Get MF-related bulk/block deals for a specific stock from NSE."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass

    today = datetime.now()
    from_d = (today - timedelta(days=90)).strftime("%d-%m-%Y")
    to_d = today.strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/historical/bulk-deals?from={from_d}&to={to_d}&symbol={symbol.upper()}"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            deals = data.get('data', [])
            if deals:
                df = pd.DataFrame(deals)
                # Filter for MF/institutional clients
                if 'clientName' in df.columns:
                    mf_keywords = ['mutual fund', 'mf', 'asset management', 'amc', 'trustee',
                                   'sbi mf', 'hdfc mf', 'icici pru', 'nippon', 'axis mf',
                                   'kotak mf', 'mirae', 'dsp', 'uti', 'franklin', 'invesco',
                                   'tata mf', 'aditya birla', 'birla sun life', 'pgim', 'quant']
                    pattern = '|'.join(mf_keywords)
                    mf_mask = df['clientName'].str.lower().str.contains(pattern, na=False)
                    df_mf = df[mf_mask].copy()
                    df_all = df.copy()
                    return df_mf, df_all, None
                return pd.DataFrame(), df, None
            return pd.DataFrame(), pd.DataFrame(), "No bulk deals found for this stock in last 90 days."
        return pd.DataFrame(), pd.DataFrame(), f"NSE returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

@st.cache_data(ttl=1800)
def fetch_shareholding_pattern(symbol):
    """Fetch latest shareholding pattern from NSE."""
    session = requests.Session()
    try:
        session.get('https://www.nseindia.com', headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass
    url = f"https://www.nseindia.com/api/shareholding-patterns?symbol={symbol.upper()}&dataType=Shareholding+Pattern&index=equities"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data, None
        return None, f"NSE returned {r.status_code}"
    except Exception as e:
        return None, str(e)

def format_inr(val):
    try:
        v = float(val)
        return f"₹{v:,.2f}"
    except Exception:
        return str(val)

# ── Tab layout ─────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 MF Scheme NAV & Info", "🔍 Stock-wise MF Activity", "📋 Shareholding Pattern"])

# ══ Tab 1: MF Scheme NAV ══════════════════════════════════════════════════════
with tab1:
    st.markdown("### Search Mutual Fund Scheme")
    st.caption("Live NAV data from AMFI via mfapi.in — updates daily after 9 PM")

    with st.spinner("Loading scheme list..."):
        schemes_df, schemes_err = fetch_mf_schemes()

    if schemes_err and schemes_df.empty:
        st.warning(f"⚠️ {schemes_err}")
    else:
        scheme_search = st.text_input(
            "Search scheme",
            placeholder="Type fund name (e.g. SBI Bluechip, HDFC Midcap, Mirae Large Cap)",
            label_visibility="collapsed",
            key="mf_scheme_search",
        )

        if scheme_search.strip() and not schemes_df.empty:
            q = scheme_search.strip().lower()
            name_col = 'schemeName' if 'schemeName' in schemes_df.columns else schemes_df.columns[1]
            code_col = 'schemeCode' if 'schemeCode' in schemes_df.columns else schemes_df.columns[0]

            filtered = schemes_df[schemes_df[name_col].str.lower().str.contains(q, na=False)]

            if filtered.empty:
                st.info("No schemes matched. Try shorter keywords.")
            else:
                options = [""] + [f"{row[code_col]} — {row[name_col]}" for _, row in filtered.head(50).iterrows()]
                sel_scheme = st.selectbox("Select scheme", options, label_visibility="collapsed", key="mf_scheme_sel")

                if sel_scheme:
                    code = int(sel_scheme.split("—")[0].strip())
                    with st.spinner("Fetching NAV history..."):
                        nav_df, meta, nav_err = fetch_scheme_nav_history(code)

                    if nav_err and nav_df.empty:
                        st.warning(f"⚠️ {nav_err}")
                    else:
                        st.markdown(f"**{meta.get('scheme_name', sel_scheme)}**")
                        mc1, mc2, mc3, mc4 = st.columns(4)
                        with mc1:
                            st.metric("Fund House", meta.get('fund_house', '-'))
                        with mc2:
                            st.metric("Category", meta.get('scheme_category', '-'))
                        with mc3:
                            if not nav_df.empty:
                                latest_nav = nav_df.iloc[-1]['nav']
                                st.metric("Latest NAV", f"₹{latest_nav:,.4f}")
                        with mc4:
                            if len(nav_df) >= 2:
                                change = nav_df.iloc[-1]['nav'] - nav_df.iloc[-2]['nav']
                                pct = (change / nav_df.iloc[-2]['nav']) * 100
                                st.metric("1-Day Change", f"{pct:+.2f}%")

                        if not nav_df.empty:
                            import plotly.graph_objects as go
                            fig = go.Figure()
                            fig.add_scatter(
                                x=nav_df['date'], y=nav_df['nav'],
                                mode='lines', line=dict(color='#00b4d8', width=2),
                                fill='tozeroy', fillcolor='rgba(0,180,216,0.1)',
                                name='NAV'
                            )
                            fig.update_layout(
                                title="NAV History (Last 90 Days)",
                                height=350, paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)', font_color='white',
                                xaxis_title='Date', yaxis_title='NAV (₹)',
                            )
                            st.plotly_chart(fig, use_container_width=True)
        else:
            if not scheme_search.strip():
                st.info("💡 Type a fund name above to search (e.g. SBI Bluechip, Nippon Small Cap)")

# ══ Tab 2: Stock-wise MF Deals ════════════════════════════════════════════════
with tab2:
    st.markdown("### MF Bulk Deals for a Stock (Last 90 Days)")
    st.caption("Mutual fund buy/sell bulk deals reported to NSE in the last 90 days")

    stock_input = st.text_input(
        "Enter NSE symbol",
        placeholder="e.g. RELIANCE, TCS, ZOMATO",
        label_visibility="collapsed",
        key="mf_stock_input",
    )

    if stock_input.strip():
        sym = stock_input.strip().upper()
        with st.spinner(f"Fetching MF deals for {sym}..."):
            mf_deals_df, all_deals_df, deal_err = fetch_nse_mf_bulk_deals_for_stock(sym)

        if deal_err and mf_deals_df.empty and all_deals_df.empty:
            st.warning(f"⚠️ {deal_err}")
        else:
            # MF-specific deals
            st.markdown(f"#### 🏦 Mutual Fund Deals in **{sym}**")
            if not mf_deals_df.empty:
                rename = {
                    'symbol': 'Symbol', 'clientName': 'MF / Scheme',
                    'dealType': 'Deal Type', 'quantity': 'Quantity',
                    'price': 'Price (₹)', 'tradeDate': 'Date',
                }
                mf_show = mf_deals_df.rename(columns={k: v for k, v in rename.items() if k in mf_deals_df.columns})
                if 'Quantity' in mf_show.columns:
                    mf_show['Quantity'] = pd.to_numeric(mf_show['Quantity'], errors='coerce').apply(
                        lambda x: f"{int(x):,}" if pd.notna(x) else '-')
                if 'Price (₹)' in mf_show.columns:
                    mf_show['Price (₹)'] = pd.to_numeric(mf_show['Price (₹)'], errors='coerce').apply(
                        lambda x: f"₹{x:,.2f}" if pd.notna(x) else '-')
                st.dataframe(mf_show.head(20).reset_index(drop=True), use_container_width=True)
            else:
                st.info(f"No mutual fund bulk deals found for **{sym}** in the last 90 days.")

            # All institutional deals
            if not all_deals_df.empty:
                with st.expander(f"📦 All Bulk Deals for {sym} (last 90 days)"):
                    rename_all = {
                        'symbol': 'Symbol', 'clientName': 'Entity',
                        'dealType': 'Deal Type', 'quantity': 'Quantity',
                        'price': 'Price (₹)', 'tradeDate': 'Date',
                    }
                    all_show = all_deals_df.rename(columns={k: v for k, v in rename_all.items() if k in all_deals_df.columns})
                    if 'Quantity' in all_show.columns:
                        all_show['Quantity'] = pd.to_numeric(all_show['Quantity'], errors='coerce').apply(
                            lambda x: f"{int(x):,}" if pd.notna(x) else '-')
                    if 'Price (₹)' in all_show.columns:
                        all_show['Price (₹)'] = pd.to_numeric(all_show['Price (₹)'], errors='coerce').apply(
                            lambda x: f"₹{x:,.2f}" if pd.notna(x) else '-')
                    st.dataframe(all_show.head(20).reset_index(drop=True), use_container_width=True)
    else:
        st.info("💡 Enter an NSE stock symbol above to see MF activity")

# ══ Tab 3: Shareholding Pattern ═══════════════════════════════════════════════
with tab3:
    st.markdown("### Quarterly Shareholding Pattern")
    st.caption("FII / DII / Promoter / Public holdings — updated quarterly (3-month lag)")

    sh_stock = st.text_input(
        "Enter NSE symbol",
        placeholder="e.g. RELIANCE, INFY, HDFCBANK",
        label_visibility="collapsed",
        key="sh_stock_input",
    )

    if sh_stock.strip():
        sym2 = sh_stock.strip().upper()
        with st.spinner(f"Fetching shareholding pattern for {sym2}..."):
            sh_data, sh_err = fetch_shareholding_pattern(sym2)

        if sh_err and not sh_data:
            st.warning(f"⚠️ {sh_err}")
        elif sh_data:
            # NSE returns varying structures — try to parse generically
            try:
                if isinstance(sh_data, list):
                    df_sh = pd.DataFrame(sh_data)
                elif isinstance(sh_data, dict):
                    # Find the most relevant key
                    for k in ['data', 'shareholding', 'results', 'records']:
                        if k in sh_data:
                            df_sh = pd.DataFrame(sh_data[k])
                            break
                    else:
                        df_sh = pd.DataFrame([sh_data])

                if not df_sh.empty:
                    st.dataframe(df_sh.head(30), use_container_width=True)

                    # Try to plot if we have standard columns
                    category_cols = [c for c in df_sh.columns if any(x in c.lower() for x in ['promoter', 'fii', 'dii', 'public', 'institution'])]
                    if category_cols:
                        import plotly.graph_objects as go
                        latest = df_sh.iloc[0]
                        vals = [pd.to_numeric(latest.get(c, 0), errors='coerce') for c in category_cols]
                        fig_pie = go.Figure(go.Pie(
                            labels=category_cols, values=vals,
                            hole=0.4, textinfo='label+percent',
                        ))
                        fig_pie.update_layout(
                            title=f"{sym2} — Shareholding Distribution",
                            height=380, paper_bgcolor='rgba(0,0,0,0)', font_color='white',
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No shareholding data in expected format.")
            except Exception as e:
                st.warning(f"Could not parse shareholding data: {e}")
                st.json(sh_data)
        else:
            st.info("No shareholding data available.")
    else:
        st.info("💡 Enter an NSE stock symbol above to see shareholding pattern")

st.divider()
with st.expander("ℹ️ About MF data sources"):
    st.markdown("""
**Scheme NAV** — Live daily NAV data from AMFI (Association of Mutual Funds in India) via the free mfapi.in API. Updates daily after 9 PM IST.

**MF Bulk Deals** — When a mutual fund buys/sells > 0.5% of a company's equity, it shows up here via NSE's bulk deal reporting system. Lag: same day.

**Shareholding Pattern** — Quarterly disclosure (March, June, September, December quarters). Released within 21 days of quarter end. Best for tracking long-term promoter/FII/DII trends.

**Pro Tip:** Combine rising MF holding (shareholding pattern) + recent MF bulk deals (buying) for strong conviction signals.
    """)

st.caption("📊 Sources: mfapi.in (AMFI), NSE India  •  NAV refreshed daily, deals every 30 min")
