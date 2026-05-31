import streamlit as st
import google.generativeai as genai
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import email.utils
import time
from streamlit_cookies_manager import EncryptedCookieManager

# --- 1. ตั้งค่าหน้าตาโปรแกรม (Theme & Layout) ---
st.set_page_config(page_title="AI Trading Pro Suite", layout="wide", initial_sidebar_state="expanded")

# 🌟 แก้ปัญหาปุ่ม Sidebar หาย โดยยกเลิกการซ่อน header ทั้งหมด 🌟
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #f0f6fc; }
    .main { background-color: #0e1117; }
    
    /* ซ่อนเฉพาะเมนู 3 จุดของ Streamlit ด้านขวาบน (ถ้าอยากให้ดูโปร) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* สไตล์กล่องข้อมูล Metric ให้ดูเป็น Card สวยๆ */
    [data-testid="stMetric"] { 
        background-color: #161b22; 
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid #30363d; 
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .smc-box { background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 15px; }
    .smc-title { color: #f9c74f; font-size: 1.1em; font-weight: bold; display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    .smc-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #30363d; font-size: 0.95em; }
    
    .ai-analysis-box { background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- ระบบจำ API Key และ Favorites (Cookies) ---
cookies = EncryptedCookieManager(prefix="aitradingpro", password="super_secret_trading_password_123")
if not cookies.ready():
    st.stop()

# --- ระบบจำสถานะหุ้นปัจจุบัน (Session State) ---
if 'active_ticker' not in st.session_state:
    st.session_state.active_ticker = "NVDA"

# --- 2. ฟังก์ชันตัวช่วยต่างๆ ---
def get_ai_model(api_key, selected_model):
    genai.configure(api_key=api_key.strip()) 
    return genai.GenerativeModel(selected_model)

def calculate_ta(df):
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    ema_up = gain.ewm(com=13, adjust=False).mean()
    ema_down = loss.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def get_stock_news(ticker):
    try:
        search_query = "Gold+prices+news" if "GC=F" in ticker else f"{ticker}+stock+news"
        url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        root = ET.fromstring(response.read())
        
        news_items = []
        now_utc = datetime.now(timezone.utc)
        seven_days_ago = now_utc - timedelta(days=7)
        tz_th = timezone(timedelta(hours=7))
        
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            pubDate_str = item.find('pubDate').text
            parsed_date = email.utils.parsedate_to_datetime(pubDate_str)
            if parsed_date >= seven_days_ago:
                local_time = parsed_date.astimezone(tz_th)
                news_items.append({'title': title, 'link': link, 'date': local_time.strftime('%d/%m/%Y %H:%M')})
            if len(news_items) >= 5: break
        return news_items
    except Exception:
        return []

# --- 3. แถบข้าง (Sidebar) สำหรับตั้งค่า ---
with st.sidebar:
    st.markdown("<h1>⚙️ Advanced Settings</h1>", unsafe_allow_html=True)
    
    saved_api_key = cookies.get("gemini_api_key", "")
    api_key = st.text_input("🔑 Gemini API Key", value=saved_api_key, type="password")
    if api_key and api_key != saved_api_key:
        cookies["gemini_api_key"] = api_key
        cookies.save()
        st.success("✅ บันทึก Key แล้ว!")
    
    st.markdown("---")
    st.subheader("🤖 เลือกโมเดล AI")
    ai_model_name = st.selectbox("เลือกรุ่นที่ต้องการใช้งาน:", 
        ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]
    )
    
    st.markdown("---")
    st.subheader("🎯 ค้นหาสินทรัพย์")
    
    # 🌟 ช่องพิมพ์ชื่อหุ้น คุมด้วย Session State 🌟
    search_input = st.text_input("พิมพ์ Ticker ที่ต้องการดู:", value=st.session_state.active_ticker).upper().strip()
    
    if search_input and search_input != st.session_state.active_ticker:
        st.session_state.active_ticker = search_input
        st.rerun()

    ticker = st.session_state.active_ticker
    
    # ดึงข้อมูลรายการโปรด
    fav_str = cookies.get("fav_tickers", "")
    fav_list = [x.strip() for x in fav_str.split(",") if x.strip()]
    
    if ticker in fav_list:
        if st.button(f"❌ ลบ {ticker} ออกจากรายการโปรด", use_container_width=True):
            fav_list.remove(ticker)
            cookies["fav_tickers"] = ",".join(fav_list)
            cookies.save()
            st.rerun()
    else:
        if st.button(f"⭐ เพิ่ม {ticker} ลงรายการโปรด", type="primary", use_container_width=True):
            fav_list.append(ticker)
            cookies["fav_tickers"] = ",".join(fav_list)
            cookies.save()
            st.rerun()
    
    st.markdown("---")
    st.subheader("⏱️ โหมดหน้าจอกราฟ")
    trade_mode = st.radio("เลือก Timeframe:", ["🔴 Live (กราฟ 1 นาที)", "⚡ Intraday (15 นาที)", "📅 Daily (รายวัน)"])
    
    st.markdown("---")
    auto_refresh = st.toggle("🔄 เปิด Auto-Refresh (ทุก 60 วิ)")

# 🌟 --- 4. Dashboard Cards (โชว์กรอบสี่เหลี่ยมหุ้นโปรด) --- 🌟
if fav_list:
    st.markdown("### ⭐ My Watchlist")
    # แบ่งการ์ดเป็นแถวๆ ละ 4 กล่อง เพื่อความสวยงาม
    num_cols = 4 
    for i in range(0, len(fav_list), num_cols):
        cols = st.columns(num_cols)
        for j, col in enumerate(cols):
            if i + j < len(fav_list):
                t = fav_list[i + j]
                with col:
                    try:
                        # ดึงข้อมูลเร็วๆ เพื่อโชว์บนการ์ด
                        tkr_data = yf.Ticker(t).history(period="2d", interval="1d", prepost=True)
                        if len(tkr_data) >= 2:
                            curr_price = tkr_data['Close'].iloc[-1]
                            prev_price = tkr_data['Close'].iloc[-2]
                            pct_change = ((curr_price - prev_price) / prev_price) * 100
                            
                            # โชว์ Metric สวยๆ
                            st.metric(label=t, value=f"${curr_price:,.2f}", delta=f"{pct_change:+.2f}%")
                            
                            # ปุ่มกดดูกราฟ
                            if st.button(f"📊 ดูกราฟ {t}", key=f"btn_{t}", use_container_width=True):
                                st.session_state.active_ticker = t
                                st.rerun()
                    except:
                        st.error(f"โหลด {t} ไม่ได้")
    st.markdown("---")

# --- 5. Main Dashboard (กราฟและ AI) ---
if "Live" in trade_mode:
    period_val, interval_val = "1d", "1m"
elif "Intraday" in trade_mode:
    period_val, interval_val = "5d", "15m"
else:
    period_val, interval_val = "6mo", "1d"

st.markdown(f"<h1 style='margin-top: -10px;'>🚀 {ticker} Intelligence Dashboard</h1>", unsafe_allow_html=True)

try:
    df = yf.Ticker(ticker).history(period=period_val, interval=interval_val, prepost=True)
    
    if not df.empty:
        df = calculate_ta(df)
        current_price = df['Close'].iloc[-1]
        
        tab1, tab2, tab3, tab4 = st.tabs(["📈 กราฟเทคนิค & สแกน", "💰 วางแผน DCA", "📰 ข่าว & ตลาด", "🏢 เจาะลึกพื้นฐานหุ้น (Pro)"])
        
        # ================= TAB 1: กราฟหลัก & AI Pro Panel =================
        with tab1:
            left_col, right_col = st.columns([2, 1])
            with left_col:
                if "Daily" in trade_mode: 
                    x_labels = df.index.strftime('%Y-%m-%d')
                else: 
                    x_labels = df.index.strftime('%H:%M')
                    
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                fig.add_trace(go.Candlestick(x=x_labels, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
                fig.add_trace(go.Line(x=x_labels, y=df['EMA20'], name='EMA20', line=dict(color='yellow', width=1)), row=1, col=1)
                fig.add_trace(go.Line(x=x_labels, y=df['EMA50'], name='EMA50', line=dict(color='cyan', width=1)), row=1, col=1)
                
                colors = ['red' if row['Open'] - row['Close'] >= 0 else 'green' for index, row in df.iterrows()]
                fig.add_trace(go.Bar(x=x_labels, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                
                fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=10, b=0), xaxis_type='category', xaxis_nticks=10)
                fig.update_xaxes(type='category', nticks=10, row=2, col=1)
                st.plotly_chart(fig, use_container_width=True)
                
            with right_col:
                st.markdown("<h3 style='margin-bottom: 10px;'>🤖 AI Advanced Analysis</h3>", unsafe_allow_html=True)
                
                if st.button(f"⚡ วิเคราะห์โครงสร้าง {ticker} ของจริง", use_container_width=True):
                    if not api_key: st.error("กรุณาใส่ API Key ด้านซ้ายก่อนครับ")
                    else:
                        with st.spinner(f"กำลังวิเคราะห์..."):
                            try:
                                model = get_ai_model(api_key, ai_model_name)
                                data_str = df[['Close', 'Volume', 'EMA20', 'EMA50', 'RSI']].tail(15).to_string()
                                prompt = f"""วิเคราะห์ทางเทคนิค 15 แท่งล่าสุดของ {ticker}. ราคาปัจจุบัน {current_price:.2f}. ข้อมูล: {data_str}
                                ตอบกลับตามฟอร์แมตเป๊ะๆ:
                                TREND: [Bullish หรือ Bearish หรือ Neutral]
                                ZONE: [Premium หรือ Discount หรือ Equilibrium]
                                SIGNAL: [BUY หรือ SELL หรือ WAIT]
                                CONF: [ความมั่นใจ 0-100]
                                ENTRY: [ราคาเข้า]
                                SL: [ราคาตัดขาดทุน]
                                TP: [ราคาทำกำไร]
                                REASON: [เหตุผล 2 บรรทัด]"""
                                
                                response = model.generate_content(prompt)
                                res_text = response.text
                                parsed_data = {"TREND": "-", "ZONE": "-", "SIGNAL": "-", "CONF": "-", "ENTRY": "-", "SL": "-", "TP": "-", "REASON": res_text}
                                for line in res_text.strip().split('\n'):
                                    if ":" in line:
                                        key, val = line.split(":", 1)
                                        parsed_data[key.strip().upper()] = val.strip()

                                sig = parsed_data.get("SIGNAL", "WAIT").upper()
                                if "BUY" in sig:
                                    s_color, s_bg, s_icon = "#15f1ac", "#0d2e23", "🟢 BUY"
                                elif "SELL" in sig:
                                    s_color, s_bg, s_icon = "#fe5d72", "#311116", "🔴 SELL"
                                else:
                                    s_color, s_bg, s_icon = "#f9c74f", "#332b00", "🟡 WAIT"

                                real_smc_html = f"""
                                <div class='smc-box'>
                                    <div class='smc-title'>⚙️ Market Structure: {ticker}</div>
                                    <div class='smc-row'>Trend: <span style='color: {s_color}'>{parsed_data.get('TREND', '-')}</span></div>
                                    <div class='smc-row'>Zone: <span>{parsed_data.get('ZONE', '-')}</span></div>
                                    <div class='smc-row'>RSI: <span>{df['RSI'].iloc[-1]:.1f}</span></div>
                                </div>
                                <div class='ai-analysis-box'>
                                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
                                        <div style='color: {s_color}; font-weight: bold; border: 2px solid {s_color}; padding: 5px 15px; border-radius: 20px; font-size: 1.2em;'>{s_icon} {ticker}</div>
                                        <div style='background-color: {s_bg}; color: {s_color}; padding: 5px 15px; border-radius: 20px; font-weight: bold;'>{parsed_data.get('CONF', '50')}% Confidence</div>
                                    </div>
                                    <div style='font-size: 0.9em; line-height: 1.8; color: #f0f6fc; margin-bottom: 15px;'>
                                        <b>Entry Target:</b> {parsed_data.get('ENTRY', '-')}<br/>
                                        <b style='color: #fe5d72'>Stop Loss:</b> {parsed_data.get('SL', '-')}<br/>
                                        <b style='color: #15f1ac'>Take Profit:</b> {parsed_data.get('TP', '-')}
                                    </div>
                                    <p style='color: #a0a0a0; font-size: 0.85em;'>{parsed_data.get('REASON', '-')}</p>
                                </div>
                                """
                                st.markdown(real_smc_html, unsafe_allow_html=True)
                            except Exception as e:
                                st.error("ติดปัญหาโควต้า API รอสักครู่แล้วกดใหม่ครับ")
                else:
                    st.info("👈 กดปุ่มด้านบนเพื่อให้ AI วิเคราะห์กราฟแบบ Real-time ครับ")

        # ================= TAB 2: วางแผน DCA =================
        with tab2:
            st.subheader("🗓️ เครื่องมือวางแผน DCA รายเดือน")
            dca_budget = st.number_input("งบประมาณ DCA ต่อเดือน (USD $)", min_value=10, value=500, step=50)
            if st.button("🤖 ให้ AI ช่วยวางแผนแบ่งไม้ DCA"):
                st.info("กำลังเรียก AI...") # ตัดโค้ดเพื่อความกระชับ สามารถก๊อปตัวเต็มเดิมมาวางทับส่วนนี้ได้

        # ================= TAB 3: ข่าว =================
        with tab3:
            st.subheader("📰 ข่าวสารล่าสุด")
            news_list = get_stock_news(ticker)
            for n in news_list: st.markdown(f"🗓️ **{n['date']}** | 🔗 **[{n['title']}]({n['link']})**")

        # ================= TAB 4: พื้นฐาน =================
        with tab4:
            st.markdown(f"<h2>🏢 เจาะลึกพื้นฐานธุรกิจ: {ticker}</h2>", unsafe_allow_html=True)
            if st.button(f"🔍 สั่ง AI เจาะลึกพื้นฐาน {ticker} (Pro Mode)", type="primary"):
                st.info("กำลังเรียก AI วิเคราะห์พื้นฐาน 12 ข้อ...") # ตัดโค้ดเพื่อความกระชับ สามารถก๊อปตัวเต็มเดิมมาวางทับส่วนนี้ได้

    else:
        st.warning("ไม่พบข้อมูลสินทรัพย์")
except Exception as e:
    st.error(f"ระบบขัดข้อง: {e}")

if auto_refresh:
    time.sleep(60) 
    st.rerun()
