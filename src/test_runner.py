import json
import subprocess
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_bug(bug_id):
    path = REPO_ROOT / "bugs" / f"{bug_id}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_docker_command(bug, models_path, container_name):
    mount = f"{Path(models_path).resolve()}:{bug['workdir']}/{bug['target_file']}:ro"
    inner = "; ".join(
        bug["env_setup"]
        + [
            f"cd {bug['workdir']}",
            f"{bug['test_command']} -q -p no:cacheprovider --junitxml=/tmp/r.xml",
            "echo ===JUNIT===",
            "cat /tmp/r.xml",
        ]
    )
    return [
        "docker", "run", "--rm", "--name", container_name,
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-e", "LANG=C.UTF-8",
        "-v", mount,
        bug["image"],
        "bash", "-c", inner,
    ]

def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_tests(bug, models_path, timeout=30):
    container_name = f"apr-test-{uuid.uuid4().hex[:8]}"
    cmd = build_docker_command(bug, models_path, container_name)
    start = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        subprocess.run(["docker", "kill", container_name], capture_output=True)
        exit_code = None
        stdout = _as_text(exc.stdout)
        stderr = _as_text(exc.stderr)
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "elapsed": time.monotonic() - start,
        "timed_out": timed_out,
    }


if __name__ == "__main__":
    bug = load_bug("requests-3179")
    result = run_tests(bug, REPO_ROOT / bug["buggy_file"])
    print("exit code:", result["exit_code"])
    print("elapsed:", round(result["elapsed"], 1), "s")
    print("timed out:", result["timed_out"])
    print("has JUnit XML:", "===JUNIT===" in result["stdout"])