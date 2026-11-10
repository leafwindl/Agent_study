import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DeepSeek_API_KEY"),
    base_url=os.getenv("BASE_URL"),
)

resp = client.chat.completions.create(
    model="deepseek-flash",
    messages=[
        {"role": "system", "content": "你是一个有帮助的助手。"},
        {"role": "user", "content": "你调用一个工具"},
    ],
    tools=[],
    tool_choice="auto"
)

print(resp.choices[0].message)
