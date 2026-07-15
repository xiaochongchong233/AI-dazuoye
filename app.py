import streamlit as st
import requests
import os
import json
import re

# ==================== 配置 ====================
QIANWEN_API_KEY = os.getenv("QIANWEN_API_KEY")
OWM_API_KEY = os.getenv("OWM_API_KEY")          # OpenWeatherMap Key

QIANWEN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# ==================== 知识库 ====================
KNOWLEDGE = {
    "通勤": "商务休闲风，衬衫、西裤、便西、乐福鞋。",
    "运动": "速干材质，透气跑鞋，防晒帽。",
    "晚宴": "正式着装，西装皮鞋或晚礼服高跟鞋。",
    "上学": "舒适得体，卫衣、牛仔裤、运动鞋。",
    "居家": "居家棉质睡衣。"
}

# ==================== 天气获取 ====================
def get_weather(city):
    params = {"q": city, "appid": OWM_API_KEY, "units": "metric", "lang": "zh_cn"}
    try:
        resp = requests.get(WEATHER_URL, params=params, timeout=5)
        if resp.status_code == 200:
            return resp.json()
        else:
            err = resp.json().get("message", "未知错误")
            st.error(f"天气查询失败：{err}")
            return None
    except Exception as e:
        st.error(f"网络异常：{e}")
        return None

def get_forecast(city):
    params = {"q": city, "appid": OWM_API_KEY, "units": "metric", "lang": "zh_cn", "cnt": 8}
    try:
        resp = requests.get(FORECAST_URL, params=params, timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

# ==================== JSON 清洗 ====================
def clean_json_response(raw_text):
    if not raw_text:
        return ""
    match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
    if match:
        raw_text = match.group(1)
    else:
        raw_text = re.sub(r'^```|```$', '', raw_text).strip()
    first = raw_text.find('{')
    last = raw_text.rfind('}')
    if first != -1 and last != -1:
        raw_text = raw_text[first:last+1]
    return raw_text.strip()

# ==================== 大模型调用 ====================
def call_qianwen(system_prompt, user_prompt):
    headers = {
        "Authorization": f"Bearer {QIANWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "qwen-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}
    }
    try:
        resp = requests.post(QIANWEN_URL, headers=headers, json=data, timeout=15)
        result = resp.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        else:
            st.error(f"大模型返回错误：{result}")
            return None
    except Exception as e:
        st.error(f"调用大模型失败：{e}")
        return None

# ==================== UI ====================
st.set_page_config(page_title="智能穿衣助手", page_icon="👗")
st.title("👗 基于大模型的智能衣物推荐助手")
st.markdown("输入城市、场景，获取今日科学穿衣建议～")

city = st.text_input("🏙️ 城市名称（拼音或英文名）", value="Beijing")
scene = st.selectbox("🎯 活动场景", list(KNOWLEDGE.keys()))
gender = st.radio("性别", ["男", "女"], horizontal=True)
age = st.slider("年龄", 10, 70, 25)

if st.button("帮我推荐今日穿搭"):
    if not QIANWEN_API_KEY or not OWM_API_KEY:
        st.error("请先在 Streamlit Secrets 中设置 QIANWEN_API_KEY 和 OWM_API_KEY")
    else:
        with st.spinner("正在获取天气并生成推荐..."):
            weather_data = get_weather(city)
            if not weather_data:
                st.stop()

            main = weather_data["main"]
            wind = weather_data["wind"]
            weather_desc = weather_data["weather"][0]["description"]
            temp = main["temp"]
            feels = main["feels_like"]
            humidity = main["humidity"]
            wind_speed = wind["speed"]
            clouds = weather_data.get("clouds", {}).get("all", "未知")

            weather_text = f"""
城市：{city}
天气：{weather_desc}
气温：{temp}℃（体感{feels}℃）
湿度：{humidity}%
风速：{wind_speed} m/s
云量：{clouds}%
""".strip()

            knowledge = KNOWLEDGE.get(scene, "日常舒适穿搭")

            system_prompt = """你是专业穿搭顾问“小搭”。根据天气和用户信息，给出具体到材质和品类的穿衣推荐。
输出JSON，必须包含以下字段：upper, lower, shoes, accessories, reason。
语气亲切自然，推荐理由简明扼要。"""

            user_prompt = f"""
天气信息：
{weather_text}

用户信息：
性别：{gender}，年龄：{age}岁，活动场景：{scene}

专业知识参考：
{knowledge}

请给出今日穿衣推荐。"""

            raw = call_qianwen(system_prompt, user_prompt)
            if not raw:
                st.stop()

            cleaned = clean_json_response(raw)
            try:
                result = json.loads(cleaned)
                st.success("✅ 推荐生成完毕！")

                # ---------- 优化后的卡片式展示 ----------
                # 天气信息栏
                with st.expander("🌤️ 当前天气详情", expanded=True):
                    cols = st.columns(4)
                    cols[0].metric("🌡️ 气温", f"{temp}℃", f"体感 {feels}℃")
                    cols[1].metric("💧 湿度", f"{humidity}%")
                    cols[2].metric("🌬️ 风速", f"{wind_speed} m/s")
                    cols[3].metric("☁️ 云量", f"{clouds}%")
                    st.caption(f"天气状况：{weather_desc}")

                st.markdown("---")

                # 穿搭卡片
                st.subheader("👔 今日推荐穿搭")
                tab1, tab2, tab3 = st.columns(3)

                with tab1:
                    st.markdown("**🧥 上装**")
                    st.info(result.get("upper", "暂无"))
                    st.markdown("**👖 下装**")
                    st.info(result.get("lower", "暂无"))

                with tab2:
                    st.markdown("**👟 鞋履**")
                    st.info(result.get("shoes", "暂无"))
                    st.markdown("**🎒 配饰**")
                    st.info(result.get("accessories", "无") if result.get("accessories") else "无")

                with tab3:
                    st.markdown("**💡 推荐理由**")
                    st.success(result.get("reason", "暂未提供理由"))

                # 保留JSON原始数据查看（折叠）
                with st.expander("🔍 查看原始JSON数据"):
                    st.json(result)

            except Exception as e:
                st.warning("AI输出格式异常，原始输出如下：")
                st.text(raw)
