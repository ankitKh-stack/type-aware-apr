# Decisions

## 2026-10-15 Harness Python
- Harness runs on Python 3.14.4 (Ubuntu's version). A2 §7 says 3.14.8: update A2 to match.
- Each bug runs in its own Python inside Docker (e.g. requests-3179 uses 3.5.9 via pyenv).

## 2026-11-03 LLM model and settings
- API model name: `deepseek-flash`, served by DeepSeek-V4.1-Flash-1017 (A2's "DeepSeek V4.1 Flash").
- Non-thinking mode: every call sends `extra_body={"thinking": {"type": "disabled"}}`.
  Thinking mode is on by default and ignores `temperature`.
- temperature = 1.0, max_tokens = 2000 on every call.

## 2026-11-03 Pricing (USD per 1M tokens, deepseek-flash)
| | Off-peak | Peak |
|---|---|---|
| Input, cache hit | 0.003 | 0.006 |
| Input, cache miss | 0.15 | 0.30 |
| Output | 0.60 | 1.20 |
- Peak: 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri. Weekends are off-peak.
- Cost per call uses the rate for that call's timestamp (A2 §14 formula needs updating).
- Plan: run the main experiment off-peak.
- TODO: pick one currency for the budget (A2 says 50 CAD, prices are USD).

## 2026-11-03 Plausible patch rule (changes A2 §2/§14)
- Some tests fail even with the developer's fix (e.g. requests-3179: test_pyopenssl_redirect
  fails on an expired certificate; test_conflicting_post_params fails because the test uses
  old pytest syntax).
- Rule: a patch is plausible if (1) the bug-exposing tests pass and (2) no test fails
  that passes with the developer's fix.
- The Bug Validator records each bug's "already failing" tests from the fixed version.
- The classifier checks bug-exposing tests by name, never just "TypeError appeared".# Decisions
