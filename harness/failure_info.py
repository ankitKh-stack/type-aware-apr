import xml.etree.ElementTree as ET

MARKER = "===JUNIT==="


def extract_xml(stdout):
    if MARKER not in stdout:
        return None
    return stdout.split(MARKER, 1)[1].strip()


def parse_testcases(xml_text):
    root = ET.fromstring(xml_text)
    results = []
    for case in root.iter("testcase"):
        status = "passed"
        message = ""
        traceback = ""
        for child in case:
            if child.tag in ("failure", "error"):
                status = "failed" if child.tag == "failure" else "error"
                message = child.get("message", "")
                traceback = child.text or ""
            elif child.tag == "skipped":
                status = "skipped"
        results.append(
            {
                "name": case.get("name"),
                "classname": case.get("classname"),
                "status": status,
                "message": message,
                "traceback": traceback,
            }
        )
    return results


def build_failure_record(cases, bug_exposing_tests):
    failing = {c["name"] for c in cases if c["status"] in ("failed", "error")}
    first = None
    for c in cases:
        if c["name"] in bug_exposing_tests and c["status"] in ("failed", "error"):
            first = c
            break
    record = {
        "failing_tests": sorted(failing),
        "test_name": None,
        "error_message": None,
        "traceback": None,
        "failing_line": None,
    }
    if first is not None:
        record["test_name"] = first["name"]
        record["error_message"] = first["message"]
        record["traceback"] = first["traceback"]
        for line in first["traceback"].splitlines():
            if line.startswith(">"):
                record["failing_line"] = line[1:].strip()
                break
    return record


if __name__ == "__main__":
    from harness.test_runner import REPO_ROOT, load_bug, run_tests

    bug = load_bug("requests-3179")
    result = run_tests(bug, REPO_ROOT / bug["buggy_file"])
    cases = parse_testcases(extract_xml(result["stdout"]))
    record = build_failure_record(cases, bug["bug_exposing_tests"])
    print("failing tests:", record["failing_tests"])
    print("test:", record["test_name"])
    print("error:", record["error_message"])
    print("failing line:", record["failing_line"])
    print("--- traceback ---")
    print(record["traceback"])