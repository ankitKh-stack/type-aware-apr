import json

from harness.failure_info import extract_xml, parse_testcases
from harness.test_runner import REPO_ROOT, load_bug, run_tests

FAIL_STATUSES = ("failed", "error")


def _run_and_parse(bug, models_file):
    result = run_tests(bug, REPO_ROOT / models_file)
    if result["timed_out"]:
        return None, "the test run timed out"
    xml_text = extract_xml(result["stdout"])
    if xml_text is None:
        return None, "no JUnit XML in the output"
    return {c["name"]: c for c in parse_testcases(xml_text)}, None


def _exclusion_reason(bug, buggy, fixed):
    for name in bug["bug_exposing_tests"]:
        if name not in buggy or name not in fixed:
            return f"bug-exposing test not found: {name}"
        if buggy[name]["status"] not in FAIL_STATUSES:
            return f"{name} does not fail on the buggy code"
        if not buggy[name]["message"].startswith("TypeError"):
            return f"{name} fails on the buggy code, but not with a TypeError"
        if fixed[name]["status"] != "passed":
            return f"{name} still fails with the developer fix"
    return None


def validate_bug(bug):
    verdict = {
        "valid": False,
        "exclusion_reason": None,
        "baseline_passing": [],
        "buggy_failing": [],
        "fixed_failing": [],
        "original_errors": {},
    }
    buggy, problem = _run_and_parse(bug, bug["buggy_file"])
    if problem:
        verdict["exclusion_reason"] = "buggy run: " + problem
        return verdict
    fixed, problem = _run_and_parse(bug, bug["fixed_file"])
    if problem:
        verdict["exclusion_reason"] = "fixed run: " + problem
        return verdict

    verdict["buggy_failing"] = sorted(n for n, c in buggy.items() if c["status"] in FAIL_STATUSES)
    verdict["fixed_failing"] = sorted(n for n, c in fixed.items() if c["status"] in FAIL_STATUSES)
    verdict["baseline_passing"] = sorted(n for n, c in fixed.items() if c["status"] == "passed")
    verdict["original_errors"] = {
        n: buggy[n]["message"] for n in bug["bug_exposing_tests"] if n in buggy
    }
    verdict["exclusion_reason"] = _exclusion_reason(bug, buggy, fixed)
    verdict["valid"] = verdict["exclusion_reason"] is None
    return verdict


def baseline_path(bug):
    return REPO_ROOT / "bugs" / bug["id"] / "baseline.json"


def save_baseline(bug, verdict):
    data = {
        "bug_id": bug["id"],
        "original_errors": verdict["original_errors"],
        "baseline_passing": verdict["baseline_passing"],
    }
    with open(baseline_path(bug), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_baseline(bug):
    with open(baseline_path(bug), encoding="utf-8") as f:
        data = json.load(f)
    return {
        "baseline_passing": set(data["baseline_passing"]),
        "original_errors": data["original_errors"],
    }


if __name__ == "__main__":
    bug = load_bug("requests-3179")
    verdict = validate_bug(bug)
    print("valid:", verdict["valid"])
    print("exclusion reason:", verdict["exclusion_reason"])
    print("buggy failing:", verdict["buggy_failing"])
    print("fixed failing:", verdict["fixed_failing"])
    print("baseline passing:", len(verdict["baseline_passing"]), "tests")
    if verdict["valid"]:
        save_baseline(bug, verdict)
        print("saved baseline to", baseline_path(bug))