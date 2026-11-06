from harness.ast_tools import parse_source, find_function


def apply_patch(source, class_name, function_name, new_function):
    tree = parse_source(source)
    node = find_function(tree, class_name, function_name)
    if node is None:
        raise ValueError(f"function {function_name} not found")
    first = node.lineno
    if node.decorator_list:
        first = min(d.lineno for d in node.decorator_list)
    last = node.end_lineno
    indent = " " * node.col_offset
    new_lines = []
    for line in new_function.rstrip("\n").split("\n"):
        new_lines.append(indent + line if line.strip() else "")
    lines = source.split("\n")
    lines[first - 1:last] = new_lines
    return "\n".join(lines)


if __name__ == "__main__":
    from harness.response_parser import parse_response
    from harness.test_runner import REPO_ROOT, load_bug

    bug = load_bug("requests-3179")
    source = (REPO_ROOT / bug["buggy_file"]).read_text(encoding="utf-8")
    original = find_function(parse_source(source), bug["target_class"], bug["target_function"])
    text = (REPO_ROOT / "notes" / "requests-3179" / "attempt_C1.md").read_text(encoding="utf-8")
    parsed = parse_response(text.split("## Response", 1)[1], original)
    patched = apply_patch(source, bug["target_class"], bug["target_function"], parsed["function_source"])
    out = REPO_ROOT / "work" / "c1_patched.py"
    out.parent.mkdir(exist_ok=True)
    out.write_text(patched, encoding="utf-8", newline="\n")
    print("wrote", out)