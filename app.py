import streamlit as st
import requests
import json
import os
from datetime import datetime

# ========== 配置区域 ==========
# 从环境变量读取密钥（部署时设置）
QIANWEN_API_KEY = os.getenv("QIANWEN_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

# 通义千问API（兼容OpenAI格式）
QIANWEN_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

# 天气API（和风天气）
WEATHER_NOW_URL = "https://devapi.qweather.com/v7/weather/now"
WEATHER_3D_URL = "https://devapi.qweather.com/v7/weather/3d"

# ========== 简化知识库 ==========
KNOWLEDGE = {
    "通勤": "商务休闲风，避免过于随意，可穿衬衫、西裤、便西、乐福鞋等。",
    "运动": "速干材质为主，注意透气性和灵活性，跑鞋、运动裤、防晒帽。",
    "晚宴": "正式或半正式着装，男士西装皮鞋，女士晚礼服/连衣裙+高跟鞋。",
    "上学": "舒适得体，卫衣、牛仔裤、运动鞋，方便携带书包。",
    "居家": "以保暖/凉爽睡衣为主，棉质优先。"
}

# ========== 工具函数 ==========
def get_city_id(city_name):
    """通过城市名称搜索城市ID（和风天气）"""
    url = f"https://geoapi.qweather.com/v2/city/lookup?location={city_name}&key={WEATHER_API_KEY}"
    resp = requests.get(url).json()
    if resp.get("code") == "200" and resp.get("location"):
        return resp["location"][0]["id"]
    return None

def get_weather_now(city_id):
    """获取实时天气"""
    params = {"location": city_id, "key": WEATHER_API_KEY}
    resp = requests.get(WEATHER_NOW_URL, params=params).json()
    if resp.get("code") == "200":
        return resp["now"]
    return None

def get_weather_3d(city_id):
    """获取未来3天天气预报"""
    params = {"location": city_id, "key": WEATHER_API_KEY}
    resp = requests.get(WEATHER_3D_URL, params=params).json()
    if resp.get("code") == "200":
        return resp["daily"]
    return None

def build_prompt(weather_text, user_gender, user_age, scene, knowledge):
    """构建发送给大模型的提示词"""
    system_prompt = """你是一位专业的穿衣搭配顾问“小搭”。根据提供的天气、用户信息和场景，推荐具体的穿搭方案。
要求：
1. 上装、下装、鞋履、配件都要具体到品类和材质。
2. 必须考虑温度、体感温度、风力、降雨、紫外线等所有天气要素。
3. 严格遵守场景的着装规范。
4. 用亲切的语气给出推荐，并简要说明理由。
5. 输出格式为JSON，含字段：upper, lower, shoes, accessories, reason。"""

    user_prompt = f"""
天气信息：{weather_text}
用户信息：性别{user_gender}，年龄{user_age}，场景{scene}
专业知识：{knowledge}
请给出今日穿衣推荐。"""
    return system_prompt, user_prompt

def ask_qianwen(system, user):
    """调用通义千问API"""
    headers = {
        "Authorization": f"Bearer {QIANWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "qwen-turbo",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"}  # 强制JSON输出
    }
    resp = requests.post(QIANWEN_URL, headers=headers, json=data)
    if resp.status_code == 200:
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    else:
        return f"大模型调用失败: {resp.text}"

# ========== Streamlit 界面 ==========
st.set_page_config(page_title="智能穿衣助手", page_icon="👗")
st.title("👗 基于大模型的智能衣物推荐助手")
st.markdown("输入城市、场景，获取今日科学穿衣建议～")

# 输入区
col1, col2 = st.columns(2)
city = col1.text_input("🏙️ 城市名称", value="北京")
scene = col2.selectbox("🎯 活动场景", ["通勤", "运动", "晚宴", "上学", "居家"])
gender = st.radio("性别", ["男", "女"], horizontal=True)
age = st.slider("年龄", 10, 70, 25)

if st.button("帮我推荐今日穿搭"):
    if not QIANWEN_API_KEY or not WEATHER_API_KEY:
        st.error("请先设置 QIANWEN_API_KEY 和 WEATHER_API_KEY 环境变量！")
    else:
        with st.spinner("正在获取天气并调用AI大脑..."):
            city_id = get_city_id(city)
            if not city_id:
                st.error("城市未找到，请检查名称。")
            else:
                now = get_weather_now(city_id)
                daily = get_weather_3d(city_id)
                if not now or not daily:
                    st.error("天气数据获取失败，请检查API Key。")
                else:
                    # 整理天气描述
                    today = daily[0]
                    weather_text = f"""
实时天气：{now['text']}，气温{now['temp']}℃，体感{now['feelsLike']}℃，风力{now['windScale']}级{now['windDir']}，湿度{now['humidity']}%
今日预报：{today['textDay']}，气温{today['tempMin']}℃~{today['tempMax']}℃，紫外线强度指数{today.get('uvIndex','暂无')}"""
                    
                    # 检索知识库
                    knowledge = KNOWLEDGE.get(scene, "舒适日常穿搭")
                    
                    system, user = build_prompt(weather_text, gender, age, scene, knowledge)
                    raw = ask_qianwen(system, user)
                    
                    try:
                        result = json.loads(raw)
                        st.success("推荐生成完毕！")
                        st.json(result)
                    except:
                        st.warning("AI返回格式异常，原始输出：")
                        st.text(raw)