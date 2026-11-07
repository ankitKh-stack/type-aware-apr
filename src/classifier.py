from xml.etree.ElementTree import ParseError

from src.failure_info import extract_xml, parse_testcases
from src.test_runner import REPO_ROOT, load_bug, run_tests
from src.validator import FAIL_STATUSES, load_baseline

PASS = "PASS"
SAME_FAILURE = "SAME_FAILURE"
NEW_FAILURE = "NEW_FAILURE"
TIMEOUT = "TIMEOUT"
INFRA_ERROR = "INFRA_ERROR"


def classify(result, bug, baseline):
    if result["timed_out"]:
        return TIMEOUT
    xml_text = extract_xml(result["stdout"])
    if xml_text is None:
        return INFRA_ERROR
    try:
        cases = parse_testcases(xml_text)
    except ParseError:
        return INFRA_ERROR

    by_name = {c["name"]: c for c in cases}
    passed = {n for n, c in by_name.items() if c["status"] == "passed"}
    bug_exposing = bug["bug_exposing_tests"]

    exposing_pass = all(n in passed for n in bug_exposing)
    regressions = baseline["baseline_passing"] - passed
    if exposing_pass and not regressions:
        return PASS

    for name in bug_exposing:
        case = by_name.get(name)
        if (
            case is not None
            and case["status"] in FAIL_STATUSES
            and case["message"] == baseline["original_errors"].get(name)
        ):
            return SAME_FAILURE
    return NEW_FAILURE


if __name__ == "__main__":
    bug = load_bug("requests-3179")
    baseline = load_baseline(bug)
    checks = [
        ("developer fix", bug["fixed_file"], PASS),
        ("buggy code", bug["buggy_file"], SAME_FAILURE),
        ("C1 answer", "notes/requests-3179/models_C1.py", PASS),
    ]
    for label, models_file, expected in checks:
        result = run_tests(bug, REPO_ROOT / models_file)
        category = classify(result, bug, baseline)
        status = "ok" if category == expected else "WRONG"
        print(f"{label}: {category} (expected {expected}) {status}")