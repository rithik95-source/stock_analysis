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

def fetch_mcx_two_days():
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
    """Get intraday trading recommendations from Investing.com and TradingView"""
    intraday_picks = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Source 1: Screener.in - Top gainers/losers (intraday momentum)
    try:
        url = "https://www.screener.in/api/screens/top-gainers/?sort=-pChange&order=desc&page=1"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])[:5]
            
            for stock in results:
                symbol = f"{stock.get('short_name', '')}.NS"
                try:
                    ticker = yf.Ticker(symbol)
                    cmp = ticker.fast_info.get('lastPrice', 0)
                    
                    if cmp > 0:
                        # Intraday target: 2-3% above current price
                        intraday_target = cmp * 1.025
                        stop_loss = cmp * 0.985  # 1.5% stop loss
                        
                        intraday_picks.append({
                            "Stock": stock.get('name', 'Unknown'),
                            "Symbol": symbol,
                            "CMP": round(cmp, 2),
                            "Target": round(intraday_target, 2),
                            "Stop Loss": round(stop_loss, 2),
                            "Upside %": 2.5,
                            "Type": "Momentum",
                            "Timeframe": "Intraday",
                            "Date": datetime.now().strftime('%Y-%m-%d %H:%M')
                        })
                except:
                    continue
    except Exception as e:
        print(f"Screener.in error: {e}")
    
    # Source 2: NSE India - Most Active Stocks (volume leaders)
    try:
        nse_url = "https://www.nseindia.com/api/live-analysis-variations?index=gainers"
        nse_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=nse_headers, timeout=10)
        
        response = session.get(nse_url, headers=nse_headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            stocks = data.get('NIFTY', [])[:3]
            
            for stock in stocks:
                symbol_nse = stock.get('symbol', '')
                symbol = f"{symbol_nse}.NS"
                
                try:
                    ticker = yf.Ticker(symbol)
                    cmp = ticker.fast_info.get('lastPrice', 0)
                    
                    if cmp > 0:
                        pct_change = stock.get('pChange', 2.0)
                        intraday_target = cmp * (1 + (pct_change / 100) * 0.5)
                        stop_loss = cmp * 0.98
                        
                        intraday_picks.append({
                            "Stock": stock.get('meta', {}).get('companyName', symbol_nse),
                            "Symbol": symbol,
                            "CMP": round(cmp, 2),
                            "Target": round(intraday_target, 2),
                            "Stop Loss": round(stop_loss, 2),
                            "Upside %": round((intraday_target - cmp) / cmp * 100, 2),
                            "Type": "Gainer",
                            "Timeframe": "Intraday",
                            "Date": datetime.now().strftime('%Y-%m-%d %H:%M')
                        })
                except:
                    continue
    except Exception as e:
        print(f"NSE India error: {e}")
    
    # Fallback: Use technical indicators on popular stocks
    if len(intraday_picks) < 3:
        popular_stocks = [
            ("RELIANCE.NS", "Reliance"),
            ("TCS.NS", "TCS"),
            ("INFY.NS", "Infosys"),
            ("HDFCBANK.NS", "HDFC Bank"),
            ("ICICIBANK.NS", "ICICI Bank")
        ]
        
        for symbol, name in popular_stocks[:3]:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d", interval="5m")
                
                if not hist.empty:
                    cmp = hist['Close'].iloc[-1]
                    # Simple momentum: if trending up in last hour
                    recent = hist.tail(12)  # Last hour (12 x 5min)
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
    
    if intraday_picks:
        df = pd.DataFrame(intraday_picks)
        return df.drop_duplicates(subset=['Stock'], keep='first').head(6)
    
    return pd.DataFrame()

def get_longterm_recommendations():
    """Get long-term (swing/positional) recommendations from analysts"""
    longterm_picks = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # Source 1: Economic Times Stock Recommendations RSS
    try:
        et_reco_rss = "https://economictimes.indiatimes.com/markets/stocks/recos/rssfeeds/1977021501.cms"
        feed = feedparser.parse(et_reco_rss)
        
        for entry in feed.entries[:8]:
            title = entry.title
            
            # Parse: "Stock Name: Buy/Sell, Target Rs XX"
            stock_match = re.search(r'^([^:]+?)(?:\s*-|\s*:)', title)
            action_match = re.search(r'\b(Buy|Accumulate|Hold)\b', title, re.IGNORECASE)
            target_match = re.search(r'(?:target|tgt|price target).*?Rs\.?\s*([\d,]+)', title, re.IGNORECASE)
            
            if stock_match and action_match:
                stock_name = stock_match.group(1).strip()
                action = action_match.group(1).upper()
                
                if action in ["BUY", "ACCUMULATE"]:
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
                                    target = cmp * 1.15  # Assume 15% target if not specified
                                
                                upside = ((target - cmp) / cmp) * 100
                                stop_loss = cmp * 0.92  # 8% stop loss for swing
                                
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
    except Exception as e:
        print(f"ET RSS error: {e}")
    
    # Source 2: Moneycontrol Stock Ideas
    try:
        mc_url = "https://www.moneycontrol.com/news/business/stocks/"
        response = requests.get(mc_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = soup.find_all('li', class_='clearfix')[:5]
            
            for article in articles:
                title_elem = article.find('h2')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    
                    # Look for buy recommendations
                    if any(word in title.lower() for word in ['buy', 'target', 'pick']):
                        # Extract stock name
                        stock_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+Ltd)?)\b', title)
                        if stock_match:
                            stock_name = stock_match.group(1)
                            symbol = get_nse_symbol(stock_name)
                            
                            if symbol:
                                try:
                                    ticker = yf.Ticker(symbol)
                                    cmp = ticker.fast_info.get('lastPrice', 0)
                                    
                                    if cmp > 0:
                                        # Conservative 12% target
                                        target = cmp * 1.12
                                        stop_loss = cmp * 0.93
                                        
                                        longterm_picks.append({
                                            "Stock": stock_name,
                                            "Symbol": symbol,
                                            "CMP": round(cmp, 2),
                                            "Target": round(target, 0),
                                            "Stop Loss": round(stop_loss, 2),
                                            "Upside %": 12.0,
                                            "Type": "Research",
                                            "Timeframe": "3-6 weeks",
                                            "Date": datetime.now().strftime('%Y-%m-%d'),
                                            "Source": "Moneycontrol"
                                        })
                                except:
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
    """Get market news from multiple RSS sources"""
    all_news = []
    
    # Source 1: Economic Times Stock Recommendations
    try:
        et_reco_rss = "https://economictimes.indiatimes.com/markets/stocks/recos/rssfeeds/1977021501.cms"
        feed = feedparser.parse(et_reco_rss)
        
        for entry in feed.entries[:6]:
            news_item = {
                'title': entry.title,
                'publisher': 'ET - Stock Picks',
                'link': entry.link,
                'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                'category': 'recommendation'
            }
            all_news.append(news_item)
    except Exception as e:
        print(f"ET Reco RSS error: {e}")
    
    # Source 2: Economic Times Market News
    try:
        et_market_rss = "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
        feed = feedparser.parse(et_market_rss)
        
        for entry in feed.entries[:6]:
            news_item = {
                'title': entry.title,
                'publisher': 'Economic Times',
                'link': entry.link,
                'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                'category': 'market'
            }
            all_news.append(news_item)
    except Exception as e:
        print(f"ET Market RSS error: {e}")
    
    # Source 3: Moneycontrol Market Reports
    try:
        mc_rss = "https://www.moneycontrol.com/rss/marketreports.xml"
        feed = feedparser.parse(mc_rss)
        
        for entry in feed.entries[:6]:
            news_item = {
                'title': entry.title,
                'publisher': 'Moneycontrol',
                'link': entry.link,
                'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                'category': 'market'
            }
            all_news.append(news_item)
    except Exception as e:
        print(f"Moneycontrol RSS error: {e}")
    
    # Source 4: Moneycontrol News
    try:
        mc_news_rss = "https://www.moneycontrol.com/rss/latestnews.xml"
        feed = feedparser.parse(mc_news_rss)
        
        for entry in feed.entries[:5]:
            if any(word in entry.title.lower() for word in ['stock', 'market', 'nifty', 'sensex', 'share']):
                news_item = {
                    'title': entry.title,
                    'publisher': 'Moneycontrol',
                    'link': entry.link,
                    'provider_publish_time': datetime(*entry.published_parsed[:6]).timestamp() if hasattr(entry, 'published_parsed') else datetime.now().timestamp(),
                    'category': 'market'
                }
                all_news.append(news_item)
    except Exception as e:
        print(f"Moneycontrol News RSS error: {e}")
    
    # Source 5: Yahoo Finance India
    try:
        for sym in ["^NSEI", "^BSESN"]:
            ticker = yf.Ticker(sym)
            news = ticker.news
            if news:
                for item in news[:3]:
                    if isinstance(item, dict) and 'title' in item:
                        item.setdefault('publisher', 'Yahoo Finance')
                        item.setdefault('link', '#')
                        if 'providerPublishTime' in item:
                            item['provider_publish_time'] = item['providerPublishTime']
                        else:
                            item['provider_publish_time'] = datetime.now().timestamp()
                        item['category'] = 'market'
                        all_news.append(item)
    except Exception as e:
        print(f"Yahoo Finance error: {e}")
    
    # Remove duplicates
    unique_news = []
    seen_titles = set()
    for item in all_news:
        if isinstance(item, dict) and 'title' in item:
            title_key = item['title'][:60].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(item)
    
    return unique_news[:20] if unique_news else [{
        'title': 'Market Dashboard - Loading News...',
        'publisher': 'System',
        'link': '#',
        'provider_publish_time': datetime.now().timestamp(),
        'category': 'market'
    }]
