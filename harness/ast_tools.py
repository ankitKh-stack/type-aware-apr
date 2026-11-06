import ast
import warnings

def parse_source(source):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(source)

def find_function(tree, class_name, function_name):
    if class_name is None:
        scopes = [tree]
    else:
        scopes = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.ClassDef) and n.name == class_name
        ]
    for scope in scopes:
        for node in scope.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
                return node
    return None


if __name__ == "__main__":
    from harness.test_runner import REPO_ROOT, load_bug

    bug = load_bug("requests-3179")
    source = (REPO_ROOT / bug["buggy_file"]).read_text(encoding="utf-8")
    node = find_function(parse_source(source), bug["target_class"], bug["target_function"])
    print(node.name, node.lineno, node.end_lineno)
    print(ast.get_source_segment(source, node).splitlines()[0])