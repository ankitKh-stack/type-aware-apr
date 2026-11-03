import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # reads DEEPSEEK_API_KEY from .env

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-flash",
    messages=[{"role": "user", "content": "Say hello in one short sentence."}],
)
print(response.choices[0].message.content)