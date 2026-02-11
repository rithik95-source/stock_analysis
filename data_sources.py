import yfinance as yf
import pandas as pd
import requests
import io
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import feedparser
import re

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
                                    continue
    except Exception as e:
        print(f"Moneycontrol error: {e}")
    
    # Source 3: Yahoo Finance Analyst Recommendations
    try:
        top_stocks = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", 
                     "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS",
                     "WIPRO.NS", "AXISBANK.NS"]
        
        for symbol in top_stocks[:6]:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                cmp = ticker.fast_info.get('lastPrice', 0)
                
                # Get analyst target price
                target = info.get('targetMeanPrice', 0)
                recommendation = info.get('recommendationKey', 'hold')
                
                if cmp > 0 and target > 0 and recommendation in ['buy', 'strong_buy']:
                    upside = ((target - cmp) / cmp) * 100
                    
                    if upside > 5:  # Only show if upside > 5%
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
        print(f"Yahoo Finance error: {e}")
    
    if longterm_picks:
        df = pd.DataFrame(longterm_picks)
        # Remove duplicates, keep best upside
        df = df.sort_values('Upside %', ascending=False)
        df = df.drop_duplicates(subset=['Stock'], keep='first')
        return df.head(8)
    
    return pd.DataFrame()

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
