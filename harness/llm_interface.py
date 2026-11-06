import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL = "deepseek-flash"
TEMPERATURE = 1.0
MAX_TOKENS = 2000
REQUEST_TIMEOUT = 60
RETRY_DELAYS = [2, 4, 8]
PRICES = {  # USD per 1M tokens
    "off_peak": {"hit": 0.003, "miss": 0.15, "out": 0.60},
    "peak": {"hit": 0.006, "miss": 0.30, "out": 1.20},
}
RETRYABLE = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)


def is_peak(when):
    if when.weekday() >= 5:
        return False
    return 1 <= when.hour < 4 or 6 <= when.hour < 10


def compute_cost(hit, miss, out, when):
    rates = PRICES["peak" if is_peak(when) else "off_peak"]
    return (hit * rates["hit"] + miss * rates["miss"] + out * rates["out"]) / 1_000_000


def call_llm(messages):
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        timeout=REQUEST_TIMEOUT,
        max_retries=0,
    )
    retries = 0
    while True:
        when = datetime.now(timezone.utc)
        start = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                extra_body={"thinking": {"type": "disabled"}},
            )
            break
        except RETRYABLE as exc:
            if retries >= len(RETRY_DELAYS):
                return {
                    "text": None,
                    "error": f"{type(exc).__name__}: {exc}",
                    "retries": retries,
                    "timestamp": when.isoformat(),
                }
            time.sleep(RETRY_DELAYS[retries])
            retries += 1
    latency = time.perf_counter() - start
    usage = resp.usage
    hit = getattr(usage, "prompt_cache_hit_tokens", 0) or 0
    miss = getattr(usage, "prompt_cache_miss_tokens", 0) or 0
    out = usage.completion_tokens
    return {
        "text": resp.choices[0].message.content,
        "error": None,
        "model": resp.model,
        "finish_reason": resp.choices[0].finish_reason,
        "input_cache_hit_tokens": hit,
        "input_cache_miss_tokens": miss,
        "output_tokens": out,
        "latency_s": round(latency, 3),
        "cost_usd": compute_cost(hit, miss, out, when),
        "retries": retries,
        "timestamp": when.isoformat(),
    }


if __name__ == "__main__":
    off = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)   # Saturday
    peak = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)   # Friday 08:00 UTC
    print("off-peak cost:", compute_cost(0, 351, 252, off), "(expect 0.00020385)")
    print("peak cost:    ", compute_cost(0, 351, 252, peak), "(expect 0.0004077)")

    from harness.prompts import SYSTEM_PROMPT

    result = call_llm([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Say hello."},
    ])
    print(result)