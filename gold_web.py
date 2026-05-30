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
from streamlit_cookies_manager import EncryptedCookieManager

# --- 1. ตั้งค่าหน้าตาโปรแกรม (Theme & Layout) และ Custom CSS สำหรับ UI Pro ---
st.set_page_config(page_title="AI Trading Pro Suite", layout="wide")

# สร้างสไตล์ CSS แบบกำหนดเองเพื่อสะท้อนแดชบอร์ดระดับโปร
st.markdown("""
    <style>
    /* บังคับธีมมืดและลบขอบส่วนเกิน */
    .stApp { background-color: #0e1117; color: #f0f6fc; }
    .main { background-color: #0e1117; }
    header { visibility: hidden; }
    
    /* สไตล์กล่องข้อมูลทั่วไป */
    div.stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; text-align: center; }
    div.stDataframe { border: 1px solid #30363d; border-radius: 10px; }
    
    /* สไตล์บานหน้าต่าง AI ทางด้านขวา (Inspired by images) */
    .smc-box { background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 15px; }
    .smc-title { color: #f9c74f; font-size: 1.1em; font-weight: bold; display: flex; align-items: center; gap: 8px; }
    .smc-row { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #30363d; font-size: 0.9em; }
    
    /* สไตล์กล่องแผนการซื้อขาย AI และ DCA Plan (Inspired by AI Analysis and Price Prediction) */
    .ai-analysis-box { background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d; margin-bottom: 15px; }
    .buy-signal { color: #15f1ac; font-weight: bold; border: 2px solid #15f1ac; padding: 5px 15px; border-radius: 20px; font-size: 1.2em; text-align: center;}
    .sell-signal { color: #fe5d72; font-weight: bold; border: 2px solid #fe5d72; padding: 5px 15px; border-radius: 20px; font-size: 1.2em; text-align: center;}
    
    /* สไตล์กล่องเหตุผล AI และ Sentiment ข่าว (Inspired by AI Reasoning) */
    .ai-reasoning-box { background-color: #1c2331; padding: 20px; border-radius: 10px; border-left: 5px solid #00f2fe; margin-bottom: 15px; }
    .reasoning-text { color: #f0f6fc; font-size: 0.95em; line-height: 1.6; }
    
    /* สไตล์ตารางคำทำนายเวลา (Inspired by OPTION TIME-SERIES FORECAST) */
    .forecast-table { background-color: #161b22; border-radius: 10px; border: 1px solid #30363d; width: 100%; font-size: 0.85em; margin-bottom: 15px;}
    .forecast-header { background-color: #1c2331; color: #f0f6fc; font-weight: bold; text-align: center;}
    .forecast-row { color: #f0f6fc; border-bottom: 1px solid #30363d; text-align: center;}
    .buy-badge { color: #15f1ac; background-color: #0d2e23; padding: 2px 8px; border-radius: 5px; font-weight: bold;}
    .sell-badge { color: #fe5d72; background-color: #311116; padding: 2px 8px; border-radius: 5px; font-weight: bold;}
    
    /* สไตล์กล่องเตือน (Warning Box) */
    .warning-box { background-color: #332b00; padding: 15px; border-radius: 10px; border-left: 5px solid #ffcc00; margin-top: 10px; color: #ffdd33;}
    </style>
    """, unsafe_allow_html=True)

# 🌟 --- ระบบจำ API Key แยกรายบุคคล (Cookies) --- 🌟
cookies = EncryptedCookieManager(prefix="aitradingpro", password="super_secret_trading_password_123")
if not cookies.ready():
    st.stop()

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
                display_date = local_time.strftime('%d/%m/%Y %H:%M')
                news_items.append({'title': title, 'link': link, 'date': display_date})
            
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
        st.success("✅ บันทึก Key ลงเครื่องนี้แล้ว!")
    
    st.markdown("---")
    st.subheader("🤖 เลือกโมเดล AI")
    ai_model_name = st.selectbox("เลือกรุ่นที่ต้องการใช้งาน:", 
        ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]
    )
    
    st.markdown("---")
    st.subheader("🎯 เลือกสินทรัพย์")
    ticker = st.text_input("Ticker เอง:", value="GC=F (ทองคำ)").split(" ")[0]
    
    st.markdown("---")
    st.subheader("⏱️ โหมดหน้าจอกราฟ")
    trade_mode = st.radio("เลือก Timeframe:", ["⚡ Intraday (15 นาที)", "📅 Daily (กราฟรายวัน)"])

if "Intraday" in trade_mode:
    period_val, interval_val = "5d", "15m"
    vol_compare_text = "เทียบแท่งต่อแท่ง (ทุกๆ 15 นาที)"
else:
    period_val, interval_val = "6mo", "1d"
    vol_compare_text = "เทียบวันต่อวัน (Daily)"

st.markdown(f"<h1>🚀 {ticker} Intelligence Dashboard</h1>", unsafe_allow_html=True)

try:
    raw_data = yf.Ticker(ticker)
    df = raw_data.history(period=period_val, interval=interval_val)
    
    if not df.empty:
        df = calculate_ta(df)
        current_price = df['Close'].iloc[-1]
        
        # --- ระบบ 2 คอลัมน์หลัก ---
        left_col, right_col = st.columns([2, 1])

        # ================= LEFT COLUMN: กราฟราคาหลัก & ข้อมูลพื้นฐาน =================
        with left_col:
            # องค์ประกอบเฉพาะเหนือกราฟ (Inspired by Price Prediction box)
            target_prediction_html = f"""
            <div style='background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #30363d; font-size: 0.8em; margin-bottom: 10px; display: flex; gap: 15px;'>
                <div><b>Target (AI Predict):</b> <span style='color: #15f1ac'>$4500</span></div>
                <div><b>Direction:</b> <span style='color: #15f1ac'>Bullish</span></div>
                <div><b>Confidence:</b> 30%</div>
                <div style='color: #fe5d72'>Risk Band: (3.54x)</div>
            </div>
            """
            st.markdown(target_prediction_html, unsafe_allow_html=True)

            # กราฟหลัก (เหมือนเดิม)
            if "Intraday" in trade_mode: x_labels = df.index.strftime('%Y-%m-%d %H:%M')
            else: x_labels = df.index.strftime('%Y-%m-%d')
                
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=x_labels, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Line(x=x_labels, y=df['EMA20'], name='EMA20', line=dict(color='yellow', width=1)), row=1, col=1)
            fig.add_trace(go.Line(x=x_labels, y=df['EMA50'], name='EMA50', line=dict(color='cyan', width=1)), row=1, col=1)
            
            colors = ['red' if row['Open'] - row['Close'] >= 0 else 'green' for index, row in df.iterrows()]
            fig.add_trace(go.Bar(x=x_labels, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
            
            fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0, r=0, t=10, b=0), xaxis_type='category', xaxis_nticks=10)
            fig.update_xaxes(type='category', nticks=10, row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"### 📊 ตาราง Volume ย้อนหลัง ({vol_compare_text})")
            vol_df = pd.DataFrame(index=df.index)
            vol_df['Volume ปัจจุบัน'] = df['Volume']
            vol_df['เปลี่ยนแปลง (DoD)'] = df['Volume'].diff()
            st.dataframe(vol_df.tail(5).sort_index(ascending=False), use_container_width=True)

        # ================= RIGHT COLUMN: AI Analysis Panel & ข่าวสาร =================
        with right_col:
            st.markdown("<h3 style='margin-bottom: 0px;'>🤖 AI Advanced Analysis</h3>", unsafe_allow_html=True)
            
            if st.button("🧠 กดเพื่อรับแผนการวิเคราะห์ (AI จะทำงานจริงที่นี่)"):
                st.info("💡 ตัวอย่าง UI นี้ใช้ข้อมูลจำลอง (DUMMY DATA) เพื่อแสดงหน้าตาแดชบอร์ดระดับโปรโดยไม่เปลือง API")
            
            # 🌟 1. SMC Overlay & Trendสรุป (Inspired by SMC Overlay) 🌟
            smc_html = """
            <div class='smc-box'>
                <div class='smc-title'><span style='color: #fe5d72'>🐻</span> Bearsih SMC Structure</div>
                <div class='smc-row'>Trend: <span>Bearish</span></div>
                <div class='smc-row'>MTF Confluence: <span>Bearish / Neutral</span></div>
                <div class='smc-row'>PD Zone: <span>Premium</span></div>
                <div class='smc-row'>Active FVG (GC=F): <span style='color: #15f1ac'>131</span> / <span style='color: #fe5d72'>570</span></div>
            </div>
            """
            st.markdown(smc_html, unsafe_allow_html=True)

            # 🌟 2. AI Analysis Plan (Inspired by AI Analysis Panel) 🌟
            ai_plan_html = """
            <div class='ai-analysis-box'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;'>
                    <div class='buy-signal'>🟢 BUY BTC</div>
                    <div style='background-color: #0d2e23; color: #15f1ac; padding: 5px 15px; border-radius: 20px; font-weight: bold;'>75% Confidence</div>
                </div>
                <div style='font-size: 0.9em; line-height: 1.8; color: #f0f6fc; margin-bottom: 15px;'>
                    <b>Entry:</b> 73,610<br/>
                    <b style='color: #fe5d72'>Stop Loss:</b> 73,408<br/>
                    <b style='color: #15f1ac'>Take Profit:</b> 74,200
                </div>
                <h4 style='color: #f9c74f; font-size: 1em; margin-bottom: 5px;'>🧠 AI Reasoning:</h4>
                <p style='color: #a0a0a0; font-size: 0.85em; line-height: 1.6;'>
                    การวิเคราะห์เชิงโครงสร้างตลาดแสดงให้เห็นว่า BTC อยู่ในโซนแนวรับที่แข็งแกร่ง (Strong Support Zone) AI มีความมั่นใจสูงในการเข้าซื้อสะสมเพื่อรอการฟื้นตัว
                </p>
            </div>
            """
            st.markdown(ai_plan_html, unsafe_allow_html=True)

            # 🌟 3. Option Time-Series Forecast (Inspired by OPTION TIME-SERIES FORECAST table) 🌟
            forecast_table_html = """
            <table class='forecast-table'>
                <tr class='forecast-header'>
                    <td>Timeframe</td> <td>Signal</td> <td>Probability</td>
                </tr>
                <tr class='forecast-row'>
                    <td>1m</td> <td><span class='buy-badge'>🟢 BUY</span></td> <td>71%</td>
                </tr>
                <tr class='forecast-row'>
                    <td>15m</td> <td><span class='buy-badge'>🟢 BUY</span></td> <td>75%</td>
                </tr>
                <tr class='forecast-row'>
                    <td>1h</td> <td><span class='sell-badge'>🔴 SELL</span></td> <td>67%</td>
                </tr>
                <tr class='forecast-row'>
                    <td>1d</td> <td><span class='buy-badge'>🟢 BUY</span></td> <td>61%</td>
                </tr>
            </table>
            """
            st.markdown(forecast_table_html, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 📰 ข่าวล่าสุด & Sentiment", unsafe_allow_html=True)
            news_list = get_stock_news(ticker)
            if news_list:
                for n in news_list:
                    st.markdown(f"🗓️ **{n['date']}** | 🔗 **[{n['title']}]({n['link']})**")
            else:
                st.info("ไม่มีข่าวสำคัญใหม่ๆ ในช่วง 7 วันที่ผ่านมาครับ")

    else:
        st.warning("ไม่พบข้อมูลสินทรัพย์")
except Exception as e:
    st.error(f"ระบบขัดข้อง: {e}")
