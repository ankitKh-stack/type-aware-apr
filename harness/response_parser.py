import ast
import re
import textwrap

from harness.ast_tools import parse_source

INVALID_OUTPUT = "INVALID_OUTPUT"
SYNTAX_ERROR = "SYNTAX_ERROR"
SIGNATURE_VIOLATION = "SIGNATURE_VIOLATION"

FENCE = re.compile(r"`{3}([A-Za-z0-9_+-]*)[ \t]*\r?\n(.*?)`{3}", re.DOTALL)


def extract_code_block(text):
    for match in FENCE.finditer(text):
        language = match.group(1).lower()
        if language in ("python", "py", "python3", ""):
            return match.group(2)
    return None


def _result(category, reason=None, function_source=None):
    return {"category": category, "reason": reason, "function_source": function_source}


def parse_response(text, original_node):
    code = extract_code_block(text)
    if code is None:
        return _result(INVALID_OUTPUT, "no python code block found")
    if not code.strip():
        return _result(INVALID_OUTPUT, "the code block is empty")
    code = textwrap.dedent(code)
    try:
        tree = parse_source(code)
    except SyntaxError as exc:
        return _result(SYNTAX_ERROR, f"{exc.msg} (line {exc.lineno})")

    functions = (ast.FunctionDef, ast.AsyncFunctionDef)
    candidates = [
        n for n in ast.walk(tree)
        if isinstance(n, functions) and n.name == original_node.name
    ]
    if not candidates:
        return _result(SIGNATURE_VIOLATION, f"no function named {original_node.name} in the answer")
    node = candidates[0]
    if ast.dump(node.args) != ast.dump(original_node.args):
        return _result(SIGNATURE_VIOLATION, f"the parameters of {original_node.name} were changed")

    segment = ast.get_source_segment(code, node)
    return _result(None, None, textwrap.dedent(" " * node.col_offset + segment))


if __name__ == "__main__":
    from harness.ast_tools import find_function
    from harness.test_runner import REPO_ROOT, load_bug

    bug = load_bug("requests-3179")
    source = (REPO_ROOT / bug["buggy_file"]).read_text(encoding="utf-8")
    original = find_function(parse_source(source), bug["target_class"], bug["target_function"])
    F = "`" * 3
    answers = {
        "valid answer": f"Here is the fix:\n{F}python\ndef json(self, **kwargs):\n    return 1\n{F}\nDone.",
        "no code block": "I think the bug is in the length check.",
        "syntax error": f"{F}python\ndef json(self, **kwargs)\n    return 1\n{F}",
        "signature changed": f"{F}python\ndef json(self):\n    return 1\n{F}",
        "indented method": f"{F}python\n    def json(self, **kwargs):\n        return 1\n{F}",
    }
    for label, text in answers.items():
        result = parse_response(text, original)
        print(label, "->", result["category"], "|", result["reason"])
    print("--- real C1 answer ---")
    from harness.ast_tools import parse_source, find_function
    from harness.test_runner import REPO_ROOT
    text = (REPO_ROOT / "notes" / "requests-3179" / "attempt_C1.md").read_text(encoding="utf-8")
    response = text.split("## Response", 1)[1]
    buggy = (REPO_ROOT / "bugs" / "requests-3179" / "models_buggy.py").read_text(encoding="utf-8")
    original = find_function(parse_source(buggy), "Response", "json")
    print(parse_response(response, original))