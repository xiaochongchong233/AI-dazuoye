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
    # 去掉 ```json ... ``` 包裹
    match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
    if match:
        raw_text = match.group(1)
    else:
        # 去掉首尾可能的 ```
        raw_text = re.sub(r'^```|```$', '', raw_text).strip()
    # 截取第一个 { 到最后一个 }
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

city = st.text_input("🏙️ 城市名称（中文或拼音）", value="北京")
scene = st.selectbox("🎯 活动场景", list(KNOWLEDGE.keys()))
gender = st.radio("性别", ["男", "女"], horizontal=True)
age = st.slider("年龄", 10, 70, 25)

if st.button("帮我推荐今日穿搭"):
    if not QIANWEN_API_KEY or not OWM_API_KEY:
        st.error("请先在 Streamlit Secrets 中设置 QIANWEN_API_KEY 和 OWM_API_KEY")
    else:
        with st.spinner("正在获取天气并生成推荐..."):
            # 获取天气
            weather_data = get_weather(city)
            if not weather_data:
                st.stop()

            # 提取天气要素
            main = weather_data["main"]
            wind = weather_data["wind"]
            weather_desc = weather_data["weather"][0]["description"]
            temp = main["temp"]
            feels = main["feels_like"]
            humidity = main["humidity"]
            wind_speed = wind["speed"]
            clouds = weather_data.get("clouds", {}).get("all", "未知")

            # 拼接天气文本
            weather_text = f"""
城市：{city}
天气：{weather_desc}
气温：{temp}℃（体感{feels}℃）
湿度：{humidity}%
风速：{wind_speed} m/s
云量：{clouds}%
""".strip()

            # 获取场景知识
            knowledge = KNOWLEDGE.get(scene, "日常舒适穿搭")

            # 组装提示词
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

            # 调用大模型
            raw = call_qianwen(system_prompt, user_prompt)
            if not raw:
                st.stop()

            # 清洗并解析JSON
            cleaned = clean_json_response(raw)
            try:
                result = json.loads(cleaned)
                st.success("推荐生成完毕！")
                st.json(result)
                st.markdown("### 🌟 推荐解读")
                st.info(result.get("reason", ""))
            except Exception as e:
                st.warning("AI输出格式异常，原始输出如下：")
                st.text(raw)
