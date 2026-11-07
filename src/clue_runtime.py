import json
import subprocess
import uuid
from pathlib import Path

from src.clue_static import function_line_range
from src.clues import ClueResult
from src.test_runner import REPO_ROOT, load_bug

MARKER = "===RTCLUES==="
PLUGIN_FILE = REPO_ROOT / "src" / "plugins" / "rt_collector.py"
PLUGIN_IN_CONTAINER = "/opt/apr/rt_collector.py"
TIMEOUT = 30  # seconds, same as the test runner


def build_collector_command(bug, models_path, test_names, container_name):
    """docker run command: the normal test run plus the rt_collector plugin."""
    mount = "%s:%s/%s:ro" % (Path(models_path).resolve(), bug["workdir"], bug["target_file"])
    plugin_mount = "%s:%s:ro" % (PLUGIN_FILE.resolve(), PLUGIN_IN_CONTAINER)
    inner = "; ".join(
        bug["env_setup"]
        + [
            "cd %s" % bug["workdir"],
            "export PYTHONPATH=/opt/apr",
            "%s -q -p no:cacheprovider -p rt_collector" % bug["test_command"],
            "echo %s" % MARKER,
            "cat /tmp/rt.json 2>/dev/null",
            "true",
        ]
    )
    return [
        "docker", "run", "--rm", "--name", container_name,
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "LANG=C.UTF-8",
        "-e", "APR_RT_OUT=/tmp/rt.json",
        "-e", "APR_TEST_NAMES=" + ",".join(test_names),
        "-e", "APR_TARGET_FILE=" + bug["target_file"],
        "-e", "APR_TARGET_FUNCTION=" + bug["target_function"],
        "-v", mount,
        "-v", plugin_mount,
        bug["image"],
        "bash", "-c", inner,
    ]


def format_clue(data, bug, function_start):
    """Turn the plugin's JSON into the clue text of A2 section 6.2.

    Inside the target function the line number is relative to the function
    (line 1 = its first line); in any other function it is the line in its file.
    """
    lines = []
    for frame in data.get("frames", []):
        if not frame["vars"]:
            continue
        line_no = frame["line"]
        in_target = (frame["file"].endswith(bug["target_file"])
                     and frame["function"] == bug["target_function"])
        if in_target and function_start:
            line_no = line_no - function_start + 1
        variables = ", ".join("%s: %s = %s" % (n, t, v) for n, t, v in frame["vars"])
        lines.append("in %s (%s), line %d: %s" % (frame["function"], frame["file"], line_no, variables))
    return "\n".join(lines)


def runtime_clue(bug, models_path, test_names=None, timeout=TIMEOUT):
    """Runtime type clue for the first failing test among `test_names`
    (default: the bug-exposing tests), run on `models_path`."""
    test_names = list(test_names or bug["bug_exposing_tests"])
    try:
        source = Path(models_path).read_text(encoding="utf-8")
        span = function_line_range(source, bug["target_class"], bug["target_function"])
    except (OSError, SyntaxError, ValueError) as exc:
        return ClueResult(failed=True, error="cannot read or parse %s: %s" % (Path(models_path).name, exc))
    function_start = span[0] if span else None

    name = "apr-rt-" + uuid.uuid4().hex[:8]
    command = build_collector_command(bug, models_path, test_names, name)
    try:
        done = subprocess.run(command, capture_output=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return ClueResult(failed=True, error="runtime collector timed out after %d s" % timeout)
    except OSError as exc:
        return ClueResult(failed=True, error="could not start docker: %s" % exc)

    if MARKER not in done.stdout:
        return ClueResult(failed=True, error="no marker in output (exit code %s): %s"
                          % (done.returncode, done.stderr.strip()[:300]))
    payload = done.stdout.split(MARKER, 1)[1].strip()
    if not payload:  # none of the watched tests crashed: nothing to report
        return ClueResult()
    try:
        data = json.loads(payload)
    except ValueError as exc:
        return ClueResult(failed=True, error="unreadable plugin output: %s" % exc)
    if "plugin_error" in data:
        return ClueResult(failed=True, error="plugin error: " + data["plugin_error"])
    return ClueResult(text=format_clue(data, bug, function_start))


if __name__ == "__main__":
    import sys

    bug = load_bug(sys.argv[1])
    path = REPO_ROOT / (sys.argv[2] if len(sys.argv) > 2 else bug["buggy_file"])
    print(runtime_clue(bug, path))