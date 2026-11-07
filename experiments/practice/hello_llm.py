import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                base_url="https://api.deepseek.com")
resp = client.chat.completions.create(
    model="deepseek-flash",
    messages=[{"role": "system", "content": "You are an Automated Program Repair tool."},
              {"role": "user", "content": "Say hello."}],
    temperature=1.0,
    max_tokens=2000,
    extra_body={"thinking": {"type": "disabled"}},
)
msg = resp.choices[0].message
print("content:", msg.content)
print("reasoning:", getattr(msg, "reasoning_content", None))
print("usage:", resp.usage)
