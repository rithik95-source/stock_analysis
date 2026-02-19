import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
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
st.caption("MF scheme NAV • Stock-wise MF deals • Quarterly shareholding pattern")
st.divider()

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://www.nseindia.com/',
}
MFAPI = "https://api.mfapi.in"

# ── Fetchers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_schemes():
    try:
        r = requests.get(f"{MFAPI}/mf", timeout=20)
        if r.status_code == 200:
            data = r.json()
            df = pd.DataFrame(data)
            # Ensure consistent column names
            if 'schemeCode' not in df.columns:
                df.columns = ['schemeCode', 'schemeName']
            df['schemeCode'] = df['schemeCode'].astype(str)
            df['schemeName'] = df['schemeName'].astype(str)
            return df, None
        return pd.DataFrame(), f"API returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_nav(code):
    try:
        r = requests.get(f"{MFAPI}/mf/{code}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            nav_rows = data.get('data', [])
            meta = data.get('meta', {})
            df = pd.DataFrame(nav_rows)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'], format='%d-%m-%Y', errors='coerce')
                df['nav'] = pd.to_numeric(df['nav'], errors='coerce')
                df = df.dropna().sort_values('date').tail(180)
            return df, meta, None
        return pd.DataFrame(), {}, f"API returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), {}, str(e)

def nse_session():
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get('https://www.nseindia.com', timeout=10)
    except Exception:
        pass
    return s

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_stock_bulk_deals(symbol, days=90):
    s = nse_session()
    today = datetime.now()
    from_d = (today - timedelta(days=days)).strftime("%d-%m-%Y")
    to_d = today.strftime("%d-%m-%Y")
    url = f"https://www.nseindia.com/api/historical/bulk-deals?from={from_d}&to={to_d}&symbol={symbol.upper()}"
    try:
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            deals = r.json().get('data', [])
            if deals:
                df = pd.DataFrame(deals)
                col_map = {'symbol':'Symbol','clientName':'Entity','dealType':'Buy/Sell',
                           'quantity':'Quantity','price':'Price (₹)','tradeDate':'Date'}
                df = df.rename(columns={k:v for k,v in col_map.items() if k in df.columns})
                if 'Quantity' in df.columns:
                    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce')
                if 'Price (₹)' in df.columns:
                    df['Price (₹)'] = pd.to_numeric(df['Price (₹)'], errors='coerce')
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%d %b %Y')
                # Split MF vs all
                if 'Entity' in df.columns:
                    mf_kw = ['mutual fund','asset management','amc','sbi mf','hdfc','icici pru',
                             'nippon','axis mf','kotak','mirae','dsp','uti','franklin','invesco',
                             'tata mf','aditya birla','birla','pgim','quant','motilal','sundaram',
                             'whiteoak','parag','hsbc mf','baroda','canara robeco','edelweiss mf']
                    pat = '|'.join(mf_kw)
                    mask = df['Entity'].str.lower().str.contains(pat, na=False)
                    return df[mask].copy(), df.copy(), None
                return pd.DataFrame(), df.copy(), None
            return pd.DataFrame(), pd.DataFrame(), f"No bulk deals for {symbol} in last {days} days."
        return pd.DataFrame(), pd.DataFrame(), f"NSE returned {r.status_code}"
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), str(e)

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_shareholding(symbol):
    """Fetch shareholding pattern using NSE equity API."""
    s = nse_session()
    # Correct NSE shareholding endpoint
    url = f"https://www.nseindia.com/api/corporate-shareholding-patterns?index=equities&symbol={symbol.upper()}"
    try:
        r = s.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data, None
        # Try alternate
        url2 = f"https://www.nseindia.com/api/shareholdingPatterns?index=equities&symbol={symbol.upper()}"
        r2 = s.get(url2, timeout=15)
        if r2.status_code == 200:
            return r2.json(), None
        return None, f"NSE returned {r.status_code}"
    except Exception as e:
        return None, str(e)

def fmt_qty(x):
    try: return f"{int(x):,}"
    except: return '-'

def fmt_price(x):
    try: return f"₹{float(x):,.2f}"
    except: return '-'

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📈 MF Scheme NAV", "🔍 Stock-wise MF Deals", "📋 Shareholding Pattern"])

# ══ TAB 1: MF Scheme NAV ══════════════════════════════════════════════════════
with tab1:
    st.markdown("#### Search a Mutual Fund Scheme")
    st.caption("Live NAV from AMFI via mfapi.in — updates daily after 9 PM IST")

    with st.spinner("Loading all MF schemes..."):
        schemes_df, schemes_err = fetch_all_schemes()

    if schemes_err and schemes_df.empty:
        st.warning(f"⚠️ {schemes_err}")
    else:
        # Single search → filtered dropdown (same pattern as Stock Recommendations)
        mf_search = st.text_input(
            "Search scheme",
            placeholder="Type fund house or scheme name (e.g. SBI Bluechip, Nippon Small Cap)",
            label_visibility="collapsed",
            key="mf_nav_search",
        )

        q = mf_search.strip().lower()
        if q and not schemes_df.empty:
            filtered = schemes_df[schemes_df['schemeName'].str.lower().str.contains(q, na=False)]
            if filtered.empty:
                st.info("No schemes matched. Try shorter keywords (e.g. 'SBI' or 'Bluechip').")
            else:
                options = [""] + [
                    f"{row['schemeCode']} — {row['schemeName']}"
                    for _, row in filtered.head(80).iterrows()
                ]
                sel = st.selectbox(
                    "Select scheme",
                    options=options,
                    index=0,
                    label_visibility="collapsed",
                    key="mf_nav_sel",
                )
                if sel:
                    code = sel.split("—")[0].strip()
                    with st.spinner("Fetching NAV data..."):
                        nav_df, meta, nav_err = fetch_nav(code)
                    if nav_err and nav_df.empty:
                        st.warning(f"⚠️ {nav_err}")
                    else:
                        scheme_name = meta.get('scheme_name', sel.split('—')[-1].strip())
                        st.markdown(f"**{scheme_name}**")
                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            st.metric("Fund House", meta.get('fund_house', '—'))
                        with m2:
                            st.metric("Category", meta.get('scheme_category', '—'))
                        with m3:
                            if not nav_df.empty:
                                st.metric("Latest NAV", f"₹{nav_df.iloc[-1]['nav']:,.4f}")
                        with m4:
                            if len(nav_df) >= 2:
                                chg = nav_df.iloc[-1]['nav'] - nav_df.iloc[-2]['nav']
                                pct = chg / nav_df.iloc[-2]['nav'] * 100
                                st.metric("1-Day Δ", f"{pct:+.2f}%")

                        if not nav_df.empty:
                            period = st.selectbox("Period", ["1 Month","3 Months","6 Months","1 Year"],
                                                  index=1, key="nav_period")
                            days_map = {"1 Month":30,"3 Months":90,"6 Months":180,"1 Year":365}
                            plot_df = nav_df.tail(days_map[period])
                            fig = go.Figure()
                            fig.add_scatter(
                                x=plot_df['date'], y=plot_df['nav'],
                                mode='lines', line=dict(color='#00b4d8', width=2),
                                fill='tozeroy', fillcolor='rgba(0,180,216,0.08)',
                            )
                            fig.update_layout(
                                title=f"NAV — {period}",
                                height=340,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font_color='white',
                                xaxis_title='', yaxis_title='NAV (₹)',
                                margin=dict(l=0,r=0,t=40,b=0),
                            )
                            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("💡 Type a fund name above to search — e.g. 'SBI', 'HDFC', 'Nippon Small Cap'")

# ══ TAB 2: Stock-wise MF Deals ════════════════════════════════════════════════
with tab2:
    st.markdown("#### MF Bulk Deals for a Stock (Last 90 Days)")
    st.caption("Mutual fund buy/sell bulk deals from NSE — same search style as other pages")

    mf_stock_search = st.text_input(
        "Search stock",
        placeholder="Type NSE symbol (e.g. RELIANCE, ZOMATO, TCS)",
        label_visibility="collapsed",
        key="mf_stock_search",
    )

    common_stocks = ['RELIANCE','TCS','INFY','HDFCBANK','ICICIBANK','SBIN','BHARTIARTL',
                     'ITC','WIPRO','AXISBANK','KOTAKBANK','ZOMATO','ADANIENT','TATAMOTORS',
                     'SUNPHARMA','LT','MARUTI','TITAN','BAJFINANCE','NESTLEIND']

    sq = mf_stock_search.strip().upper()
    filtered_stocks = [s for s in common_stocks if sq in s] if sq else common_stocks

    mf_sel_stock = st.selectbox(
        "Select stock",
        options=[""] + filtered_stocks,
        index=0,
        label_visibility="collapsed",
        key="mf_stock_sel",
    )

    if mf_sel_stock:
        with st.spinner(f"Fetching MF deals for {mf_sel_stock}..."):
            mf_df, all_df, deal_err = fetch_stock_bulk_deals(mf_sel_stock)

        if deal_err and mf_df.empty and all_df.empty:
            st.warning(f"⚠️ {deal_err}")
        else:
            st.markdown(f"##### 🏦 Mutual Fund Deals — {mf_sel_stock}")
            if not mf_df.empty:
                show = mf_df.copy()
                if 'Quantity' in show.columns:
                    show['Quantity'] = show['Quantity'].apply(fmt_qty)
                if 'Price (₹)' in show.columns:
                    show['Price (₹)'] = show['Price (₹)'].apply(fmt_price)
                st.dataframe(show.reset_index(drop=True), use_container_width=True)
            else:
                st.info(f"No mutual fund bulk deals found for **{mf_sel_stock}** in the last 90 days.")

            if not all_df.empty:
                with st.expander(f"📦 All Bulk Deals for {mf_sel_stock} (90 days)"):
                    show2 = all_df.copy()
                    if 'Quantity' in show2.columns:
                        show2['Quantity'] = show2['Quantity'].apply(fmt_qty)
                    if 'Price (₹)' in show2.columns:
                        show2['Price (₹)'] = show2['Price (₹)'].apply(fmt_price)
                    st.dataframe(show2.head(20).reset_index(drop=True), use_container_width=True)
    else:
        st.info("💡 Type or select a stock above to see MF bulk deal activity")

# ══ TAB 3: Shareholding Pattern ═══════════════════════════════════════════════
with tab3:
    st.markdown("#### Quarterly Shareholding Pattern")
    st.caption("Promoter / FII / DII / Public — disclosed quarterly, 3-month lag")

    sh_search = st.text_input(
        "Search stock",
        placeholder="Type NSE symbol (e.g. RELIANCE, INFY, HDFCBANK)",
        label_visibility="collapsed",
        key="sh_search",
    )

    sh_stocks = ['RELIANCE','TCS','INFY','HDFCBANK','ICICIBANK','SBIN','BHARTIARTL',
                 'ITC','WIPRO','AXISBANK','KOTAKBANK','ZOMATO','ADANIENT','TATAMOTORS',
                 'SUNPHARMA','LT','MARUTI','TITAN','BAJFINANCE','NESTLEIND','DRREDDY',
                 'COALINDIA','NTPC','POWERGRID','ONGC','BPCL','GRASIM','ULTRACEMCO']

    shq = sh_search.strip().upper()
    filtered_sh = [s for s in sh_stocks if shq in s] if shq else sh_stocks

    sh_sel = st.selectbox(
        "Select stock",
        options=[""] + filtered_sh,
        index=0,
        label_visibility="collapsed",
        key="sh_sel",
    )

    if sh_sel:
        with st.spinner(f"Fetching shareholding for {sh_sel}..."):
            sh_data, sh_err = fetch_shareholding(sh_sel)

        if sh_err and not sh_data:
            st.warning(f"⚠️ {sh_err}")
            st.info("NSE's shareholding endpoint may be restricted. The quarterly data is available on NSE website → Company Info → Shareholding Pattern.")
        elif sh_data:
            try:
                if isinstance(sh_data, list):
                    df_sh = pd.DataFrame(sh_data)
                elif isinstance(sh_data, dict):
                    for k in ['data', 'shareholding', 'results', 'records', 'body']:
                        if k in sh_data and sh_data[k]:
                            df_sh = pd.DataFrame(sh_data[k])
                            break
                    else:
                        df_sh = pd.DataFrame([sh_data])

                if not df_sh.empty:
                    st.dataframe(df_sh.head(30), use_container_width=True)

                    # Pie chart if we can find % columns
                    pct_cols = [c for c in df_sh.columns
                                if any(x in c.lower() for x in ['promoter','fii','dii','public','institution','foreign'])]
                    if pct_cols and len(df_sh) > 0:
                        latest = df_sh.iloc[0]
                        vals = []
                        labels = []
                        for c in pct_cols:
                            v = pd.to_numeric(latest.get(c, 0), errors='coerce')
                            if pd.notna(v) and v > 0:
                                vals.append(v)
                                labels.append(c)
                        if vals:
                            fig_pie = go.Figure(go.Pie(
                                labels=labels, values=vals,
                                hole=0.4, textinfo='label+percent',
                            ))
                            fig_pie.update_layout(
                                title=f"{sh_sel} — Shareholding Mix (Latest Quarter)",
                                height=380,
                                paper_bgcolor='rgba(0,0,0,0)',
                                font_color='white',
                            )
                            st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("Data returned but could not be parsed into a table.")
            except Exception as e:
                st.warning(f"Parse error: {e}")
        else:
            st.info("No shareholding data returned.")
    else:
        st.info("💡 Type or select a stock above to see its shareholding pattern")

st.divider()
with st.expander("ℹ️ About data sources & lag"):
    st.markdown("""
**MF Scheme NAV** — AMFI publishes NAV daily after 9 PM IST. Fetched via mfapi.in (free, no auth needed).

**MF Bulk Deals** — NSE mandates disclosure when a fund buys/sells >0.5% of a company's equity.
Same-day reporting. The page shows deals from the last 90 days and highlights MF names.

**Shareholding Pattern** — SEBI requires quarterly disclosure within 21 days of quarter-end.
Reflects holdings as of March/June/September/December. Use this for long-term FII/DII trend tracking.

**Pro Tip:** Rising MF holding quarter-on-quarter + recent MF bulk buy deal = high conviction institutional accumulation.
    """)

st.caption("📊 Sources: AMFI (mfapi.in), NSE India  •  NAV daily, deals 30 min cache")
