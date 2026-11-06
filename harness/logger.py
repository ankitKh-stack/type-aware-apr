import json
from datetime import datetime, timezone

from harness.test_runner import REPO_ROOT

RESULTS_DIR = REPO_ROOT / "results"


def new_run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RunLogger:
    def __init__(self, run_id=None):
        self.run_id = run_id or new_run_id()
        self.run_dir = RESULTS_DIR / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = RESULTS_DIR / f"{self.run_id}.jsonl"
        self.log_path = self.run_dir / "run.log"

    def call_dir(self, trial, call):
        path = self.run_dir / f"trial_{trial}" / f"call_{call}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_text(self, folder, name, text):
        with open(folder / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def save_json(self, folder, name, obj):
        self.save_text(folder, name, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")

    def log(self, step, result):
        with open(self.log_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"{_utc_now()}  {step}  {result}\n")

    def append_record(self, record):
        with open(self.jsonl_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    logger = RunLogger("selftest")
    folder = logger.call_dir(1, 1)
    logger.save_json(folder, "01_failure_record.json", {"test_name": "demo", "note": "naïve é"})
    logger.save_text(folder, "04_response_raw.txt", "line one\nline two\n")
    logger.log("llm_call", "ok")
    logger.log("classify", "SAME_FAILURE")
    logger.append_record({"type": "attempt", "trial": 1, "call": 1, "category": "SAME_FAILURE"})
    logger.append_record({"type": "run", "outcome": "unsolved"})
    print("run dir:", logger.run_dir)
    for path in sorted(logger.run_dir.rglob("*")):
        print("  ", path.relative_to(logger.run_dir))
    print("--- run.log ---")
    print((logger.log_path).read_text(encoding="utf-8"), end="")
    print("--- jsonl ---")
    print(logger.jsonl_path.read_text(encoding="utf-8"), end="")