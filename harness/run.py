import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness.ast_tools import parse_source, find_function
from harness.classifier import PASS, SAME_FAILURE, NEW_FAILURE, INFRA_ERROR, classify
from harness.failure_info import extract_xml, parse_testcases, build_failure_record
from harness.llm_interface import call_llm, MODEL, TEMPERATURE, MAX_TOKENS
from harness.logger import RunLogger
from harness.patch_applier import apply_patch
from harness.prompts import SYSTEM_PROMPT, build_prompt, build_feedback, function_source
from harness.response_parser import parse_response
from harness.test_runner import REPO_ROOT, load_bug, run_tests
from harness.validator import load_baseline

MAX_CALLS = 10
EXCHANGES = 3
PASS_RERUNS = 3
MAX_INFRA_ERRORS = 3
FAIL_STATUSES = ("failed", "error")


def make_fake_llm(path):
    text = Path(path).read_text(encoding="utf-8")

    def fake(messages):
        return {
            "text": text,
            "error": None,
            "model": "fake",
            "finish_reason": "stop",
            "input_cache_hit_tokens": 0,
            "input_cache_miss_tokens": 0,
            "output_tokens": 0,
            "latency_s": 0.0,
            "cost_usd": 0.0,
            "retries": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return fake


def new_failure_record(cases, bug, baseline):
    wanted = set(bug["bug_exposing_tests"]) | baseline["baseline_passing"]
    failing = [c for c in cases if c["status"] in FAIL_STATUSES]
    for case in failing:
        if case["name"] in wanted:
            return {"test_name": case["name"], "error_message": case["message"]}
    return {"test_name": failing[0]["name"], "error_message": failing[0]["message"]}


def test_and_classify(bug, path, baseline):
    result = run_tests(bug, path)
    category = classify(result, bug, baseline)
    if category == INFRA_ERROR:  # A2: retry once on a Docker failure
        result = run_tests(bug, path)
        category = classify(result, bug, baseline)
    return result, category


def rerun_if_pass(bug, path, baseline, result, category):
    reruns = []
    if category != PASS:
        return result, category, reruns
    for _ in range(PASS_RERUNS):
        result, category = test_and_classify(bug, path, baseline)
        reruns.append(category)
        if category != PASS:
            break
    return result, category, reruns


def attempt_once(ctx, trial, attempt, messages):
    logger, bug, baseline = ctx["logger"], ctx["bug"], ctx["baseline"]
    folder = logger.call_dir(trial, attempt)
    logger.save_json(folder, "02_messages_sent.json", messages)
    llm_result = ctx["llm"](messages)
    out = {"llm": llm_result, "category": None, "reason": None,
           "failure": None, "reruns": [], "test_seconds": 0.0}
    logger.save_json(folder, "03_llm_call.json", {k: v for k, v in llm_result.items() if k != "text"})
    logger.log(f"trial {trial} call {attempt} llm_call", "error" if llm_result["error"] else "ok")
    if llm_result["error"]:
        out["category"] = INFRA_ERROR
        out["reason"] = llm_result["error"]
        return out

    logger.save_text(folder, "04_response_raw.txt", llm_result["text"])
    parsed = parse_response(llm_result["text"], ctx["original"])
    if parsed["category"]:
        out["category"] = parsed["category"]
        out["reason"] = parsed["reason"]
        logger.save_json(folder, "05_parse_error.json",
                         {"category": parsed["category"], "reason": parsed["reason"]})
        logger.log(f"trial {trial} call {attempt} parse", parsed["category"])
        return out

    logger.save_text(folder, "05_parsed_function.py", parsed["function_source"] + "\n")
    patched = apply_patch(ctx["source"], bug["target_class"], bug["target_function"],
                          parsed["function_source"])
    logger.save_text(folder, "06_patched_file.py", patched)
    patched_path = folder / "06_patched_file.py"

    result, category = test_and_classify(bug, patched_path, baseline)
    result, category, reruns = rerun_if_pass(bug, patched_path, baseline, result, category)
    out["category"] = category
    out["reruns"] = reruns
    out["test_seconds"] = result["elapsed"]
    logger.save_text(folder, "07_test_output.txt",
                     result["stdout"] + "\n--- stderr ---\n" + result["stderr"])
    cases = []
    if category in (PASS, SAME_FAILURE, NEW_FAILURE):
        xml = extract_xml(result["stdout"])
        logger.save_text(folder, "07_junit.xml", xml)
        cases = parse_testcases(xml)
    if category == NEW_FAILURE:
        out["failure"] = new_failure_record(cases, bug, baseline)
    logger.save_json(folder, "08_classification.json", {"category": category, "reruns": reruns})
    logger.log(f"trial {trial} call {attempt} classify", f"{category} reruns={reruns}")
    return out


def make_feedback(category, out):
    if category == NEW_FAILURE:
        return build_feedback(category, out["failure"])
    return build_feedback(category, reason=out["reason"])


def run_trial(ctx, trial):
    logger, bug = ctx["logger"], ctx["bug"]
    initial = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": ctx["first_prompt"]},
    ]
    messages = list(initial)
    conversation, in_conversation = 1, 0
    calls = attempt = infra = 0
    tokens_in = tokens_out = 0
    cost = 0.0
    outcome = "unsolved"
    plausible_call = None

    while calls < MAX_CALLS:
        attempt += 1
        out = attempt_once(ctx, trial, attempt, messages)
        llm_result, category = out["llm"], out["category"]
        hit = llm_result.get("input_cache_hit_tokens", 0)
        miss = llm_result.get("input_cache_miss_tokens", 0)
        output = llm_result.get("output_tokens", 0)
        tokens_in += hit + miss
        tokens_out += output
        cost += llm_result.get("cost_usd", 0.0)
        logger.append_record({
            "type": "attempt",
            "run_id": logger.run_id,
            "bug_id": bug["id"],
            "condition": ctx["condition"],
            "trial": trial,
            "call": attempt,
            "conversation": conversation,
            "counts_as_try": category != INFRA_ERROR,
            "model": llm_result.get("model", MODEL),
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            "timestamp": llm_result["timestamp"],
            "messages_sent": messages,
            "response": llm_result["text"],
            "category": category,
            "reason": out["reason"],
            "new_failure": out["failure"],
            "reruns": out["reruns"],
            "input_cache_hit_tokens": hit,
            "input_cache_miss_tokens": miss,
            "output_tokens": output,
            "latency_s": llm_result.get("latency_s"),
            "cost_usd": llm_result.get("cost_usd", 0.0),
            "api_retries": llm_result.get("retries", 0),
            "test_seconds": out["test_seconds"],
        })
        print(f"trial {trial} call {attempt}: {category}")

        if category == INFRA_ERROR:
            infra += 1
            if infra >= MAX_INFRA_ERRORS:
                outcome = "infra_failure"
                break
            continue
        calls += 1
        in_conversation += 1
        if category == PASS:
            outcome = "plausible"
            plausible_call = attempt
            break
        feedback = make_feedback(category, out)
        logger.save_text(logger.call_dir(trial, attempt), "09_feedback.txt", feedback)
        if in_conversation >= EXCHANGES:
            messages = list(initial)
            conversation += 1
            in_conversation = 0
        else:
            messages = messages + [
                {"role": "assistant", "content": llm_result["text"]},
                {"role": "user", "content": feedback},
            ]

    summary = {
        "type": "run",
        "run_id": logger.run_id,
        "bug_id": bug["id"],
        "condition": ctx["condition"],
        "trial": trial,
        "outcome": outcome,
        "calls_used": calls,
        "plausible_call": plausible_call,
        "total_input_tokens": tokens_in,
        "total_output_tokens": tokens_out,
        "total_cost_usd": cost,
    }
    logger.append_record(summary)
    logger.log(f"trial {trial} run", f"{outcome} calls={calls} cost_usd={cost:.6f}")
    print(f"trial {trial}: {outcome} after {calls} call(s), cost {cost:.6f} USD")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bug", default="requests-3179")
    parser.add_argument("--condition", default="C1")
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--fake-llm", default=None)
    args = parser.parse_args()
    if args.condition != "C1":
        parser.error("only condition C1 exists in stage 1")

    bug = load_bug(args.bug)
    try:
        baseline = load_baseline(bug)
    except FileNotFoundError:
        sys.exit("baseline.json is missing: run python -m harness.validator first")

    buggy_path = REPO_ROOT / bug["buggy_file"]
    source = buggy_path.read_text(encoding="utf-8")
    original = find_function(parse_source(source), bug["target_class"], bug["target_function"])

    logger = RunLogger()
    print("run id:", logger.run_id)
    first = run_tests(bug, buggy_path)
    cases = parse_testcases(extract_xml(first["stdout"]))
    failure = build_failure_record(cases, bug["bug_exposing_tests"])
    logger.save_json(logger.run_dir, "01_failure_record.json", failure)
    first_prompt = build_prompt(bug, failure, function_source(source, original))

    llm = make_fake_llm(args.fake_llm) if args.fake_llm else call_llm
    if args.fake_llm:
        print("using fake LLM answers from", args.fake_llm)
    ctx = {"bug": bug, "baseline": baseline, "source": source, "original": original,
           "logger": logger, "llm": llm, "first_prompt": first_prompt,
           "condition": args.condition}
    for trial in range(1, args.trials + 1):
        run_trial(ctx, trial)


if __name__ == "__main__":
    main()