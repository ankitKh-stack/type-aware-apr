import os
import re
import subprocess
import sys
from pathlib import Path

from harness.ast_tools import find_function, parse_source
from harness.clues import ClueResult

MYPY_TIMEOUT = 30  # seconds (our choice; A2 gives no number)
MYPY_FLAGS = [
    "--check-untyped-defs",
    "--ignore-missing-imports",
    "--follow-imports=skip",
    "--no-error-summary",
    "--no-color-output",
    "--cache-dir=" + os.devnull,
]
# path:LINE: severity: message  [code]   (the path may contain "C:" on Windows)
MYPY_LINE = re.compile(r"^(?P<path>.*?):(?P<line>\d+): (?P<severity>error|warning|note): (?P<message>.*)$")
ERROR_CODE = re.compile(r"\s+\[[a-z0-9-]+\]$")


def function_line_range(source, class_name, function_name):
    """First line (decorators included) and last line of the function, or None."""
    node = find_function(parse_source(source), class_name, function_name)
    if node is None:
        return None
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return start, node.end_lineno


def static_clue(bug, source_path):
    """mypy warnings inside the target function of `source_path` (A2 section 4)."""
    source_path = Path(source_path).resolve()
    try:
        source = source_path.read_text(encoding="utf-8")
        span = function_line_range(source, bug["target_class"], bug["target_function"])
    except (OSError, SyntaxError, ValueError) as exc:
        return ClueResult(failed=True, error="cannot read or parse %s: %s" % (source_path.name, exc))
    if span is None:
        return ClueResult(failed=True, error="target function not found in %s" % source_path.name)
    start, end = span

    command = [sys.executable, "-m", "mypy"] + MYPY_FLAGS + [source_path.name]
    try:
        done = subprocess.run(
            command, cwd=str(source_path.parent), capture_output=True,
            encoding="utf-8", errors="replace", timeout=MYPY_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return ClueResult(failed=True, error="mypy timed out after %d s" % MYPY_TIMEOUT)
    except OSError as exc:
        return ClueResult(failed=True, error="could not start mypy: %s" % exc)
    if done.returncode not in (0, 1):  # 0 = clean, 1 = errors found, 2 = mypy crashed
        return ClueResult(failed=True, error="mypy exit code %d: %s" % (done.returncode, done.stderr.strip()[:300]))

    lines = []
    for raw in done.stdout.splitlines():
        match = MYPY_LINE.match(raw)
        if match and match["severity"] == "error" and start <= int(match["line"]) <= end:
            relative = int(match["line"]) - start + 1  # line 1 is the first line of the function
            lines.append("line %d: %s" % (relative, ERROR_CODE.sub("", match["message"])))
    return ClueResult(text="\n".join(lines))


if __name__ == "__main__":
    from harness.test_runner import REPO_ROOT, load_bug

    bug = load_bug(sys.argv[1])
    path = REPO_ROOT / (sys.argv[2] if len(sys.argv) > 2 else bug["buggy_file"])
    print(static_clue(bug, path))