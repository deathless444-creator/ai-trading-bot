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

# --- 1. ตั้งค่าหน้าตาโปรแกรม (Theme & Layout) ---
st.set_page_config(page_title="AI Trading Pro Max", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; text-align: center; }
    .ai-box { background-color: #1c2331; padding: 20px; border-radius: 10px; border-left: 5px solid #00f2fe; margin-top: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ฟังก์ชันตัวช่วยต่างๆ ---
@st.cache_resource # 🌟 เพิ่มบรรทัดนี้เพื่อให้เว็บจดจำ AI ไว้ จะได้ไม่เรียกซ้ำให้เปลืองโควต้า
def get_ai_model(api_key):
    genai.configure(api_key=api_key)
    # ลบระบบค้นหาอัตโนมัติทิ้ง แล้วล็อคชื่อรุ่นที่เร็วและเสถียรที่สุดไปเลย
    return genai.GenerativeModel("gemini-1.5-flash")

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

# 🌟 ฟังก์ชันดึงข่าว (อัปเกรด: แสดงวันที่ + กรอง 7 วันล่าสุด + ปรับเวลาท้องถิ่น)
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
        
        # ตั้งค่า Timezone เป็น +7 
        tz_th = timezone(timedelta(hours=7))
        
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            pubDate_str = item.find('pubDate').text
            
            # แปลงวันที่จาก Text เป็นข้อมูลเวลาที่คำนวณได้
            parsed_date = email.utils.parsedate_to_datetime(pubDate_str)
            
            # คัดกรองเฉพาะข่าวที่ใหม่กว่า 7 วัน
            if parsed_date >= seven_days_ago:
                # ปรับให้เป็นเวลา +7 และจัดฟอร์แมตให้อ่านง่าย
                local_time = parsed_date.astimezone(tz_th)
                display_date = local_time.strftime('%d/%m/%Y %H:%M')
                
                news_items.append({'title': title, 'link': link, 'date': display_date})
            
            # ดึงมาแค่ 5-6 ข่าวที่ตรงเงื่อนไขเพื่อไม่ให้รกลูกตา
            if len(news_items) >= 5:
                break
                
        return news_items
    except Exception as e:
        return []

# --- 3. แถบข้าง (Sidebar) สำหรับตั้งค่า ---
with st.sidebar:
    st.title("⚙️ ตั้งค่าระบบ")
    api_key = st.text_input("🔑 Gemini API Key", type="password")
    
    st.markdown("---")
    st.subheader("🎯 เลือกสินทรัพย์")
    quick_tickers = ["NVDA", "AVGO", "ONDS", "RKLB", "GC=F (ทองคำ)"]
    selected_quick = st.selectbox("รายการด่วน:", quick_tickers)
    default_ticker = selected_quick.split(" ")[0] 
    
    ticker = st.text_input("หรือพิมพ์ Ticker เอง:", value=default_ticker)
    
    st.markdown("---")
    st.subheader("⏱️ โหมดหน้าจอกราฟ")
    trade_mode = st.radio("เลือก Timeframe:", ["⚡ Intraday (15 นาที)", "📅 Daily (กราฟรายวัน)"])

if "Intraday" in trade_mode:
    period_val, interval_val = "5d", "15m"
    vol_compare_text = "เทียบแท่งต่อแท่ง (ทุกๆ 15 นาที)"
else:
    period_val, interval_val = "6mo", "1d"
    vol_compare_text = "เทียบวันต่อวัน (Daily)"

st.title(f"🚀 {ticker} Intelligence Dashboard")

try:
    raw_data = yf.Ticker(ticker)
    df = raw_data.history(period=period_val, interval=interval_val)
    
    if not df.empty:
        df = calculate_ta(df)
        current_price = df['Close'].iloc[-1]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("ราคาปัจจุบัน", f"${current_price:,.2f}")
        col2.metric("RSI (ความร้อนแรง)", f"{df['RSI'].iloc[-1]:.1f}")
        col3.metric("EMA 20 (เทรนด์สั้น)", f"${df['EMA20'].iloc[-1]:,.2f}")
        col4.metric("EMA 50 (เทรนด์กลาง)", f"${df['EMA50'].iloc[-1]:,.2f}")

        # --- 4. ระบบ Tab แยกหน้าการใช้งาน ---
        tab1, tab2, tab3 = st.tabs(["📈 กราฟเทคนิค & AI สแกน", "💰 วางแผน DCA รายเดือน", "📰 วิเคราะห์ข่าว & สภาพตลาด"])
        
        # ================= TAB 1: Technical Chart & Volume Analyze =================
        with tab1:
            if "Intraday" in trade_mode:
                x_labels = df.index.strftime('%Y-%m-%d %H:%M')
            else:
                x_labels = df.index.strftime('%Y-%m-%d')
                
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            fig.add_trace(go.Candlestick(x=x_labels, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
            fig.add_trace(go.Line(x=x_labels, y=df['EMA20'], name='EMA20', line=dict(color='yellow', width=1)), row=1, col=1)
            fig.add_trace(go.Line(x=x_labels, y=df['EMA50'], name='EMA50', line=dict(color='cyan', width=1)), row=1, col=1)
            
            colors = ['red' if row['Open'] - row['Close'] >= 0 else 'green' for index, row in df.iterrows()]
            fig.add_trace(go.Bar(x=x_labels, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
            
            fig.update_layout(
                height=500, 
                template="plotly_dark", 
                xaxis_rangeslider_visible=False, 
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis_type='category',
                xaxis_nticks=10
            )
            fig.update_xaxes(type='category', nticks=10, row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"### 📊 ตารางสรุปและเปรียบเทียบ Volume ย้อนหลัง ({vol_compare_text})")
            
            vol_df = pd.DataFrame(index=df.index)
            vol_df['ราคาปิด (Close)'] = df['Close'].round(2)
            vol_df['Volume ปัจจุบัน'] = df['Volume']
            vol_df['เปลี่ยนแปลง (DoD)'] = df['Volume'].diff()
            vol_df['% เปลี่ยนแปลง'] = (df['Volume'].pct_change() * 100).round(2)
            
            vol_show = vol_df.tail(5).sort_index(ascending=False)
            
            st.dataframe(
                vol_show,
                column_config={
                    "ราคาปิด (Close)": st.column_config.NumberColumn("ราคาปิด", format="$%,.2f"),
                    "Volume ปัจจุบัน": st.column_config.NumberColumn("ปริมาณการซื้อขาย (Volume)", format="%,d"),
                    "เปลี่ยนแปลง (DoD)": st.column_config.NumberColumn("เพิ่มขึ้น/ลดลง", format="%+,d"),
                    "% เปลี่ยนแปลง": st.column_config.NumberColumn("% เทียบแท่งก่อนหน้า", format="%+.2f%%"),
                },
                use_container_width=True
            )
            st.markdown("---")
            
            if st.button("⚡ สแกนกราฟด้วย AI (Technical Analysis)"):
                if not api_key: st.error("กรุณาใส่ API Key")
                else:
                    with st.spinner("กำลังวิเคราะห์อินดิเคเตอร์..."):
                        model = get_ai_model(api_key)
                        data_str = df[['Close', 'Volume', 'EMA20', 'RSI']].tail(15).to_string()
                        prompt = f"""
                        คุณคือนักเทรดกราฟเทคนิค วิเคราะห์ข้อมูล 15 แท่งล่าสุดของ {ticker}: {data_str}
                        ช่วยสรุป: 1. เทรนด์ปัจจุบัน 2. จุดเข้าซื้อ/ตัดขาดทุน 3. สภาพ Volume สั้นๆ ตรงประเด็น
                        """
                        st.markdown(f"<div class='ai-box'>{model.generate_content(prompt).text}</div>", unsafe_allow_html=True)

        # ================= TAB 2: DCA Planner =================
        with tab2:
            st.subheader("🗓️ เครื่องมือวางแผน DCA รายเดือน")
            dca_budget = st.number_input("งบประมาณ DCA ต่อเดือน (USD $)", min_value=10, value=500, step=50)
            shares_est = dca_budget / current_price
            
            st.info(f"💡 ด้วยงบ **${dca_budget}** คุณสามารถสะสม {ticker} ได้ประมาณ **{shares_est:.4f} หุ้น** ที่ราคาปัจจุบัน (${current_price:,.2f})")
            
            if st.button("🤖 ให้ AI ช่วยวางแผนแบ่งไม้ DCA"):
                if not api_key: st.error("กรุณาใส่ API Key")
                else:
                    with st.spinner("กำลังคำนวณแนวรับเพื่อแบ่งไม้ DCA..."):
                        model = get_ai_model(api_key)
                        data_str = df[['High', 'Low', 'Close']].tail(30).to_string()
                        prompt = f"""
                        ฉันต้องการ DCA หุ้น {ticker} เดือนนี้ด้วยงบ ${dca_budget} ราคาปัจจุบันคือ ${current_price}
                        นี่คือข้อมูลราคา 30 แท่งล่าสุด: {data_str}
                        
                        ในฐานะผู้เชี่ยวชาญการลงทุน ช่วยวางแผนแบ่งเงินซื้อสะสม (เช่น แบ่ง 2-3 ไม้ ตามแนวรับสำคัญ)
                        เพื่อลดความเสี่ยงและทำให้ได้ต้นทุนเฉลี่ยที่ดีที่สุด อธิบายเหตุผลสั้นๆ เข้าใจง่าย
                        """
                        st.markdown(f"<div class='ai-box'>{model.generate_content(prompt).text}</div>", unsafe_allow_html=True)

        # ================= TAB 3: News & Sentiment =================
        with tab3:
            st.subheader("📰 ข่าวสารล่าสุด & AI อ่านใจตลาด (กรอง 7 วันล่าสุด)")
            
            with st.spinner("กำลังสแกนหาข่าวสาร..."):
                news_list = get_stock_news(ticker)
                
            if news_list and len(news_list) > 0:
                valid_titles = []
                for n in news_list:
                    # แสดงไอคอนปฏิทิน พร้อมวันที่และเวลา
                    st.markdown(f"🗓️ **{n['date']}** | 🔗 **[{n['title']}]({n['link']})**")
                    valid_titles.append(n['title'])
                
                st.markdown("---")
                if st.button("🧠 ให้ AI วิเคราะห์ Sentiment จากข่าว"):
                    if not api_key: st.error("กรุณาใส่ API Key")
                    else:
                        with st.spinner("กำลังสรุปทิศทางข่าว..."):
                            model = get_ai_model(api_key)
                            prompt = f"ข่าวล่าสุดของตลาด {ticker} ในรอบสัปดาห์มีหัวข้อดังนี้: {valid_titles} \nข่าวเหล่านี้ส่งผลเชิงบวก (Bullish) หรือเชิงลบ (Bearish) ต่อทิศทางราคา? สรุปสั้นๆ เป็นข้อๆ"
                            st.markdown(f"<div class='ai-box'>{model.generate_content(prompt).text}</div>", unsafe_allow_html=True)
            else:
                st.info("ไม่มีข่าวสำคัญใหม่ๆ เกี่ยวกับสินทรัพย์นี้ในช่วง 7 วันที่ผ่านมาครับ")

    else:
        st.warning("ไม่พบข้อมูลสินทรัพย์")
except Exception as e:
    st.error(f"ระบบขัดข้อง: {e}")
