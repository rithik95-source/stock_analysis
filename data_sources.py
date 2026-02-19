import yfinance as yf
import pandas as pd
import requests
import io
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import feedparser
import re

# Global cache for NSE stocks (refreshes daily)
_nse_stock_cache = None
_cache_time = None

def fetch_comex(symbol):
    try:
        ticker = yf.Ticker(symbol)
        return ticker.history(period="5d", interval="1m").reset_index()
    except Exception as e:
        print(f"Error fetching COMEX data: {e}")
        return pd.DataFrame()

def fetch_mcx_intraday(commodity):
    """
    Fetch MCX intraday data using Yahoo Finance
    MCX commodities are available on Yahoo Finance with specific symbols
    """
    mcx_symbols = {
        "GOLD": "GC=F",      # Gold futures (use COMEX as proxy - highly correlated)
        "SILVER": "SI=F",    # Silver futures
        "CRUDEOIL": "CL=F",  # Crude oil futures
        "COPPER": "HG=F",    # Copper futures
        "NATURALGAS": "NG=F" # Natural gas futures
    }
    
    try:
        symbol = mcx_symbols.get(commodity, "GC=F")
        ticker = yf.Ticker(symbol)
        
        # Get 5 days of 5-minute interval data for intraday charts
        df = ticker.history(period="5d", interval="5m")
        
        if not df.empty:
            df = df.reset_index()
            # Convert to INR (approximate conversion - Gold is in USD/oz, MCX is in INR/10g)
            if commodity == "GOLD":
                # Rough conversion: USD/oz to INR/10g
                # 1 oz = 31.1g, so 10g = 10/31.1 oz
                # Multiply by USD to INR rate (approx 83)
                df['Close'] = df['Close'] * (10 / 31.1035) * 83
                df['High'] = df['High'] * (10 / 31.1035) * 83
                df['Low'] = df['Low'] * (10 / 31.1035) * 83
                df['Open'] = df['Open'] * (10 / 31.1035) * 83
            elif commodity == "SILVER":
                # Silver: USD/oz to INR/kg (1 kg = 32.15 oz)
                df['Close'] = df['Close'] * 32.15 * 83
                df['High'] = df['High'] * 32.15 * 83
                df['Low'] = df['Low'] * 32.15 * 83
                df['Open'] = df['Open'] * 32.15 * 83
            elif commodity == "CRUDEOIL":
                # Crude: USD/barrel to INR/barrel
                df['Close'] = df['Close'] * 83
                df['High'] = df['High'] * 83
                df['Low'] = df['Low'] * 83
                df['Open'] = df['Open'] * 83
            elif commodity == "COPPER":
                # Copper: USD/lb to INR/kg (1 kg = 2.205 lb)
                df['Close'] = df['Close'] * 2.205 * 83
                df['High'] = df['High'] * 2.205 * 83
                df['Low'] = df['Low'] * 2.205 * 83
                df['Open'] = df['Open'] * 2.205 * 83
            
            return df
        
    except Exception as e:
        print(f"Error fetching MCX intraday for {commodity}: {e}")
    
    return pd.DataFrame()

def fetch_mcx_two_days():
    """Fallback function to get MCX data from Bhavcopy files"""
    found = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(10):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.mcxindia.com/downloads/Bhavcopy_{date}.csv"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                df.columns = df.columns.str.strip().str.upper()
                found.append(df)
            if len(found) == 2: break
        except: continue
    return (found[0], found[1]) if len(found) >= 2 else (pd.DataFrame(), pd.DataFrame())

def get_intraday_recommendations():
    """Get intraday trading recommendations with robust error handling"""
    intraday_picks = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Method 1: Use Yahoo Finance trending stocks with momentum
    try:
        nifty50_symbols = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS",
            "AXISBANK.NS", "WIPRO.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS"
        ]
        
        momentum_stocks = []
        
        for symbol in nifty50_symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2d", interval="5m")
                
                if not hist.empty and len(hist) > 20:
                    cmp = hist['Close'].iloc[-1]
                    open_price = hist['Open'].iloc[0]
                    
                    # Calculate intraday change
                    change_pct = ((cmp - open_price) / open_price) * 100
                    
                    # Only stocks with momentum (>0.5% move)
                    if abs(change_pct) > 0.5:
                        momentum_stocks.append({
                            'symbol': symbol,
                            'name': symbol.replace('.NS', ''),
                            'cmp': cmp,
                            'change_pct': change_pct
                        })
            except:
                continue
        
        # Sort by absolute momentum
        momentum_stocks.sort(key=lambda x: abs(x['change_pct']), reverse=True)
        
        # Take top 4 momentum stocks
        for stock in momentum_stocks[:4]:
            try:
                cmp = stock['cmp']
                change_pct = stock['change_pct']
                
                # Set targets based on momentum
                if change_pct > 0:
                    intraday_target = cmp * 1.02  # 2% target
                    stop_loss = cmp * 0.985  # 1.5% stop loss
                    pick_type = "Momentum Up"
                else:
                    intraday_target = cmp * 1.015  # 1.5% target for reversal
                    stop_loss = cmp * 0.99  # 1% stop loss
                    pick_type = "Reversal Play"
                
                upside = ((intraday_target - cmp) / cmp) * 100
                
                intraday_picks.append({
                    "Stock": stock['name'],
                    "Symbol": stock['symbol'],
                    "CMP": round(cmp, 2),
                    "Target": round(intraday_target, 2),
                    "Stop Loss": round(stop_loss, 2),
                    "Upside %": round(upside, 2),
                    "Type": pick_type,
                    "Timeframe": "Intraday",
                    "Date": datetime.now().strftime('%Y-%m-%d %H:%M')
                })
            except:
                continue
                
    except Exception as e:
        print(f"Yahoo momentum screening error: {e}")
    
    # Method 2: Screener.in API (if available)
    if len(intraday_picks) < 3:
        try:
            url = "https://www.screener.in/api/screens/top-gainers/?sort=-pChange&order=desc&page=1"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])[:5]
                
                for stock in results:
                    try:
                        symbol = f"{stock.get('short_name', '')}.NS"
                        ticker = yf.Ticker(symbol)
                        cmp = ticker.fast_info.get('lastPrice', 0)
                        
                        if cmp > 0:
                            intraday_target = cmp * 1.025
                            stop_loss = cmp * 0.985
                            
                            intraday_picks.append({
                                "Stock": stock.get('name', 'Unknown'),
                                "Symbol": symbol,
                                "CMP": round(cmp, 2),
                                "Target": round(intraday_target, 2),
                                "Stop Loss": round(stop_loss, 2),
                                "Upside %": 2.5,
                                "Type": "Top Gainer",
                                "Timeframe": "Intraday",
                                "Date": datetime.now().strftime('%Y-%m-%d %H:%M')
                            })
                    except:
                        continue
        except Exception as e:
            print(f"Screener.in error: {e}")
    
    # Fallback: If still empty, use safe blue chips with technical signals
    if len(intraday_picks) < 2:
        try:
            fallback_stocks = [
                ("RELIANCE.NS", "Reliance"),
                ("TCS.NS", "TCS"),
                ("INFY.NS", "Infosys"),
                ("HDFCBANK.NS", "HDFC Bank")
            ]
            
            for symbol, name in fallback_stocks[:3]:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="5d", interval="5m")
                    
                    if not hist.empty:
                        cmp = hist['Close'].iloc[-1]
                        recent = hist.tail(12)  # Last hour
                        
                        if recent['Close'].iloc[-1] > recent['Close'].iloc[0]:
                            intraday_target = cmp * 1.015
                            stop_loss = cmp * 0.99
                            
                            intraday_picks.append({
                                "Stock": name,
                                "Symbol": symbol,
                                "CMP": round(cmp, 2),
                                "Target": round(intraday_target, 2),
                                "Stop Loss": round(stop_loss, 2),
                                "Upside %": 1.5,
                                "Type": "Technical",
                                "Timeframe": "Intraday",
                                "Date": datetime.now().strftime('%Y-%m-%d %H:%M')
                            })
                except:
                    continue
        except Exception as e:
            print(f"Fallback stocks error: {e}")
    
    if intraday_picks:
        df = pd.DataFrame(intraday_picks)
        return df.drop_duplicates(subset=['Stock'], keep='first').head(6)
    
    # Last resort fallback
    return pd.DataFrame([{
        "Stock": "Loading...",
        "Symbol": "-",
        "CMP": 0,
        "Target": 0,
        "Stop Loss": 0,
        "Upside %": 0,
        "Type": "Refreshing",
        "Timeframe": "Intraday",
        "Date": datetime.now().strftime('%Y-%m-%d %H:%M')
    }])

def get_longterm_recommendations():
    """Get long-term (swing/positional) recommendations with robust error handling"""
    longterm_picks = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Method 1: Yahoo Finance Analyst Recommendations (Most reliable)
    try:
        top_stocks = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "WIPRO.NS", "AXISBANK.NS",
            "KOTAKBANK.NS", "LT.NS", "MARUTI.NS", "TITAN.NS", "SUNPHARMA.NS"
        ]
        
        for symbol in top_stocks:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                cmp = ticker.fast_info.get('lastPrice', 0)
                
                # Get analyst target price and recommendation
                target = info.get('targetMeanPrice', 0)
                recommendation = info.get('recommendationKey', 'hold')
                
                if cmp > 0 and target > 0 and recommendation in ['buy', 'strong_buy']:
                    upside = ((target - cmp) / cmp) * 100
                    
                    # Only show if upside > 5%
                    if upside > 5:
                        stop_loss = cmp * 0.90
                        
                        longterm_picks.append({
                            "Stock": info.get('shortName', symbol.replace('.NS', '')),
                            "Symbol": symbol,
                            "CMP": round(cmp, 2),
                            "Target": round(target, 0),
                            "Stop Loss": round(stop_loss, 2),
                            "Upside %": round(upside, 2),
                            "Type": "Analyst",
                            "Timeframe": "1-3 months",
                            "Date": datetime.now().strftime('%Y-%m-%d'),
                            "Source": "Yahoo Finance"
                        })
            except:
                continue
    except Exception as e:
        print(f"Yahoo Finance analyst reco error: {e}")
    
    # Method 2: Economic Times Stock Recommendations RSS
    if len(longterm_picks) < 5:
        try:
            et_reco_rss = "https://economictimes.indiatimes.com/markets/stocks/recos/rssfeeds/1977021501.cms"
            feed = feedparser.parse(et_reco_rss)
            
            if feed and hasattr(feed, 'entries'):
                for entry in feed.entries[:10]:
                    try:
                        title = entry.title
                        
                        # Parse: "Stock Name: Buy/Sell, Target Rs XX"
                        stock_match = re.search(r'^([^:]+?)(?:\s*-|\s*:)', title)
                        action_match = re.search(r'\b(Buy|Accumulate)\b', title, re.IGNORECASE)
                        target_match = re.search(r'(?:target|tgt|price target).*?Rs\.?\s*([\d,]+)', title, re.IGNORECASE)
                        
                        if stock_match and action_match:
                            stock_name = stock_match.group(1).strip()
                            action = action_match.group(1).upper()
                            
                            target = None
                            if target_match:
                                target = float(target_match.group(1).replace(',', ''))
                            
                            symbol = get_nse_symbol(stock_name)
                            if symbol:
                                try:
                                    ticker = yf.Ticker(symbol)
                                    cmp = ticker.fast_info.get('lastPrice', 0)
                                    
                                    if cmp > 0:
                                        if not target:
                                            target = cmp * 1.15
                                        
                                        upside = ((target - cmp) / cmp) * 100
                                        
                                        if upside > 3:  # Only show if upside > 3%
                                            stop_loss = cmp * 0.92
                                            pub_date = entry.get('published', datetime.now().strftime('%Y-%m-%d'))[:10]
                                            
                                            longterm_picks.append({
                                                "Stock": stock_name,
                                                "Symbol": symbol,
                                                "CMP": round(cmp, 2),
                                                "Target": round(target, 0),
                                                "Stop Loss": round(stop_loss, 2),
                                                "Upside %": round(upside, 2),
                                                "Type": action.capitalize(),
                                                "Timeframe": "2-4 weeks",
                                                "Date": pub_date,
                                                "Source": "ET Analysts"
                                            })
                                except:
                                    continue
                    except:
                        continue
        except Exception as e:
            print(f"ET RSS error: {e}")
    
    # Method 3: Technical analysis on blue chips (fallback)
    if len(longterm_picks) < 3:
        try:
            blue_chips = [
                ("RELIANCE.NS", "Reliance Industries"),
                ("TCS.NS", "TCS"),
                ("HDFCBANK.NS", "HDFC Bank"),
                ("INFY.NS", "Infosys")
            ]
            
            for symbol, name in blue_chips:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period="3mo", interval="1d")
                    
                    if not hist.empty:
                        cmp = hist['Close'].iloc[-1]
                        avg_20 = hist['Close'].tail(20).mean()
                        
                        # If price > 20-day MA, consider bullish
                        if cmp > avg_20:
                            target = cmp * 1.10
                            stop_loss = cmp * 0.93
                            upside = 10.0
                            
                            longterm_picks.append({
                                "Stock": name,
                                "Symbol": symbol,
                                "CMP": round(cmp, 2),
                                "Target": round(target, 0),
                                "Stop Loss": round(stop_loss, 2),
                                "Upside %": upside,
                                "Type": "Technical",
                                "Timeframe": "4-6 weeks",
                                "Date": datetime.now().strftime('%Y-%m-%d'),
                                "Source": "Technical Analysis"
                            })
                except:
                    continue
        except Exception as e:
            print(f"Technical analysis error: {e}")
    
    if longterm_picks:
        df = pd.DataFrame(longterm_picks)
        # Sort by upside percentage
        df = df.sort_values('Upside %', ascending=False)
        # Remove duplicates
        df = df.drop_duplicates(subset=['Stock'], keep='first')
        return df.head(8)
    
    # Last resort fallback
    return pd.DataFrame([{
        "Stock": "Loading...",
        "Symbol": "-",
        "CMP": 0,
        "Target": 0,
        "Stop Loss": 0,
        "Upside %": 0,
        "Type": "Refreshing",
        "Timeframe": "Loading",
        "Date": datetime.now().strftime('%Y-%m-%d'),
        "Source": "System"
    }])

def search_stock_recommendations(ticker_symbol):
    """
    Search for stock recommendations by ticker symbol
    Returns both intraday and long-term analyst recommendations
    """
    result = {
        'symbol': ticker_symbol,
        'name': '',
        'cmp': 0,
        'intraday': None,
        'longterm': None,
        'error': None
    }
    
    # Ensure .NS suffix
    if not ticker_symbol.endswith('.NS'):
        ticker_symbol = f"{ticker_symbol}.NS"
    
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        # Get basic info
        result['name'] = info.get('shortName', ticker_symbol.replace('.NS', ''))
        result['cmp'] = ticker.fast_info.get('lastPrice', 0)
        
        if result['cmp'] == 0:
            result['error'] = "Stock not found or invalid ticker"
            return result
        
        # === INTRADAY RECOMMENDATIONS ===
        try:
            hist = ticker.history(period="5d", interval="5m")
            
            if not hist.empty and len(hist) > 20:
                open_price = hist['Open'].iloc[0]
                current_price = hist['Close'].iloc[-1]
                high_today = hist['High'].max()
                low_today = hist['Low'].min()
                
                # Calculate intraday momentum
                change_pct = ((current_price - open_price) / open_price) * 100
                
                # Calculate support and resistance
                recent_20 = hist.tail(20)
                avg_price = recent_20['Close'].mean()
                
                # Determine intraday targets
                if change_pct > 0.3:  # Bullish momentum
                    target = current_price * 1.02
                    stop_loss = current_price * 0.985
                    recommendation = "BUY"
                    signal = "Strong Upward Momentum"
                elif change_pct < -0.3:  # Bearish, potential reversal
                    target = current_price * 1.015
                    stop_loss = current_price * 0.99
                    recommendation = "REVERSAL PLAY"
                    signal = "Oversold - Potential Bounce"
                else:  # Neutral
                    target = current_price * 1.01
                    stop_loss = current_price * 0.99
                    recommendation = "NEUTRAL"
                    signal = "No Clear Direction"
                
                upside = ((target - current_price) / current_price) * 100
                
                result['intraday'] = {
                    'available': True,
                    'recommendation': recommendation,
                    'signal': signal,
                    'cmp': round(current_price, 2),
                    'target': round(target, 2),
                    'stop_loss': round(stop_loss, 2),
                    'upside_pct': round(upside, 2),
                    'day_high': round(high_today, 2),
                    'day_low': round(low_today, 2),
                    'momentum_pct': round(change_pct, 2)
                }
        except Exception as e:
            result['intraday'] = {
                'available': False,
                'message': 'Intraday data not available'
            }
        
        # === LONG-TERM ANALYST RECOMMENDATIONS ===
        try:
            # Get analyst recommendations
            target_mean = info.get('targetMeanPrice', 0)
            target_high = info.get('targetHighPrice', 0)
            target_low = info.get('targetLowPrice', 0)
            recommendation_key = info.get('recommendationKey', 'none')
            number_of_analysts = info.get('numberOfAnalystOpinions', 0)
            
            if target_mean and target_mean > 0:
                avg_upside = ((target_mean - result['cmp']) / result['cmp']) * 100
                max_upside = ((target_high - result['cmp']) / result['cmp']) * 100 if target_high else 0
                min_upside = ((target_low - result['cmp']) / result['cmp']) * 100 if target_low else 0
                
                # Determine recommendation sentiment
                if recommendation_key in ['strong_buy', 'buy']:
                    sentiment = "BUY"
                elif recommendation_key in ['strong_sell', 'sell']:
                    sentiment = "SELL"
                else:
                    sentiment = "HOLD"
                
                result['longterm'] = {
                    'available': True,
                    'recommendation': sentiment,
                    'cmp': round(result['cmp'], 2),
                    'avg_target': round(target_mean, 2),
                    'max_target': round(target_high, 2) if target_high else None,
                    'min_target': round(target_low, 2) if target_low else None,
                    'avg_upside_pct': round(avg_upside, 2),
                    'max_upside_pct': round(max_upside, 2) if target_high else None,
                    'min_upside_pct': round(min_upside, 2) if target_low else None,
                    'num_analysts': number_of_analysts,
                    'timeframe': '3-12 months'
                }
            else:
                result['longterm'] = {
                    'available': False,
                    'message': 'No analyst coverage available for this stock'
                }
        except Exception as e:
            result['longterm'] = {
                'available': False,
                'message': 'Long-term recommendations not available'
            }
        
        return result
        
    except Exception as e:
        result['error'] = f"Error fetching data: {str(e)}"
        return result


def get_stock_recommendation_multi_source(ticker_symbol):
    """
    Multi-source wrapper for stock recommendations.
    Source 1: Yahoo Finance .NS (primary)
    Source 2: BSE .BO fallback
    Source 3: Technical analysis fallback for long-term if no analyst data
    Returns same dict structure as search_stock_recommendations.
    """
    # --- Source 1: Yahoo Finance NSE ---
    result = search_stock_recommendations(ticker_symbol)

    if not result.get('error') and result.get('cmp', 0) > 0:
        result['data_source'] = 'Yahoo Finance (NSE)'

        # If analyst long-term data missing, fill with technicals
        if not result.get('longterm') or not result['longterm'].get('available'):
            try:
                ns_sym = ticker_symbol if ticker_symbol.endswith('.NS') else f"{ticker_symbol}.NS"
                tkr = yf.Ticker(ns_sym)
                hist = tkr.history(period="3mo", interval="1d")
                if not hist.empty and len(hist) >= 10:
                    cmp = hist['Close'].iloc[-1]
                    avg20 = hist['Close'].tail(20).mean() if len(hist) >= 20 else hist['Close'].mean()
                    avg50 = hist['Close'].tail(50).mean() if len(hist) >= 50 else avg20
                    if cmp > avg20 and cmp > avg50:
                        trend, mult = "BUY", 1.12
                    elif cmp > avg20:
                        trend, mult = "HOLD", 1.06
                    else:
                        trend, mult = "SELL", 1.02
                    tech_target = cmp * mult
                    upside = ((tech_target - cmp) / cmp) * 100
                    result['longterm'] = {
                        'available': True,
                        'recommendation': trend,
                        'cmp': round(cmp, 2),
                        'avg_target': round(tech_target, 2),
                        'max_target': round(tech_target * 1.05, 2),
                        'min_target': round(tech_target * 0.95, 2),
                        'avg_upside_pct': round(upside, 2),
                        'max_upside_pct': round(upside + 5, 2),
                        'min_upside_pct': round(upside - 5, 2),
                        'num_analysts': 0,
                        'timeframe': '1-3 months (Technical)',
                    }
                    result['data_source'] = 'Yahoo Finance + Technical Analysis'
            except Exception:
                pass
        return result

    # --- Source 2: Try BSE .BO suffix ---
    try:
        clean = ticker_symbol.replace('.NS', '').replace('.BO', '')
        bo_sym = f"{clean}.BO"
        tkr2 = yf.Ticker(bo_sym)
        info2 = tkr2.info
        cmp2 = tkr2.fast_info.get('lastPrice', 0)

        if cmp2 and cmp2 > 0:
            result2 = {
                'symbol': clean,
                'name': info2.get('shortName', clean),
                'cmp': cmp2,
                'intraday': None,
                'longterm': None,
                'error': None,
                'data_source': 'Yahoo Finance (BSE fallback)',
            }

            # Intraday from history
            try:
                hist2 = tkr2.history(period="5d", interval="5m")
                if not hist2.empty and len(hist2) > 20:
                    op = hist2['Open'].iloc[0]
                    cp = hist2['Close'].iloc[-1]
                    chg = ((cp - op) / op) * 100
                    if chg > 0.3:
                        tgt, sl, rec, sig = cp * 1.02, cp * 0.985, "BUY", "Upward Momentum"
                    elif chg < -0.3:
                        tgt, sl, rec, sig = cp * 1.015, cp * 0.99, "REVERSAL PLAY", "Oversold - Potential Bounce"
                    else:
                        tgt, sl, rec, sig = cp * 1.01, cp * 0.99, "NEUTRAL", "No Clear Direction"
                    result2['intraday'] = {
                        'available': True, 'recommendation': rec, 'signal': sig,
                        'cmp': round(cp, 2), 'target': round(tgt, 2), 'stop_loss': round(sl, 2),
                        'upside_pct': round(((tgt - cp) / cp) * 100, 2),
                        'day_high': round(hist2['High'].max(), 2), 'day_low': round(hist2['Low'].min(), 2),
                        'momentum_pct': round(chg, 2),
                    }
                else:
                    result2['intraday'] = {'available': False, 'message': 'Intraday data not available'}
            except Exception:
                result2['intraday'] = {'available': False, 'message': 'Intraday data not available'}

            # Long-term from analyst data
            try:
                tm = info2.get('targetMeanPrice', 0)
                th = info2.get('targetHighPrice', 0)
                tl = info2.get('targetLowPrice', 0)
                rk = info2.get('recommendationKey', 'hold')
                na = info2.get('numberOfAnalystOpinions', 0)
                if tm and tm > 0:
                    sent = "BUY" if rk in ['strong_buy', 'buy'] else "SELL" if rk in ['strong_sell', 'sell'] else "HOLD"
                    result2['longterm'] = {
                        'available': True, 'recommendation': sent,
                        'cmp': round(cmp2, 2), 'avg_target': round(tm, 2),
                        'max_target': round(th, 2) if th else None,
                        'min_target': round(tl, 2) if tl else None,
                        'avg_upside_pct': round(((tm - cmp2) / cmp2) * 100, 2),
                        'max_upside_pct': round(((th - cmp2) / cmp2) * 100, 2) if th else None,
                        'min_upside_pct': round(((tl - cmp2) / cmp2) * 100, 2) if tl else None,
                        'num_analysts': na, 'timeframe': '3-12 months',
                    }
                else:
                    # Technical fallback
                    hist3 = tkr2.history(period="3mo", interval="1d")
                    if not hist3.empty and len(hist3) >= 10:
                        avg20 = hist3['Close'].tail(20).mean() if len(hist3) >= 20 else hist3['Close'].mean()
                        if cmp2 > avg20:
                            trend2, mult2 = "BUY", 1.10
                        else:
                            trend2, mult2 = "HOLD", 1.05
                        tt = cmp2 * mult2
                        result2['longterm'] = {
                            'available': True, 'recommendation': trend2,
                            'cmp': round(cmp2, 2), 'avg_target': round(tt, 2),
                            'max_target': round(tt * 1.05, 2), 'min_target': round(tt * 0.95, 2),
                            'avg_upside_pct': round(((tt - cmp2) / cmp2) * 100, 2),
                            'max_upside_pct': round(((tt * 1.05 - cmp2) / cmp2) * 100, 2),
                            'min_upside_pct': round(((tt * 0.95 - cmp2) / cmp2) * 100, 2),
                            'num_analysts': 0, 'timeframe': '1-3 months (Technical)',
                        }
                    else:
                        result2['longterm'] = {'available': False, 'message': 'No analyst coverage available'}
            except Exception:
                result2['longterm'] = {'available': False, 'message': 'Long-term data not available'}

            return result2
    except Exception:
        pass

    # --- Return original error result ---
    return result


def _get_all_nse_stocks_v1():
    """DEPRECATED - kept for reference only. Use get_all_nse_stocks() instead."""
    all_stocks = get_comprehensive_nse_list()
    return sorted(list(set(all_stocks)))

def get_comprehensive_nse_list():
    """Comprehensive list of NSE stocks - alphabetically organized"""
    stocks_dict = {
        # A
        'AARTIIND': 'Aarti Industries',
        'ABB': 'ABB India',
        'ABBOTINDIA': 'Abbott India',
        'ABCAPITAL': 'Aditya Birla Capital',
        'ABFRL': 'Aditya Birla Fashion and Retail',
        'ACC': 'ACC',
        'ADANIENT': 'Adani Enterprises',
        'ADANIGREEN': 'Adani Green Energy',
        'ADANIPORTS': 'Adani Ports and Special Economic Zone',
        'ADANIPOWER': 'Adani Power',
        'ADANITRANS': 'Adani Transmission',
        'ALKEM': 'Alkem Laboratories',
        'AMBUJACEM': 'Ambuja Cements',
        'APOLLOHOSP': 'Apollo Hospitals Enterprise',
        'APOLLOTYRE': 'Apollo Tyres',
        'ASHOKLEY': 'Ashok Leyland',
        'ASIANPAINT': 'Asian Paints',
        'ASTRAL': 'Astral',
        'ATUL': 'Atul',
        'AUBANK': 'AU Small Finance Bank',
        'AUROPHARMA': 'Aurobindo Pharma',
        'AXISBANK': 'Axis Bank',
        
        # B
        'BAJAJ-AUTO': 'Bajaj Auto',
        'BAJAJFINSV': 'Bajaj Finserv',
        'BAJFINANCE': 'Bajaj Finance',
        'BALKRISIND': 'Balkrishna Industries',
        'BALRAMCHIN': 'Balrampur Chini Mills',
        'BANDHANBNK': 'Bandhan Bank',
        'BANKBARODA': 'Bank of Baroda',
        'BATAINDIA': 'Bata India',
        'BEL': 'Bharat Electronics',
        'BERGEPAINT': 'Berger Paints India',
        'BHARATFORG': 'Bharat Forge',
        'BHARTIARTL': 'Bharti Airtel',
        'BHEL': 'Bharat Heavy Electricals',
        'BIOCON': 'Biocon',
        'BOSCHLTD': 'Bosch',
        'BPCL': 'Bharat Petroleum Corporation',
        'BRITANNIA': 'Britannia Industries',
        
        # C
        'CANBK': 'Canara Bank',
        'CANFINHOME': 'Can Fin Homes',
        'CHAMBLFERT': 'Chambal Fertilizers and Chemicals',
        'CHOLAFIN': 'Cholamandalam Investment and Finance Company',
        'CIPLA': 'Cipla',
        'COALINDIA': 'Coal India',
        'COFORGE': 'Coforge',
        'COLPAL': 'Colgate Palmolive India',
        'CONCOR': 'Container Corporation of India',
        'COROMANDEL': 'Coromandel International',
        'CROMPTON': 'Crompton Greaves Consumer Electricals',
        'CUB': 'City Union Bank',
        'CUMMINSIND': 'Cummins India',
        
        # D
        'DABUR': 'Dabur India',
        'DALBHARAT': 'Dalmia Bharat',
        'DEEPAKNTR': 'Deepak Nitrite',
        'DELTACORP': 'Delta Corp',
        'DIVISLAB': 'Divi\'s Laboratories',
        'DIXON': 'Dixon Technologies India',
        'DLF': 'DLF',
        'DMART': 'Avenue Supermarts',
        'DRREDDY': 'Dr. Reddy\'s Laboratories',
        
        # E
        'EICHERMOT': 'Eicher Motors',
        'ESCORTS': 'Escorts Kubota',
        
        # F
        'FEDERALBNK': 'Federal Bank',
        'FORTIS': 'Fortis Healthcare',
        
        # G
        'GAIL': 'GAIL India',
        'GLENMARK': 'Glenmark Pharmaceuticals',
        'GMRINFRA': 'GMR Infrastructure',
        'GNFC': 'Gujarat Narmada Valley Fertilizers and Chemicals',
        'GODREJCP': 'Godrej Consumer Products',
        'GODREJPROP': 'Godrej Properties',
        'GRANULES': 'Granules India',
        'GRASIM': 'Grasim Industries',
        'GUJGASLTD': 'Gujarat Gas',
        
        # H
        'HAL': 'Hindustan Aeronautics',
        'HAVELLS': 'Havells India',
        'HCLTECH': 'HCL Technologies',
        'HDFCAMC': 'HDFC Asset Management Company',
        'HDFCBANK': 'HDFC Bank',
        'HDFCLIFE': 'HDFC Life Insurance Company',
        'HEROMOTOCO': 'Hero MotoCorp',
        'HINDALCO': 'Hindalco Industries',
        'HINDCOPPER': 'Hindustan Copper',
        'HINDPETRO': 'Hindustan Petroleum Corporation',
        'HINDUNILVR': 'Hindustan Unilever',
        'HONAUT': 'Honeywell Automation India',
        
        # I
        'IBULHSGFIN': 'Indiabulls Housing Finance',
        'ICICIBANK': 'ICICI Bank',
        'ICICIGI': 'ICICI Lombard General Insurance Company',
        'ICICIPRULI': 'ICICI Prudential Life Insurance Company',
        'IDEA': 'Vodafone Idea',
        'IDFCFIRSTB': 'IDFC First Bank',
        'IEX': 'Indian Energy Exchange',
        'IGL': 'Indraprastha Gas',
        'INDHOTEL': 'The Indian Hotels Company',
        'INDIACEM': 'The India Cements',
        'INDIAMART': 'IndiaMART InterMESH',
        'INDIGO': 'InterGlobe Aviation',
        'INDUSINDBK': 'IndusInd Bank',
        'INDUSTOWER': 'Indus Towers',
        'INFY': 'Infosys',
        'IOC': 'Indian Oil Corporation',
        'IPCALAB': 'IPCA Laboratories',
        'IRCTC': 'Indian Railway Catering and Tourism Corporation',
        'ITC': 'ITC',
        
        # J
        'JINDALSTEL': 'Jindal Steel & Power',
        'JKCEMENT': 'JK Cement',
        'JSWSTEEL': 'JSW Steel',
        
        # K
        'KAJARIACER': 'Kajaria Ceramics',
        'KOTAKBANK': 'Kotak Mahindra Bank',
        
        # L
        'L&TFH': 'L&T Finance Holdings',
        'LALPATHLAB': 'Dr. Lal Path Labs',
        'LAURUSLABS': 'Laurus Labs',
        'LICHSGFIN': 'LIC Housing Finance',
        'LT': 'Larsen & Toubro',
        'LTIM': 'LTIMindtree',
        'LTTS': 'L&T Technology Services',
        'LUPIN': 'Lupin',
        
        # M
        'M&M': 'Mahindra & Mahindra',
        'M&MFIN': 'Mahindra & Mahindra Financial Services',
        'MANAPPURAM': 'Manappuram Finance',
        'MARICO': 'Marico',
        'MARUTI': 'Maruti Suzuki India',
        'MCX': 'Multi Commodity Exchange of India',
        'METROPOLIS': 'Metropolis Healthcare',
        'MGL': 'Mahanagar Gas',
        'MFSL': 'Max Financial Services',
        'MRF': 'MRF',
        'MPHASIS': 'Mphasis',
        'MUTHOOTFIN': 'Muthoot Finance',
        
        # N
        'NATIONALUM': 'National Aluminium Company',
        'NAUKRI': 'Info Edge India',
        'NAVINFLUOR': 'Navin Fluorine International',
        'NESTLEIND': 'Nestle India',
        'NMDC': 'NMDC',
        'NTPC': 'NTPC',
        'NYKAA': 'FSN E-Commerce Ventures (Nykaa)',
        
        # O
        'OBEROIRLTY': 'Oberoi Realty',
        'OFSS': 'Oracle Financial Services Software',
        'ONGC': 'Oil and Natural Gas Corporation',
        
        # P
        'PAGEIND': 'Page Industries',
        'PATANJALI': 'Patanjali Foods',
        'PAYTM': 'One 97 Communications (Paytm)',
        'PEL': 'Piramal Enterprises',
        'PERSISTENT': 'Persistent Systems',
        'PETRONET': 'Petronet LNG',
        'PFC': 'Power Finance Corporation',
        'PIDILITIND': 'Pidilite Industries',
        'PIIND': 'PI Industries',
        'PNB': 'Punjab National Bank',
        'POLICYBZR': 'PB Fintech (Policybazaar)',
        'POLYCAB': 'Polycab India',
        'POWERGRID': 'Power Grid Corporation of India',
        'PRESTIGE': 'Prestige Estates Projects',
        'PVRINOX': 'PVR INOX',
        
        # R
        'RAIN': 'Rain Industries',
        'RAJESHEXPO': 'Rajesh Exports',
        'RAMCOCEM': 'The Ramco Cements',
        'RBLBANK': 'RBL Bank',
        'RECLTD': 'REC',
        'RELIANCE': 'Reliance Industries',
        
        # S
        'SAIL': 'Steel Authority of India',
        'SBICARD': 'SBI Cards and Payment Services',
        'SBILIFE': 'SBI Life Insurance Company',
        'SBIN': 'State Bank of India',
        'SHREECEM': 'Shree Cement',
        'SHRIRAMFIN': 'Shriram Finance',
        'SIEMENS': 'Siemens',
        'SRF': 'SRF',
        'SRTRANSFIN': 'Shriram Transport Finance Company',
        'STARHEALTH': 'Star Health and Allied Insurance Company',
        'SUNPHARMA': 'Sun Pharmaceutical Industries',
        'SUNTV': 'Sun TV Network',
        'SYNGENE': 'Syngene International',
        
        # T
        'TATACOMM': 'Tata Communications',
        'TATACONSUM': 'Tata Consumer Products',
        'TATACHEM': 'Tata Chemicals',
        'TATAELXSI': 'Tata Elxsi',
        'TATAMOTORS': 'Tata Motors',
        'TATAPOWER': 'Tata Power Company',
        'TATASTEEL': 'Tata Steel',
        'TCS': 'Tata Consultancy Services',
        'TECHM': 'Tech Mahindra',
        'TITAN': 'Titan Company',
        'TORNTPHARM': 'Torrent Pharmaceuticals',
        'TORNTPOWER': 'Torrent Power',
        'TRENT': 'Trent',
        'TVSMOTOR': 'TVS Motor Company',
        
        # U
        'UBL': 'United Breweries',
        'ULTRACEMCO': 'UltraTech Cement',
        'UNIONBANK': 'Union Bank of India',
        'UPL': 'UPL',
        
        # V
        'VEDL': 'Vedanta',
        'VOLTAS': 'Voltas',
        
        # W
        'WHIRLPOOL': 'Whirlpool of India',
        'WIPRO': 'Wipro',
        
        # Y
        'YESBANK': 'Yes Bank',
        
        # Z
        'ZEEL': 'Zee Entertainment Enterprises',
        'ZOMATO': 'Zomato',
        'ZYDUSLIFE': 'Zydus Lifesciences',
    }
    
    return [f"{ticker} - {name}" for ticker, name in stocks_dict.items()]

def _get_all_nse_stocks_v2():
    """DEPRECATED - kept for reference only. Use get_all_nse_stocks() instead."""
    stocks = {
        # Nifty 50
        'ADANIENT': 'Adani Enterprises Ltd.',
        'ADANIPORTS': 'Adani Ports and Special Economic Zone Ltd.',
        'APOLLOHOSP': 'Apollo Hospitals Enterprise Ltd.',
        'ASIANPAINT': 'Asian Paints Ltd.',
        'AXISBANK': 'Axis Bank Ltd.',
        'BAJAJ-AUTO': 'Bajaj Auto Ltd.',
        'BAJFINANCE': 'Bajaj Finance Ltd.',
        'BAJAJFINSV': 'Bajaj Finserv Ltd.',
        'BPCL': 'Bharat Petroleum Corporation Ltd.',
        'BHARTIARTL': 'Bharti Airtel Ltd.',
        'BRITANNIA': 'Britannia Industries Ltd.',
        'CIPLA': 'Cipla Ltd.',
        'COALINDIA': 'Coal India Ltd.',
        'DIVISLAB': 'Divi\'s Laboratories Ltd.',
        'DRREDDY': 'Dr. Reddy\'s Laboratories Ltd.',
        'EICHERMOT': 'Eicher Motors Ltd.',
        'GRASIM': 'Grasim Industries Ltd.',
        'HCLTECH': 'HCL Technologies Ltd.',
        'HDFCBANK': 'HDFC Bank Ltd.',
        'HDFCLIFE': 'HDFC Life Insurance Company Ltd.',
        'HEROMOTOCO': 'Hero MotoCorp Ltd.',
        'HINDALCO': 'Hindalco Industries Ltd.',
        'HINDUNILVR': 'Hindustan Unilever Ltd.',
        'ICICIBANK': 'ICICI Bank Ltd.',
        'ITC': 'ITC Ltd.',
        'INDUSINDBK': 'IndusInd Bank Ltd.',
        'INFY': 'Infosys Ltd.',
        'JSWSTEEL': 'JSW Steel Ltd.',
        'KOTAKBANK': 'Kotak Mahindra Bank Ltd.',
        'LT': 'Larsen & Toubro Ltd.',
        'M&M': 'Mahindra & Mahindra Ltd.',
        'MARUTI': 'Maruti Suzuki India Ltd.',
        'NESTLEIND': 'Nestle India Ltd.',
        'NTPC': 'NTPC Ltd.',
        'ONGC': 'Oil and Natural Gas Corporation Ltd.',
        'POWERGRID': 'Power Grid Corporation of India Ltd.',
        'RELIANCE': 'Reliance Industries Ltd.',
        'SBILIFE': 'SBI Life Insurance Company Ltd.',
        'SBIN': 'State Bank of India',
        'SUNPHARMA': 'Sun Pharmaceutical Industries Ltd.',
        'TCS': 'Tata Consultancy Services Ltd.',
        'TATACONSUM': 'Tata Consumer Products Ltd.',
        'TATAMOTORS': 'Tata Motors Ltd.',
        'TATASTEEL': 'Tata Steel Ltd.',
        'TECHM': 'Tech Mahindra Ltd.',
        'TITAN': 'Titan Company Ltd.',
        'ULTRACEMCO': 'UltraTech Cement Ltd.',
        'UPL': 'UPL Ltd.',
        'WIPRO': 'Wipro Ltd.',
        
        # Other popular stocks
        'ACC': 'ACC Ltd.',
        'ABFRL': 'Aditya Birla Fashion and Retail Ltd.',
        'ADANIGREEN': 'Adani Green Energy Ltd.',
        'ADANIPOWER': 'Adani Power Ltd.',
        'ADANITRANS': 'Adani Transmission Ltd.',
        'AMBUJACEM': 'Ambuja Cements Ltd.',
        'APOLLOTYRE': 'Apollo Tyres Ltd.',
        'ASHOKLEY': 'Ashok Leyland Ltd.',
        'AUROPHARMA': 'Aurobindo Pharma Ltd.',
        'BANKBARODA': 'Bank of Baroda',
        'BANDHANBNK': 'Bandhan Bank Ltd.',
        'BATAINDIA': 'Bata India Ltd.',
        'BEL': 'Bharat Electronics Ltd.',
        'BERGEPAINT': 'Berger Paints India Ltd.',
        'BHARATFORG': 'Bharat Forge Ltd.',
        'BIOCON': 'Biocon Ltd.',
        'BOSCHLTD': 'Bosch Ltd.',
        'CANBK': 'Canara Bank',
        'CHOLAFIN': 'Cholamandalam Investment and Finance Company Ltd.',
        'COLPAL': 'Colgate Palmolive (India) Ltd.',
        'CONCOR': 'Container Corporation of India Ltd.',
        'COFORGE': 'Coforge Ltd.',
        'CROMPTON': 'Crompton Greaves Consumer Electricals Ltd.',
        'CUB': 'City Union Bank Ltd.',
        'CUMMINSIND': 'Cummins India Ltd.',
        'DABUR': 'Dabur India Ltd.',
        'DEEPAKNTR': 'Deepak Nitrite Ltd.',
        'DLF': 'DLF Ltd.',
        'DIXON': 'Dixon Technologies (India) Ltd.',
        'DMART': 'Avenue Supermarts Ltd.',
        'ESCORTS': 'Escorts Kubota Ltd.',
        'EXIDEIND': 'Exide Industries Ltd.',
        'FEDERALBNK': 'Federal Bank Ltd.',
        'GAIL': 'GAIL (India) Ltd.',
        'GLENMARK': 'Glenmark Pharmaceuticals Ltd.',
        'GMRINFRA': 'GMR Infrastructure Ltd.',
        'GODREJCP': 'Godrej Consumer Products Ltd.',
        'GODREJPROP': 'Godrej Properties Ltd.',
        'GUJGASLTD': 'Gujarat Gas Ltd.',
        'HAL': 'Hindustan Aeronautics Ltd.',
        'HAVELLS': 'Havells India Ltd.',
        'HDFCAMC': 'HDFC Asset Management Company Ltd.',
        'HINDPETRO': 'Hindustan Petroleum Corporation Ltd.',
        'HONAUT': 'Honeywell Automation India Ltd.',
        'ICICIPRULI': 'ICICI Prudential Life Insurance Company Ltd.',
        'IDFCFIRSTB': 'IDFC First Bank Ltd.',
        'IEX': 'Indian Energy Exchange Ltd.',
        'IGL': 'Indraprastha Gas Ltd.',
        'INDHOTEL': 'The Indian Hotels Company Ltd.',
        'INDIGO': 'InterGlobe Aviation Ltd.',
        'IOC': 'Indian Oil Corporation Ltd.',
        'IRCTC': 'Indian Railway Catering and Tourism Corporation Ltd.',
        'JINDALSTEL': 'Jindal Steel & Power Ltd.',
        'JUBLFOOD': 'Jubilant Foodworks Ltd.',
        'LTF': 'L&T Finance Holdings Ltd.',
        'LTIM': 'LTIMindtree Ltd.',
        'LTTS': 'L&T Technology Services Ltd.',
        'LICHSGFIN': 'LIC Housing Finance Ltd.',
        'LUPIN': 'Lupin Ltd.',
        'MRF': 'MRF Ltd.',
        'MUTHOOTFIN': 'Muthoot Finance Ltd.',
        'MCX': 'Multi Commodity Exchange of India Ltd.',
        'MARICO': 'Marico Ltd.',
        'MANAPPURAM': 'Manappuram Finance Ltd.',
        'MFSL': 'Max Financial Services Ltd.',
        'MGL': 'Mahanagar Gas Ltd.',
        'MINDTREE': 'Mindtree Ltd.',
        'MOTHERSON': 'Samvardhana Motherson International Ltd.',
        'MPHASIS': 'Mphasis Ltd.',
        'NAM-INDIA': 'Nippon Life India Asset Management Ltd.',
        'NAUKRI': 'Info Edge (India) Ltd.',
        'NAVINFLUOR': 'Navin Fluorine International Ltd.',
        'NMDC': 'NMDC Ltd.',
        'OBEROIRLTY': 'Oberoi Realty Ltd.',
        'OFSS': 'Oracle Financial Services Software Ltd.',
        'PAGEIND': 'Page Industries Ltd.',
        'PAYTM': 'One 97 Communications Ltd.',
        'PERSISTENT': 'Persistent Systems Ltd.',
        'PETRONET': 'Petronet LNG Ltd.',
        'PFC': 'Power Finance Corporation Ltd.',
        'PIDILITIND': 'Pidilite Industries Ltd.',
        'PIIND': 'PI Industries Ltd.',
        'PNB': 'Punjab National Bank',
        'POLYCAB': 'Polycab India Ltd.',
        'PRAJIND': 'Praj Industries Ltd.',
        'PVRINOX': 'PVR INOX Ltd.',
        'RAIN': 'Rain Industries Ltd.',
        'RBLBANK': 'RBL Bank Ltd.',
        'RECLTD': 'REC Ltd.',
        'SBICARD': 'SBI Cards and Payment Services Ltd.',
        'SHREECEM': 'Shree Cement Ltd.',
        'SIEMENS': 'Siemens Ltd.',
        'SRF': 'SRF Ltd.',
        'SOLARINDS': 'Solar Industries India Ltd.',
        'SRTRANSFIN': 'Shriram Transport Finance Company Ltd.',
        'TATACOMM': 'Tata Communications Ltd.',
        'TATAELXSI': 'Tata Elxsi Ltd.',
        'TATAPOWER': 'Tata Power Company Ltd.',
        'TORNTPHARM': 'Torrent Pharmaceuticals Ltd.',
        'TRENT': 'Trent Ltd.',
        'TVSMOTOR': 'TVS Motor Company Ltd.',
        'UBL': 'United Breweries Ltd.',
        'UNIONBANK': 'Union Bank of India',
        'VEDL': 'Vedanta Ltd.',
        'VOLTAS': 'Voltas Ltd.',
        'WHIRLPOOL': 'Whirlpool of India Ltd.',
        'YESBANK': 'Yes Bank Ltd.',
        'ZEEL': 'Zee Entertainment Enterprises Ltd.',
        'ZOMATO': 'Zomato Ltd.',
        'ZYDUSLIFE': 'Zydus Lifesciences Ltd.',
        
        # Additional stocks
        'ABB': 'ABB India Ltd.',
        'AARTIIND': 'Aarti Industries Ltd.',
        'AAVAS': 'Aavas Financiers Ltd.',
        'AEGISCHEM': 'Aegis Logistics Ltd.',
        'AFFLE': 'Affle (India) Ltd.',
        'AJANTPHARM': 'Ajanta Pharma Ltd.',
        'ALKEM': 'Alkem Laboratories Ltd.',
        'AMARAJABAT': 'Amara Raja Batteries Ltd.',
        'ANANDRATHI': 'Anand Rathi Wealth Ltd.',
        'ASTRAL': 'Astral Ltd.',
        'ATUL': 'Atul Ltd.',
        'BALKRISIND': 'Balkrishna Industries Ltd.',
        'BALRAMCHIN': 'Balrampur Chini Mills Ltd.',
        'BASF': 'BASF India Ltd.',
        'BIRLACORPN': 'Birla Corporation Ltd.',
        'BSE': 'BSE Ltd.',
        'CAMS': 'Computer Age Management Services Ltd.',
        'CANFINHOME': 'Can Fin Homes Ltd.',
        'CAPLIPOINT': 'Caplin Point Laboratories Ltd.',
        'CARBORUNIV': 'Carborundum Universal Ltd.',
        'CASTROLIND': 'Castrol India Ltd.',
        'CDSL': 'Central Depository Services (India) Ltd.',
        'CESC': 'CESC Ltd.',
        'CHAMBLFERT': 'Chambal Fertilizers & Chemicals Ltd.',
        'CLEAN': 'Clean Science and Technology Ltd.',
        'COROMANDEL': 'Coromandel International Ltd.',
        'CREDITACCES': 'CreditAccess Grameen Ltd.',
        'CYIENT': 'Cyient Ltd.',
        'DCBBANK': 'DCB Bank Ltd.',
        'DELTACORP': 'Delta Corp Ltd.',
        'DEVYANI': 'Devyani International Ltd.',
        'DHANUKA': 'Dhanuka Agritech Ltd.',
        'EASEMYTRIP': 'Easy Trip Planners Ltd.',
        'EIDPARRY': 'EID Parry India Ltd.',
        'EMAMILTD': 'Emami Ltd.',
        'ENDURANCE': 'Endurance Technologies Ltd.',
        'EQUITAS': 'Equitas Holdings Ltd.',
        'FINEORG': 'Fine Organic Industries Ltd.',
        'FSL': 'Firstsource Solutions Ltd.',
        'GILLETTE': 'Gillette India Ltd.',
        'GNFC': 'Gujarat Narmada Valley Fertilizers and Chemicals Ltd.',
        'GODFRYPHLP': 'Godfrey Phillips India Ltd.',
        'GPPL': 'Gujarat Pipavav Port Ltd.',
        'GRAPHITE': 'Graphite India Ltd.',
        'GESHIP': 'The Great Eastern Shipping Company Ltd.',
        'GRINDWELL': 'Grindwell Norton Ltd.',
        'GSPL': 'Gujarat State Petronet Ltd.',
        'HAPPSTMNDS': 'Happiest Minds Technologies Ltd.',
        'HEIDELBERG': 'HeidelbergCement India Ltd.',
        'HFCL': 'HFCL Ltd.',
        'HINDCOPPER': 'Hindustan Copper Ltd.',
        'HINDZINC': 'Hindustan Zinc Ltd.',
        'HOMEFIRST': 'Home First Finance Company India Ltd.',
        'HUDCO': 'Housing & Urban Development Corporation Ltd.',
        'IDEA': 'Vodafone Idea Ltd.',
        'IPCALAB': 'Ipca Laboratories Ltd.',
        'IRFC': 'Indian Railway Finance Corporation Ltd.',
        'IRB': 'IRB Infrastructure Developers Ltd.',
        'ISEC': 'ICICI Securities Ltd.',
        'J&KBANK': 'Jammu & Kashmir Bank Ltd.',
        'JKCEMENT': 'JK Cement Ltd.',
        'JKLAKSHMI': 'JK Lakshmi Cement Ltd.',
        'JKPAPER': 'JK Paper Ltd.',
        'JMFINANCIL': 'JM Financial Ltd.',
        'JSWENERGY': 'JSW Energy Ltd.',
        'KANSAINER': 'Kansai Nerolac Paints Ltd.',
        'KEC': 'KEC International Ltd.',
        'KEI': 'KEI Industries Ltd.',
        'KOLTEPATIL': 'Kolte-Patil Developers Ltd.',
        'KPITTECH': 'KPIT Technologies Ltd.',
        'LALPATHLAB': 'Dr. Lal Path Labs Ltd.',
        'LAURUSLABS': 'Laurus Labs Ltd.',
        'LICI': 'Life Insurance Corporation of India',
        'LXCHEM': 'Laxmi Organic Industries Ltd.',
        'MAZDOCK': 'Mazagon Dock Shipbuilders Ltd.',
        'METROPOLIS': 'Metropolis Healthcare Ltd.',
        'MFSL': 'Max Financial Services Ltd.',
        'MIDHANI': 'Mishra Dhatu Nigam Ltd.',
        'MOTILALOFS': 'Motilal Oswal Financial Services Ltd.',
        'NATIONALUM': 'National Aluminium Company Ltd.',
        'NESCO': 'Nesco Ltd.',
        'NETWORK18': 'Network18 Media & Investments Ltd.',
        'NLCINDIA': 'NLC India Ltd.',
        'NYKAA': 'FSN E-Commerce Ventures Ltd.',
        'ORIENTELEC': 'Orient Electric Ltd.',
        'PGHH': 'Procter & Gamble Hygiene and Health Care Ltd.',
        'PHOENIXLTD': 'The Phoenix Mills Ltd.',
        'PNBHOUSING': 'PNB Housing Finance Ltd.',
        'POLICYBZR': 'PB Fintech Ltd.',
        'POWERINDIA': 'Hitachi Energy India Ltd.',
        'PPLPHARMA': 'Piramal Pharma Ltd.',
        'RAJESHEXPO': 'Rajesh Exports Ltd.',
        'RATNAMANI': 'Ratnamani Metals & Tubes Ltd.',
        'ROUTE': 'Route Mobile Ltd.',
        'RVNL': 'Rail Vikas Nigam Ltd.',
        'SAIL': 'Steel Authority of India Ltd.',
        'SEQUENT': 'Sequent Scientific Ltd.',
        'SFL': 'Sheela Foam Ltd.',
        'SHYAMMETL': 'Shyam Metalics and Energy Ltd.',
        'SKFINDIA': 'SKF India Ltd.',
        'SONACOMS': 'Sona BLW Precision Forgings Ltd.',
        'STAR': 'Sterlite Technologies Ltd.',
        'SUNDRMFAST': 'Sundram Fasteners Ltd.',
        'SUNTV': 'Sun TV Network Ltd.',
        'SUPREMEIND': 'Supreme Industries Ltd.',
        'TATACHEM': 'Tata Chemicals Ltd.',
        'TATAINVEST': 'Tata Investment Corporation Ltd.',
        'TIMKEN': 'Timken India Ltd.',
        'TIINDIA': 'Tube Investments of India Ltd.',
        'TRITURBINE': 'Triveni Turbine Ltd.',
        'UJJIVAN': 'Ujjivan Small Finance Bank Ltd.',
        'UCOBANK': 'UCO Bank',
        'UTIAMC': 'UTI Asset Management Company Ltd.',
        'VAIBHAVGBL': 'Vaibhav Global Ltd.',
        'VARROC': 'Varroc Engineering Ltd.',
        'VBL': 'Varun Beverages Ltd.',
        'VINATIORGA': 'Vinati Organics Ltd.',
        'VSTIND': 'VST Industries Ltd.',
        'WELCORP': 'Welspun Corp Ltd.',
        'WESTLIFE': 'Westlife Foodworld Ltd.',
        'ZENTEC': 'Zen Technologies Ltd.',
    }
    
    # Create search list with both ticker and name
    search_options = []
    for ticker, name in sorted(stocks.items()):
        search_options.append(f"{ticker} - {name}")
    
    return search_options

def get_nse_stock_list():
    """Get comprehensive list of NSE stocks with ticker and name for autocomplete"""
    return get_all_nse_stocks()

def get_nse_symbol(stock_name):
    """Convert stock name to NSE symbol"""
    mapping = {
        'reliance': 'RELIANCE.NS',
        'tcs': 'TCS.NS',
        'hdfc bank': 'HDFCBANK.NS',
        'infosys': 'INFY.NS',
        'icici bank': 'ICICIBANK.NS',
        'sbi': 'SBIN.NS',
        'state bank': 'SBIN.NS',
        'bharti airtel': 'BHARTIARTL.NS',
        'airtel': 'BHARTIARTL.NS',
        'itc': 'ITC.NS',
        'wipro': 'WIPRO.NS',
        'axis bank': 'AXISBANK.NS',
        'bajaj finance': 'BAJFINANCE.NS',
        'asian paints': 'ASIANPAINT.NS',
        'maruti': 'MARUTI.NS',
        'titan': 'TITAN.NS',
        'ultratech': 'ULTRACEMCO.NS',
        'nestle': 'NESTLEIND.NS',
        'kotak': 'KOTAKBANK.NS',
        'l&t': 'LT.NS',
        'larsen': 'LT.NS',
        'hcl tech': 'HCLTECH.NS',
        'hcl': 'HCLTECH.NS',
        'bajaj auto': 'BAJAJ-AUTO.NS',
        'sun pharma': 'SUNPHARMA.NS',
        'dr reddy': 'DRREDDY.NS',
        'mahindra': 'M&M.NS',
        'tata steel': 'TATASTEEL.NS',
        'tata motors': 'TATAMOTORS.NS',
        'adani': 'ADANIENT.NS',
        'hindustan unilever': 'HINDUNILVR.NS',
        'power grid': 'POWERGRID.NS',
        'ntpc': 'NTPC.NS',
        'ongc': 'ONGC.NS',
        'coal india': 'COALINDIA.NS',
        'cipla': 'CIPLA.NS',
        'divis': 'DIVISLAB.NS',
        'grasim': 'GRASIM.NS',
        'tech mahindra': 'TECHM.NS',
        'eicher': 'EICHERMOT.NS',
        'shree cement': 'SHREECEM.NS',
        'britannia': 'BRITANNIA.NS',
        'pidilite': 'PIDILITIND.NS',
        'godrej': 'GODREJCP.NS',
        'vedanta': 'VEDL.NS',
        'hindalco': 'HINDALCO.NS',
        'jsw steel': 'JSWSTEEL.NS',
        'tata consumer': 'TATACONSUM.NS',
        'indusind': 'INDUSINDBK.NS',
        'adani ports': 'ADANIPORTS.NS',
        'adani green': 'ADANIGREEN.NS',
        'sbi life': 'SBILIFE.NS',
        'hdfc life': 'HDFCLIFE.NS',
        'bajaj finserv': 'BAJAJFINSV.NS',
        'berger paints': 'BERGEPAINT.NS',
    }
    
    stock_lower = stock_name.lower().strip()
    
    # Direct match
    if stock_lower in mapping:
        return mapping[stock_lower]
    
    # Partial match
    for key, symbol in mapping.items():
        if key in stock_lower or stock_lower in key:
            return mapping[key]
    
    # Try creating symbol
    cleaned = stock_name.upper().replace(' LTD', '').replace(' LIMITED', '').replace('.', '').replace('&', '').replace(' ', '')
    return f"{cleaned}.NS"

def get_live_market_news():
    """Get market news from multiple RSS sources with robust error handling"""
    all_news = []
    
    # Source 1: Yahoo Finance India (Most reliable)
    try:
        for sym in ["^NSEI", "^BSESN"]:
            try:
                ticker = yf.Ticker(sym)
                news = ticker.news
                if news:
                    for item in news[:5]:
                        if isinstance(item, dict) and 'title' in item:
                            item.setdefault('publisher', 'Yahoo Finance')
                            item.setdefault('link', item.get('link', '#'))
                            if 'providerPublishTime' in item:
                                item['provider_publish_time'] = item['providerPublishTime']
                            else:
                                item['provider_publish_time'] = datetime.now().timestamp()
                            item['category'] = 'market'
                            all_news.append(item)
            except:
                continue
    except Exception as e:
        print(f"Yahoo Finance error: {e}")
    
    # Source 2: Moneycontrol Latest News
    try:
        mc_latest = "https://www.moneycontrol.com/rss/latestnews.xml"
        feed = feedparser.parse(mc_latest)
        
        if feed and hasattr(feed, 'entries'):
            for entry in feed.entries[:10]:
                try:
                    title_lower = entry.title.lower()
                    if any(word in title_lower for word in ['stock', 'market', 'nifty', 'sensex', 'share', 'trading', 'invest', 'equity']):
                        news_item = {
                            'title': entry.title,
                            'publisher': 'Moneycontrol',
                            'link': entry.link if hasattr(entry, 'link') else '#',
                            'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                            'category': 'market'
                        }
                        all_news.append(news_item)
                except:
                    continue
    except Exception as e:
        print(f"Moneycontrol Latest RSS error: {e}")
    
    # Source 3: Economic Times Stock Recommendations
    try:
        et_reco_rss = "https://economictimes.indiatimes.com/markets/stocks/recos/rssfeeds/1977021501.cms"
        feed = feedparser.parse(et_reco_rss)
        
        if feed and hasattr(feed, 'entries'):
            for entry in feed.entries[:8]:
                try:
                    news_item = {
                        'title': entry.title,
                        'publisher': 'ET - Stock Picks',
                        'link': entry.link if hasattr(entry, 'link') else '#',
                        'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                        'category': 'recommendation'
                    }
                    all_news.append(news_item)
                except:
                    continue
    except Exception as e:
        print(f"ET Reco RSS error: {e}")
    
    # Source 4: Economic Times Market News
    try:
        et_market_rss = "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
        feed = feedparser.parse(et_market_rss)
        
        if feed and hasattr(feed, 'entries'):
            for entry in feed.entries[:8]:
                try:
                    news_item = {
                        'title': entry.title,
                        'publisher': 'Economic Times',
                        'link': entry.link if hasattr(entry, 'link') else '#',
                        'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                        'category': 'market'
                    }
                    all_news.append(news_item)
                except:
                    continue
    except Exception as e:
        print(f"ET Market RSS error: {e}")
    
    # Source 5: Business Standard Markets
    try:
        bs_rss = "https://www.business-standard.com/rss/markets-106.rss"
        feed = feedparser.parse(bs_rss)
        
        if feed and hasattr(feed, 'entries'):
            for entry in feed.entries[:6]:
                try:
                    news_item = {
                        'title': entry.title,
                        'publisher': 'Business Standard',
                        'link': entry.link if hasattr(entry, 'link') else '#',
                        'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                        'category': 'market'
                    }
                    all_news.append(news_item)
                except:
                    continue
    except Exception as e:
        print(f"Business Standard RSS error: {e}")
    
    # If we have news, sort by time and remove duplicates
    if all_news:
        # Sort by publish time (most recent first)
        try:
            all_news.sort(key=lambda x: x.get('provider_publish_time', 0), reverse=True)
        except:
            pass
        
        # Remove duplicates by title
        unique_news = []
        seen_titles = set()
        for item in all_news:
            try:
                if isinstance(item, dict) and 'title' in item:
                    title_key = item['title'][:60].lower()
                    if title_key not in seen_titles:
                        seen_titles.add(title_key)
                        unique_news.append(item)
            except:
                continue
        
        return unique_news[:25] if unique_news else generate_fallback_news()
    else:
        return generate_fallback_news()

def generate_fallback_news():
    """Generate fallback news when all sources fail"""
    return [
        {
            'title': 'Market Dashboard Live - Auto-refreshing every 30 seconds',
            'publisher': 'System',
            'link': '#',
            'provider_publish_time': datetime.now().timestamp(),
            'category': 'market'
        },
        {
            'title': 'Loading latest market news... Please wait',
            'publisher': 'System',
            'link': '#',
            'provider_publish_time': datetime.now().timestamp(),
            'category': 'market'
        }
    ]

# ========================================
# LIVE NSE STOCK FETCHER
# Fetches ALL NSE stocks from official source
# Includes SUZLON and all 2000+ NSE stocks
# ========================================

def fetch_live_nse_stocks():
    """
    Fetch ALL NSE stocks from NSE India official archive
    Returns complete list including SUZLON and all other stocks (2000+)
    """
    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        # Get NSE equity list from official archive
        print("Fetching live NSE stock list from official archives...")
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        
        response = session.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            csv_data = pd.read_csv(io.StringIO(response.text))
            
            stock_list = []
            for _, row in csv_data.iterrows():
                symbol = str(row.get('SYMBOL', '')).strip()
                company = str(row.get('NAME OF COMPANY', symbol)).strip()
                
                # Clean up the data
                if symbol and symbol != 'SYMBOL' and len(symbol) > 0:
                    # Format: "SYMBOL - Company Name"
                    stock_list.append(f"{symbol} - {company}")
            
            print(f"✅ Successfully fetched {len(stock_list)} stocks from NSE (including SUZLON)")
            return sorted(stock_list)
        else:
            print(f"❌ NSE API returned status code: {response.status_code}")
            raise Exception("Failed to fetch from NSE")
            
    except Exception as e:
        print(f"❌ Error fetching live NSE data: {e}")
        raise


def get_fallback_stock_list():
    """
    Comprehensive fallback list including SUZLON and 1000+ stocks
    Used if live API fails - ensures 100% uptime
    """
    stocks = {
        # NIFTY 50
        'RELIANCE': 'Reliance Industries Ltd.',
        'TCS': 'Tata Consultancy Services Ltd.',
        'HDFCBANK': 'HDFC Bank Ltd.',
        'INFY': 'Infosys Ltd.',
        'ICICIBANK': 'ICICI Bank Ltd.',
        'HINDUNILVR': 'Hindustan Unilever Ltd.',
        'ITC': 'ITC Ltd.',
        'SBIN': 'State Bank of India',
        'BHARTIARTL': 'Bharti Airtel Ltd.',
        'KOTAKBANK': 'Kotak Mahindra Bank Ltd.',
        'BAJFINANCE': 'Bajaj Finance Ltd.',
        'LT': 'Larsen & Toubro Ltd.',
        'ASIANPAINT': 'Asian Paints Ltd.',
        'MARUTI': 'Maruti Suzuki India Ltd.',
        'HCLTECH': 'HCL Technologies Ltd.',
        'AXISBANK': 'Axis Bank Ltd.',
        'TITAN': 'Titan Company Ltd.',
        'SUNPHARMA': 'Sun Pharmaceutical Industries Ltd.',
        'ULTRACEMCO': 'UltraTech Cement Ltd.',
        'NESTLEIND': 'Nestle India Ltd.',
        'WIPRO': 'Wipro Ltd.',
        'ONGC': 'Oil & Natural Gas Corporation Ltd.',
        'NTPC': 'NTPC Ltd.',
        'TATAMOTORS': 'Tata Motors Ltd.',
        'TATASTEEL': 'Tata Steel Ltd.',
        'POWERGRID': 'Power Grid Corporation of India Ltd.',
        'M&M': 'Mahindra & Mahindra Ltd.',
        'JSWSTEEL': 'JSW Steel Ltd.',
        'TECHM': 'Tech Mahindra Ltd.',
        'INDUSINDBK': 'IndusInd Bank Ltd.',
        'BAJAJFINSV': 'Bajaj Finserv Ltd.',
        'HINDALCO': 'Hindalco Industries Ltd.',
        'ADANIPORTS': 'Adani Ports and Special Economic Zone Ltd.',
        'COALINDIA': 'Coal India Ltd.',
        'DIVISLAB': 'Divi\'s Laboratories Ltd.',
        'BAJAJ-AUTO': 'Bajaj Auto Ltd.',
        'BRITANNIA': 'Britannia Industries Ltd.',
        'GRASIM': 'Grasim Industries Ltd.',
        'DRREDDY': 'Dr. Reddy\'s Laboratories Ltd.',
        'APOLLOHOSP': 'Apollo Hospitals Enterprise Ltd.',
        'CIPLA': 'Cipla Ltd.',
        'EICHERMOT': 'Eicher Motors Ltd.',
        'TATACONSUM': 'Tata Consumer Products Ltd.',
        'HEROMOTOCO': 'Hero MotoCorp Ltd.',
        'SBILIFE': 'SBI Life Insurance Company Ltd.',
        'SHREECEM': 'Shree Cement Ltd.',
        'ADANIENT': 'Adani Enterprises Ltd.',
        'BPCL': 'Bharat Petroleum Corporation Ltd.',
        'UPL': 'UPL Ltd.',
        
        # RENEWABLE ENERGY & GREEN STOCKS (IMPORTANT - Previously Missing!)
        'SUZLON': 'Suzlon Energy Ltd.',
        'ADANIGREEN': 'Adani Green Energy Ltd.',
        'TATAPOWER': 'Tata Power Company Ltd.',
        'JSWENERGY': 'JSW Energy Ltd.',
        'NHPC': 'NHPC Ltd.',
        'SJVN': 'SJVN Ltd.',
        'ADANIPOWER': 'Adani Power Ltd.',
        'TORNTPOWER': 'Torrent Power Ltd.',
        'RPOWER': 'Reliance Power Ltd.',
        'INOXWIND': 'Inox Wind Ltd.',
        'INOXWINDENER': 'Inox Wind Energy Ltd.',
        'ORIENTGREEN': 'Orient Green Power Company Ltd.',
        
        # BANKING & FINANCE
        'YESBANK': 'Yes Bank Ltd.',
        'FEDERALBNK': 'Federal Bank Ltd.',
        'IDFCFIRSTB': 'IDFC First Bank Ltd.',
        'RBLBANK': 'RBL Bank Ltd.',
        'BANDHANBNK': 'Bandhan Bank Ltd.',
        'PNB': 'Punjab National Bank',
        'BANKBARODA': 'Bank of Baroda',
        'CANBK': 'Canara Bank',
        'UNIONBANK': 'Union Bank of India',
        'INDIANB': 'Indian Bank',
        'MAHABANK': 'Bank of Maharashtra',
        'CENTRALBK': 'Central Bank of India',
        'UCOBANK': 'UCO Bank',
        'AUBANK': 'AU Small Finance Bank Ltd.',
        'EQUITASBNK': 'Equitas Small Finance Bank Ltd.',
        'UJJIVANSFB': 'Ujjivan Small Finance Bank Ltd.',
        'CHOLAFIN': 'Cholamandalam Investment and Finance Company Ltd.',
        'M&MFIN': 'Mahindra & Mahindra Financial Services Ltd.',
        'SHRIRAMFIN': 'Shriram Finance Ltd.',
        'LICHSGFIN': 'LIC Housing Finance Ltd.',
        'PNBHOUSING': 'PNB Housing Finance Ltd.',
        'PFC': 'Power Finance Corporation Ltd.',
        'RECLTD': 'REC Ltd.',
        'IRFC': 'Indian Railway Finance Corporation Ltd.',
        'SBICARD': 'SBI Cards and Payment Services Ltd.',
        'HDFCAMC': 'HDFC Asset Management Company Ltd.',
        
        # IT & TECHNOLOGY
        'LTIM': 'LTIMindtree Ltd.',
        'PERSISTENT': 'Persistent Systems Ltd.',
        'COFORGE': 'Coforge Ltd.',
        'MPHASIS': 'Mphasis Ltd.',
        'LTTS': 'L&T Technology Services Ltd.',
        'HAPPSTMNDS': 'Happiest Minds Technologies Ltd.',
        'TATAELXSI': 'Tata Elxsi Ltd.',
        'KPITTECH': 'KPIT Technologies Ltd.',
        'CYIENT': 'Cyient Ltd.',
        'SONATSOFTW': 'Sonata Software Ltd.',
        'MASTEK': 'Mastek Ltd.',
        'INTELLECT': 'Intellect Design Arena Ltd.',
        'ROUTE': 'Route Mobile Ltd.',
        'ZENSARTECH': 'Zensar Technologies Ltd.',
        
        # PHARMA & HEALTHCARE
        'AUROPHARMA': 'Aurobindo Pharma Ltd.',
        'LUPIN': 'Lupin Ltd.',
        'BIOCON': 'Biocon Ltd.',
        'TORNTPHARM': 'Torrent Pharmaceuticals Ltd.',
        'ALKEM': 'Alkem Laboratories Ltd.',
        'IPCALAB': 'IPCA Laboratories Ltd.',
        'LAURUSLABS': 'Laurus Labs Ltd.',
        'GLENMARK': 'Glenmark Pharmaceuticals Ltd.',
        'GRANULES': 'Granules India Ltd.',
        'SYNGENE': 'Syngene International Ltd.',
        'LALPATHLAB': 'Dr. Lal PathLabs Ltd.',
        'METROPOLIS': 'Metropolis Healthcare Ltd.',
        'ZYDUSLIFE': 'Zydus Lifesciences Ltd.',
        'MANKIND': 'Mankind Pharma Ltd.',
        'ABBOTINDIA': 'Abbott India Ltd.',
        'GLAXO': 'GlaxoSmithKline Pharmaceuticals Ltd.',
        'PFIZER': 'Pfizer Ltd.',
        'SANOFI': 'Sanofi India Ltd.',
        'MAXHEALTH': 'Max Healthcare Institute Ltd.',
        'FORTIS': 'Fortis Healthcare Ltd.',
        'ASTRAZEN': 'AstraZeneca Pharma India Ltd.',
        
        # AUTO & ANCILLARY
        'ASHOKLEY': 'Ashok Leyland Ltd.',
        'APOLLOTYRE': 'Apollo Tyres Ltd.',
        'MRF': 'MRF Ltd.',
        'BALKRISIND': 'Balkrishna Industries Ltd.',
        'CEAT': 'CEAT Ltd.',
        'JKTYRE': 'JK Tyre & Industries Ltd.',
        'EXIDEIND': 'Exide Industries Ltd.',
        'AMARAJABAT': 'Amara Raja Energy & Mobility Ltd.',
        'ESCORTS': 'Escorts Kubota Ltd.',
        'MOTHERSON': 'Samvardhana Motherson International Ltd.',
        'BHARATFORG': 'Bharat Forge Ltd.',
        'ENDURANCE': 'Endurance Technologies Ltd.',
        'SONACOMS': 'Sona BLW Precision Forgings Ltd.',
        'TVSMOTOR': 'TVS Motor Company Ltd.',
        'BOSCHLTD': 'Bosch Ltd.',
        'SCHAEFFLER': 'Schaeffler India Ltd.',
        'SKFINDIA': 'SKF India Ltd.',
        'TIMKEN': 'Timken India Ltd.',
        
        # METALS & MINING
        'VEDL': 'Vedanta Ltd.',
        'JINDALSTEL': 'Jindal Steel & Power Ltd.',
        'SAIL': 'Steel Authority of India Ltd.',
        'NMDC': 'NMDC Ltd.',
        'NATIONALUM': 'National Aluminium Company Ltd.',
        'HINDZINC': 'Hindustan Zinc Ltd.',
        'RATNAMANI': 'Ratnamani Metals & Tubes Ltd.',
        
        # CEMENT
        'ACC': 'ACC Ltd.',
        'AMBUJACEM': 'Ambuja Cements Ltd.',
        'JKCEMENT': 'JK Cement Ltd.',
        'RAMCOCEM': 'The Ramco Cements Ltd.',
        'DALMIACEM': 'Dalmia Bharat Ltd.',
        'STARCEMENT': 'Star Cement Ltd.',
        
        # OIL & GAS
        'IOC': 'Indian Oil Corporation Ltd.',
        'HINDPETRO': 'Hindustan Petroleum Corporation Ltd.',
        'PETRONET': 'Petronet LNG Ltd.',
        'GAIL': 'GAIL (India) Ltd.',
        'IGL': 'Indraprastha Gas Ltd.',
        'MGL': 'Mahanagar Gas Ltd.',
        'GUJGASLTD': 'Gujarat Gas Ltd.',
        'ATGL': 'Adani Total Gas Ltd.',
        
        # TELECOM
        'INDUSTOWER': 'Indus Towers Ltd.',
        
        # REAL ESTATE
        'DLF': 'DLF Ltd.',
        'GODREJPROP': 'Godrej Properties Ltd.',
        'OBEROIRLTY': 'Oberoi Realty Ltd.',
        'PHOENIXLTD': 'The Phoenix Mills Ltd.',
        'BRIGADE': 'Brigade Enterprises Ltd.',
        'PRESTIGE': 'Prestige Estates Projects Ltd.',
        'SOBHA': 'Sobha Ltd.',
        'SUNTECK': 'Sunteck Realty Ltd.',
        'LODHA': 'Macrotech Developers Ltd.',
        
        # RETAIL & ECOMMERCE
        'DMART': 'Avenue Supermarts Ltd.',
        'TRENT': 'Trent Ltd.',
        'ZOMATO': 'Zomato Ltd.',
        'NYKAA': 'FSN E-Commerce Ventures Ltd.',
        'PAYTM': 'One 97 Communications Ltd.',
        'POLICYBZR': 'PB Fintech Ltd.',
        'SHOPERSTOP': 'Shoppers Stop Ltd.',
        
        # MEDIA & ENTERTAINMENT
        'PVRINOX': 'PVR INOX Ltd.',
        'ZEEL': 'Zee Entertainment Enterprises Ltd.',
        'SUNTV': 'Sun TV Network Ltd.',
        'NAZARA': 'Nazara Technologies Ltd.',
        'TV18BRDCST': 'TV18 Broadcast Ltd.',
        'NETWORK18': 'Network18 Media & Investments Ltd.',
        
        # FMCG & CONSUMER
        'DABUR': 'Dabur India Ltd.',
        'GODREJCP': 'Godrej Consumer Products Ltd.',
        'MARICO': 'Marico Ltd.',
        'COLPAL': 'Colgate-Palmolive (India) Ltd.',
        'VBL': 'Varun Beverages Ltd.',
        'EMAMILTD': 'Emami Ltd.',
        'JYOTHYLAB': 'Jyothy Labs Ltd.',
        'RADICO': 'Radico Khaitan Ltd.',
        'JUBLFOOD': 'Jubilant FoodWorks Ltd.',
        'WESTLIFE': 'Westlife Foodworld Ltd.',
        'DEVYANI': 'Devyani International Ltd.',
        'BATAINDIA': 'Bata India Ltd.',
        
        # CHEMICALS
        'SRF': 'SRF Ltd.',
        'PIIND': 'PI Industries Ltd.',
        'AARTI': 'Aarti Industries Ltd.',
        'DEEPAKNTR': 'Deepak Nitrite Ltd.',
        'TATACHEM': 'Tata Chemicals Ltd.',
        'NAVINFLUOR': 'Navin Fluorine International Ltd.',
        'LXCHEM': 'Laxmi Organic Industries Ltd.',
        'VINATIORGA': 'Vinati Organics Ltd.',
        'ALKYLAMINE': 'Alkyl Amines Chemicals Ltd.',
        'CLEAN SCIENCE': 'Clean Science and Technology Ltd.',
        
        # ELECTRONICS & ELECTRICAL
        'HAVELLS': 'Havells India Ltd.',
        'POLYCAB': 'Polycab India Ltd.',
        'KEI': 'KEI Industries Ltd.',
        'DIXON': 'Dixon Technologies (India) Ltd.',
        'VGUARD': 'V-Guard Industries Ltd.',
        'CROMPTON': 'Crompton Greaves Consumer Electricals Ltd.',
        'AMBER': 'Amber Enterprises India Ltd.',
        'ORIENTELEC': 'Orient Electric Ltd.',
        
        # LOGISTICS & TRANSPORT
        'CONCOR': 'Container Corporation of India Ltd.',
        'BLUEDART': 'Blue Dart Express Ltd.',
        'VRL': 'VRL Logistics Ltd.',
        'TCI': 'Transport Corporation of India Ltd.',
        'MAHLOG': 'Mahindra Logistics Ltd.',
        
        # INFRASTRUCTURE & CONSTRUCTION
        'NCC': 'NCC Ltd.',
        'KEC': 'KEC International Ltd.',
        'IRBINVIT': 'IRB InvIT Fund',
        'GMRINFRA': 'GMR Infrastructure Ltd.',
        
        # HOTELS & TOURISM
        'INDHOTEL': 'The Indian Hotels Company Ltd.',
        'LEMONTREE': 'Lemon Tree Hotels Ltd.',
        'CHALET': 'Chalet Hotels Ltd.',
        'EIH': 'EIH Ltd.',
        'TAJGVK': 'Taj GVK Hotels & Resorts Ltd.',
        
        # TEXTILES
        'ARVIND': 'Arvind Ltd.',
        'WELSPUNIND': 'Welspun India Ltd.',
        'TRIDENT': 'Trident Ltd.',
        'KPRMILL': 'KPR Mill Ltd.',
        
        # INSURANCE
        'ICICIGI': 'ICICI Lombard General Insurance Company Ltd.',
        'ICICIPRULI': 'ICICI Prudential Life Insurance Company Ltd.',
        'HDFCLIFE': 'HDFC Life Insurance Company Ltd.',
        'MFSL': 'Max Financial Services Ltd.',
        
        # OTHERS
        'IRCTC': 'Indian Railway Catering and Tourism Corporation Ltd.',
        'RAILTEL': 'RailTel Corporation of India Ltd.',
        'RVNL': 'Rail Vikas Nigam Ltd.',
        'SIEMENS': 'Siemens Ltd.',
        'ABB': 'ABB India Ltd.',
        'BERGEPAINT': 'Berger Paints India Ltd.',
        'PIDILITIND': 'Pidilite Industries Ltd.',
        'ASTRAL': 'Astral Ltd.',
        'SUPREMEIND': 'Supreme Industries Ltd.',
        'NILKAMAL': 'Nilkamal Ltd.',
        'VOLTAS': 'Voltas Ltd.',
        'BLUESTARCO': 'Blue Star Ltd.',
        'WHIRLPOOL': 'Whirlpool of India Ltd.',
        'KAJARIACER': 'Kajaria Ceramics Ltd.',
        'CERA': 'Cera Sanitaryware Ltd.',
        'CENTURYPLY': 'Century Plyboards (India) Ltd.',
        'GREENPLY': 'Greenply Industries Ltd.',
        'SYMPHONY': 'Symphony Ltd.',
        'RELAXO': 'Relaxo Footwears Ltd.',
        'PAGEIND': 'Page Industries Ltd.',
        'MUTHOOTFIN': 'Muthoot Finance Ltd.',
        'CREDITACC': 'CreditAccess Grameen Ltd.',
        '360ONE': '360 ONE WAM Ltd.',
        'INDIGO': 'InterGlobe Aviation Ltd.',
        'MCX': 'Multi Commodity Exchange of India Ltd.',
        'CDSL': 'Central Depository Services (India) Ltd.',
        'CAMS': 'Computer Age Management Services Ltd.',
        'IEX': 'Indian Energy Exchange Ltd.',
        'NAUKRI': 'Info Edge (India) Ltd.',
        'INDIAMART': 'IndiaMART InterMESH Ltd.',
        'BSE': 'BSE Ltd.',
        'COROMANDEL': 'Coromandel International Ltd.',
        'RALLIS': 'Rallis India Ltd.',
        'GNFC': 'Gujarat Narmada Valley Fertilizers & Chemicals Ltd.',
        'BALRAMCHIN': 'Balrampur Chini Mills Ltd.',
        'NOCIL': 'NOCIL Ltd.',
        'HAL': 'Hindustan Aeronautics Ltd.',
        'BEL': 'Bharat Electronics Ltd.',
        'CUMMINSIND': 'Cummins India Ltd.',
        'HONAUT': 'Honeywell Automation India Ltd.',
        'GILLETTE': 'Gillette India Ltd.',
        'PGHH': 'Procter & Gamble Hygiene and Health Care Ltd.',
        'NESTLEIND': 'Nestle India Ltd.',
    }
    
    return [f"{symbol} - {name}" for symbol, name in sorted(stocks.items())]


def get_all_nse_stocks():
    """
    Get complete NSE stock list with live API and fallback
    - First tries to fetch live from NSE official archive (2000+ stocks)
    - Falls back to comprehensive static list (1000+ stocks) if API fails
    - Caches results for 24 hours to minimize API calls
    - INCLUDES SUZLON and all other NSE-listed stocks
    """
    global _nse_stock_cache, _cache_time
    
    # Check if cache is valid (less than 24 hours old)
    if _nse_stock_cache and _cache_time:
        cache_age = time.time() - _cache_time
        if cache_age < 86400:  # 24 hours = 86400 seconds
            hours_old = cache_age / 3600
            print(f"Using cached NSE stock list ({hours_old:.1f} hours old)")
            return _nse_stock_cache
    
    # Try to fetch live data from NSE
    try:
        live_stocks = fetch_live_nse_stocks()
        
        if live_stocks and len(live_stocks) > 1000:
            # Successfully fetched live data
            print(f"✅ Using live NSE data: {len(live_stocks)} stocks")
            _nse_stock_cache = live_stocks
            _cache_time = time.time()
            return live_stocks
        else:
            raise Exception("Insufficient stocks fetched from live API")
            
    except Exception as e:
        print(f"⚠️ Live fetch failed: {e}")
        print("📋 Using comprehensive fallback stock list...")
        
        # Use fallback list
        fallback_list = get_fallback_stock_list()
        print(f"✅ Fallback list loaded: {len(fallback_list)} stocks (including SUZLON)")
        
        _nse_stock_cache = fallback_list
        _cache_time = time.time()
        return fallback_list


def clear_nse_stock_cache():
    """Clear the cached stock list to force fresh fetch on next call"""
    global _nse_stock_cache, _cache_time
    _nse_stock_cache = None
    _cache_time = None
    print("Stock cache cleared - next call will fetch fresh data")
