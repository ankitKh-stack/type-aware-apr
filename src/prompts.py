from src.classifier import SAME_FAILURE, NEW_FAILURE, TIMEOUT
from src.response_parser import INVALID_OUTPUT, SYNTAX_ERROR, SIGNATURE_VIOLATION
from src.test_runner import REPO_ROOT


def load_template(name):
    path = REPO_ROOT / "prompts" / name
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n").rstrip("\n")


SYSTEM_PROMPT = load_template("system_prompt.txt")
FENCE = "`" * 3
INVALID_CATEGORIES = (INVALID_OUTPUT, SYNTAX_ERROR, SIGNATURE_VIOLATION)


def function_source(source, node):
    first = node.lineno
    if node.decorator_list:
        first = min(d.lineno for d in node.decorator_list)
    return "\n".join(source.split("\n")[first - 1:node.end_lineno])


def build_prompt(bug, failure, buggy_function, clues=None, condition="C1"):
    if condition != "C1":
        raise NotImplementedError("clue blocks are added in stage 2")
    test_id = bug["test_command"].split(" ", 1)[1] + "::" + failure["test_name"]
    return load_template("basic_prompt.txt").format(
        fence=FENCE,
        buggy_function=buggy_function,
        test_id=test_id,
        failing_line=failure["failing_line"],
        error_message=failure["error_message"],
    )


def build_feedback(category, failure=None, reason=None):
    if category == SAME_FAILURE:
        return load_template("feedback_same_failure.txt")
    if category == NEW_FAILURE:
        return load_template("feedback_new_failure.txt").format(
            test_name=failure["test_name"], error_message=failure["error_message"]
        )
    if category == TIMEOUT:
        return load_template("feedback_timeout.txt")
    if category in INVALID_CATEGORIES:
        return load_template("feedback_invalid_output.txt").format(reason=reason)
    raise ValueError(f"no feedback template for category {category}")


if __name__ == "__main__":
    import difflib

    from src.ast_tools import parse_source, find_function
    from src.failure_info import extract_xml, parse_testcases, build_failure_record
    from src.test_runner import REPO_ROOT, load_bug, run_tests

    bug = load_bug("requests-3179")
    buggy_path = REPO_ROOT / bug["buggy_file"]
    source = buggy_path.read_text(encoding="utf-8")
    node = find_function(parse_source(source), bug["target_class"], bug["target_function"])
    result = run_tests(bug, buggy_path)
    cases = parse_testcases(extract_xml(result["stdout"]))
    failure = build_failure_record(cases, bug["bug_exposing_tests"])
    prompt = build_prompt(bug, failure, function_source(source, node))

    text = (REPO_ROOT / "notes" / "requests-3179" / "attempt_C1.md").read_text(encoding="utf-8")
    expected = text.split("## Prompt\n\n", 1)[1].split("\n\n## Response", 1)[0]
    if prompt.strip() == expected.strip():
        print("C1 prompt: identical to attempt_C1.md ok")
    else:
        print("C1 prompt: DIFFERENT")
        for line in difflib.unified_diff(expected.splitlines(), prompt.splitlines(), "attempt_C1.md", "built", lineterm=""):
            print(line)
    print(build_feedback(SAME_FAILURE))
    print(build_feedback(NEW_FAILURE, failure))
    print(build_feedback(SYNTAX_ERROR, reason="expected ':' (line 1)"))