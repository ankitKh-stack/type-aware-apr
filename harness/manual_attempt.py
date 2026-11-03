"""Send one manual repair attempt for requests-3179 to DeepSeek (step 1.7).

Usage: python harness/manual_attempt.py C1   (no clues)
       python harness/manual_attempt.py C4   (runtime + static clues)
"""
import os
import sys
from datetime import datetime, timezone

CONDITION = sys.argv[1] if len(sys.argv) > 1 else ""
if CONDITION not in ("C1", "C4"):
    sys.exit("Usage: python harness/manual_attempt.py C1|C4")

BUG_DIR = "notes/requests-3179"
FIRST_LINE, LAST_LINE = 789, 812  # json() in models_buggy.py

with open(os.path.join(BUG_DIR, "models_buggy.py"), encoding="utf-8") as f:
    buggy_function = "".join(f.readlines()[FIRST_LINE - 1:LAST_LINE])

prompt = f"""The following Python function contains a bug that makes a test fail with a TypeError.

```python
{buggy_function}```

The code fails on this test: tests/test_requests.py::TestRequests::test_response_json_when_content_is_None
on this test line: r.json()
with the following error: TypeError: object of type 'NoneType' has no len()
"""

if CONDITION == "C4":
    prompt += """
Runtime types when the TypeError was raised:
in json, line 795: self.content: NoneType = None, self.encoding: NoneType = None
"""
    # No mypy block: mypy found nothing inside json(), and A2 §12 says a
    # missing clue leaves that block out.

prompt += """
Please provide the complete corrected function in a single python code block. Do not change the function name or its parameters."""

if "--dry-run" in sys.argv:
    print(prompt)
    sys.exit()

from openai import OpenAI

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
sent_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
resp = client.chat.completions.create(
    model="deepseek-flash",
    messages=[{"role": "system", "content": "You are an Automated Program Repair tool."},
              {"role": "user", "content": prompt}],
    temperature=1.0,
    max_tokens=2000,
    extra_body={"thinking": {"type": "disabled"}},
)
answer = resp.choices[0].message.content

out_path = os.path.join(BUG_DIR, f"attempt_{CONDITION}.md")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(f"# {CONDITION} attempt, sent {sent_at} (UTC)\n\n")
    f.write(f"Model: {resp.model}\nUsage: {resp.usage}\n\n")
    f.write("## Prompt\n\n" + prompt + "\n\n## Response\n\n" + answer + "\n")

print(answer)
print("\nUsage:", resp.usage)
print("Saved to", out_path)