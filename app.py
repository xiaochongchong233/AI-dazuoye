import streamlit as st
import requests
import os

# 读取密钥
QIANWEN_API_KEY = os.getenv("QIANWEN_API_KEY")
OWM_API_KEY = os.getenv("OWM_API_KEY")   # OpenWeatherMap Key

# 通义千问 URL
QIANWEN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# 天气 API (OpenWeatherMap)
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# 简化知识库
KNOWLEDGE = {
    "通勤": "商务休闲风，衬衫、西裤、便西、乐福鞋。",
    "运动": "速干材质，透气跑鞋，防晒帽。",
    "晚宴": "正式着装，西装皮鞋或晚礼服高跟鞋。",
    "上学": "舒适得体，卫衣、牛仔裤、运动鞋。",
    "居家": "居家棉质睡衣。"
}

def get_weather(city):
    params = {"q": city, "appid": OWM_API_KEY, "units": "metric", "lang": "zh_cn"}
    resp = requests.get(WEATHER_URL, params=params)
    if resp.status_code == 200:
        return resp.json()
    else:
        st.error(f"天气查询失败：{resp.json().get('message', '未知错误')}")
        return None

def get_forecast(city):
    params = {"q": city, "appid": OWM_API_KEY, "units": "metric", "lang": "zh_cn", "cnt": 8}  # 取未来24小时
    resp = requests.get(FORECAST_URL, params=params)
    if resp.status_code == 200:
        return resp.json()
    return None

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
        resp = requests.post(QIANWEN_URL, headers=headers, json=data)
        result = resp.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        else:
            return f"大模型返回错误：{result}"
    except Exception as e:
        return f"调用失败：{e}"

# ---------- UI ----------
st.title("👗 智能衣物推荐助手")
st.markdown("输入城市、场景，获取今日科学穿衣建议～")

city = st.text_input("🏙️ 城市名称（中文或拼音）", value="北京")
scene = st.selectbox("🎯 活动场景", ["通勤", "运动", "晚宴", "上学", "居家"])
gender = st.radio("性别", ["男", "女"], horizontal=True)
age = st.slider("年龄", 10, 70, 25)

if st.button("帮我推荐今日穿搭"):
    if not QIANWEN_API_KEY or not OWM_API_KEY:
        st.error("请先在 Streamlit Secrets 中设置 QIANWEN_API_KEY 和 OWM_API_KEY")
    else:
        with st.spinner("正在获取天气并生成推荐..."):
            weather_data = get_weather(city)
            if weather_data:
                main = weather_data["main"]
                wind = weather_data["wind"]
                weather_desc = weather_data["weather"][0]["description"]
                temp = main["temp"]
                feels = main["feels_like"]
                humidity = main["humidity"]
                wind_speed = wind["speed"]
                # 简易紫外线（OpenWeatherMap免费版无UV，可用云量估计）
                clouds = weather_data["clouds"]["all"]

                weather_text = f"""
城市：{city}
天气：{weather_desc}
气温：{temp}℃（体感{feels}℃）
湿度：{humidity}%
风速：{wind_speed} m/s
云量：{clouds}%
""".strip()

                knowledge = KNOWLEDGE.get(scene, "日常舒适穿搭")

                system_prompt = """你是专业穿搭顾问“小搭”。根据天气和用户信息，给出具体到材质和品类的穿衣推荐。输出JSON，含upper, lower, shoes, accessories, reason五个字段。语气亲切。"""
                user_prompt = f"""
天气信息：
{weather_text}
用户：{gender}，{age}岁，场景：{scene}
知识参考：{knowledge}
请推荐今日穿搭。
"""
                result = call_qianwen(system_prompt, user_prompt)
                try:
                    result_json = json.loads(result)
                    st.success("推荐生成完毕！")
                    st.json(result_json)
                except:
                    st.warning("AI输出格式异常，原始输出：")
                    st.text(result)
