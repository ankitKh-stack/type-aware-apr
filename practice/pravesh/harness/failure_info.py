"""1.3 Failure Info Extractor.

Reads the JUnit XML part of the test runner's output and builds a
failure record: every test's outcome, the failing tests, and details
of the first failing bug-exposing test.
"""
import sys
import xml.etree.ElementTree as ET

from test_runner import JUNIT_MARKER, ROOT, load_bug, run_tests


def _outcome(testcase):
    """passed / failed / error / skipped for one <testcase> element."""
    if testcase.find("failure") is not None:
        return "failed"
    if testcase.find("error") is not None:
        return "error"
    if testcase.find("skipped") is not None:
        return "skipped"
    return "passed"


def _failing_test_line(traceback_text):
    """The first line pytest marks with '>' is the line in the test that failed."""
    for line in traceback_text.splitlines():
        if line.startswith(">"):
            return line[1:].strip()
    return ""


def extract_failure_info(stdout, bug):
    """Build a failure record from the test runner's stdout.

    parse_ok is False when there is no XML (for example, Docker failed).
    1.5 turns that into INFRA_ERROR.
    """
    record = {"parse_ok": False, "tests": {}, "failing_tests": [], "first_failure": None}

    if JUNIT_MARKER not in stdout:
        return record
    xml_text = stdout.split(JUNIT_MARKER, 1)[1].strip()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return record

    # root.iter() finds <testcase> at any depth, so it works whether the
    # XML starts with <testsuites> (newer pytest) or <testsuite> (older).
    problems = {}  # test name -> its <failure> or <error> element
    for testcase in root.iter("testcase"):
        name = testcase.get("name")
        outcome = _outcome(testcase)
        record["tests"][name] = outcome
        if outcome in ("failed", "error"):
            problems[name] = testcase.find("failure")
            if problems[name] is None:
                problems[name] = testcase.find("error")

    record["parse_ok"] = True
    record["failing_tests"] = sorted(problems)

    # Details for the first bug-exposing test that failed, in the bug file's order.
    for name in bug["bug_exposing_tests"]:
        if name in problems:
            element = problems[name]
            traceback_text = element.text or ""
            record["first_failure"] = {
                "test_name": name,
                "error_message": element.get("message", ""),
                "traceback": traceback_text,
                "failing_test_line": _failing_test_line(traceback_text),
            }
            break

    return record


if __name__ == "__main__":
    # Manual check:  python practice/pravesh/harness/failure_info.py <bug_id> <file>
    if len(sys.argv) != 3:
        sys.exit("Usage: python failure_info.py <bug_id> <path-to-target-file>")
    bug = load_bug(sys.argv[1])
    result = run_tests(bug, ROOT / sys.argv[2])
    info = extract_failure_info(result["stdout"], bug)

    print("parse ok      :", info["parse_ok"])
    print("tests counted :", len(info["tests"]))
    print("failing tests :")
    for name in info["failing_tests"]:
        print("   ", name)
    first = info["first_failure"]
    if first:
        print("first bug-exposing failure:")
        print("    test    :", first["test_name"])
        print("    message :", first["error_message"])
        print("    line    :", first["failing_test_line"])
    else:
        print("first bug-exposing failure: none (all bug-exposing tests passed)")