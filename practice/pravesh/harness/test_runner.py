"""1.2 Sandboxed Test Runner.

Runs a bug's tests in a brand-new Docker container, with a given file
from the laptop mounted (read-only) over the bug's target file.
"""
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

# This file is <repo>/practice/pravesh/harness/test_runner.py,
# so the repo root is three folders up.
ROOT = Path(__file__).resolve().parents[3]

TIMEOUT_SECONDS = 30          # per-run limit from the design (A2)
JUNIT_MARKER = "===JUNIT==="  # separates pytest's text output from the XML


def load_bug(bug_id):
    """Read bugs/<bug_id>.json from the repo root."""
    path = ROOT / "bugs" / f"{bug_id}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _to_text(value):
    """TimeoutExpired can hand back bytes or None; always return a string."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_tests(bug, target_path, timeout=TIMEOUT_SECONDS):
    """Run the bug's tests with target_path in place of the target file.

    Returns a dict: exit_code, stdout, stderr, elapsed_seconds, timed_out.
    """
    target_path = Path(target_path).resolve()        # C:\... on Windows, /home/... in WSL
    container_target = f"{bug['workdir']}/{bug['target_file']}"
    name = "apr-test-" + uuid.uuid4().hex[:12]        # unique name, so we can kill it

    # This script runs INSIDE the Linux container, so bash is allowed here.
    inner_script = "; ".join(bug["env_setup"]) + "; " + (
        f"cd {bug['workdir']} && "
        f"{bug['test_command']} -q -p no:cacheprovider --junitxml=/tmp/r.xml; "
        "rc=$?; "                                     # remember pytest's exit code
        f"echo {JUNIT_MARKER}; cat /tmp/r.xml; "
        "exit $rc"
    )

    command = [
        "docker", "run", "--rm", "--name", name,
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "LANG=C.UTF-8",
        "--mount", f"type=bind,source={target_path},target={container_target},readonly",
        bug["image"],
        "bash", "-c", inner_script,
    ]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        exit_code, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        # Killing only the client would leave the container running.
        subprocess.run(["docker", "kill", name], capture_output=True)
        exit_code, stdout, stderr, timed_out = None, _to_text(e.stdout), _to_text(e.stderr), True
    elapsed = time.monotonic() - start

    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "elapsed_seconds": round(elapsed, 2),
        "timed_out": timed_out,
    }


if __name__ == "__main__":
    # Manual check:  python practice/pravesh/harness/test_runner.py <bug_id> <file>
    # <file> may be relative to the repo root, e.g. bugs/requests-3179/models_buggy.py
    if len(sys.argv) != 3:
        sys.exit("Usage: python test_runner.py <bug_id> <path-to-target-file>")
    bug = load_bug(sys.argv[1])
    result = run_tests(bug, ROOT / sys.argv[2])

    text_part = result["stdout"].split(JUNIT_MARKER)[0].strip().splitlines()
    print("exit code :", result["exit_code"])
    print("timed out :", result["timed_out"])
    print("elapsed   :", result["elapsed_seconds"], "s")
    print("summary   :", text_part[-1] if text_part else "(no output)")
    print("junit xml :", "yes" if JUNIT_MARKER in result["stdout"] else "MISSING")
    if JUNIT_MARKER not in result["stdout"]:
        print("--- docker said ---\n" + (result["stderr"] or result["stdout"]).strip())