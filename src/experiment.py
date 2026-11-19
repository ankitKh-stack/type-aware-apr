"""B4: run a whole experiment, bugs x conditions x trials (A2 §16).

- For each trial and each bug, the conditions run in a random order,
  shuffled with a recorded seed, so the order can be reproduced.
- A running cost total stops the experiment cleanly at the budget cap (A2 §8).
- progress.jsonl gets one line per finished unit, so --resume skips finished work.
- Units that ended as infra_failure are rerun once at the end (A2 §16 step 6).

A "unit" is one bug x one condition x one trial: one call to run_trial.
State lives in results/experiments/<experiment id>/ (results/ is git-ignored).
"""
import argparse
import json
import random
import time
from datetime import datetime, timezone

from src.prompts import CONDITIONS
from src.run import build_context, run_trial
from src.test_runner import REPO_ROOT

CONFIG_PATH = REPO_ROOT / "config" / "experiment_config.json"
EXPERIMENTS_DIR = REPO_ROOT / "results" / "experiments"


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def unit_key(unit):
    return f"{unit['bug']}|{unit['condition']}|{unit['trial']}"


def make_schedule(bugs, conditions, trials, seed):
    """Every unit, in run order. For each trial and bug, conditions are shuffled.

    The shuffle is seeded by (seed, bug, trial), so the same settings always
    give the same order, on any machine.
    """
    schedule = []
    for trial in range(1, trials + 1):
        for bug in bugs:
            order = list(conditions)
            random.Random(f"{seed}:{bug}:{trial}").shuffle(order)
            for condition in order:
                schedule.append({"trial": trial, "bug": bug, "condition": condition})
    return schedule


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)


def load_progress(folder):
    path = folder / "progress.jsonl"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def append_progress(folder, record):
    with open(folder / "progress.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record) + "\n")


def run_unit(unit, fake_llm):
    """Run one bug x condition x trial and return its progress record."""
    start = time.monotonic()
    ctx = build_context(unit["bug"], unit["condition"], fake_llm)
    summary = run_trial(ctx, unit["trial"])
    return {**unit,
            "run_id": summary["run_id"],
            "outcome": summary["outcome"],
            "calls_used": summary["calls_used"],
            "cost_usd": summary["total_cost_usd"],
            "wall_seconds": round(time.monotonic() - start, 1),
            "finished_at": now_utc()}


def stop_for_budget(folder, plan, spent):
    write_json(folder / "stopped.json",
               {"reason": "budget", "spent_usd": spent,
                "budget_usd": plan["budget_usd"], "at": now_utc()})
    print(f"\nBudget reached: spent {spent:.6f} of {plan['budget_usd']:.6f} USD. Stopped cleanly.")
    print(f"Resume later with:  python -m src.experiment --resume {plan['experiment_id']}")


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    parser = argparse.ArgumentParser(description="Run bugs x conditions x trials.")
    parser.add_argument("--bugs", nargs="+", default=["requests-3179"])
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=config["conditions"])
    parser.add_argument("--trials", type=int, default=config["trials"])
    parser.add_argument("--seed", type=int, default=config["seed"])
    parser.add_argument("--budget-cad", type=float, default=None,
                        help="override the budget in config/experiment_config.json")
    parser.add_argument("--fake-llm", default=None)
    parser.add_argument("--resume", default=None, metavar="EXPERIMENT_ID")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the schedule and stop, without running anything")
    args = parser.parse_args()

    if args.resume:
        folder = EXPERIMENTS_DIR / args.resume
        plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
        print("resuming experiment", plan["experiment_id"])
    else:
        experiment_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        plan = {"experiment_id": experiment_id, "created_at": now_utc(),
                "seed": args.seed, "bugs": args.bugs, "conditions": args.conditions,
                "trials": args.trials, "budget_cad": config["budget_cad"],
                "usd_per_cad": config["usd_per_cad"], "fake_llm": args.fake_llm,
                "schedule": make_schedule(args.bugs, args.conditions, args.trials, args.seed)}
        folder = EXPERIMENTS_DIR / experiment_id

    if args.budget_cad is not None:
        plan["budget_cad"] = args.budget_cad
    plan["budget_usd"] = plan["budget_cad"] * plan["usd_per_cad"]

    if args.dry_run:
        for i, unit in enumerate(plan["schedule"], 1):
            print(f"{i:3}  trial {unit['trial']}  {unit['bug']}  {unit['condition']}")
        print(f"{len(plan['schedule'])} units, seed {plan['seed']}, "
              f"budget {plan['budget_cad']} CAD = {plan['budget_usd']:.2f} USD")
        return

    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "plan.json", plan)
    print("experiment id:", plan["experiment_id"])

    progress = load_progress(folder)
    done = {unit_key(r) for r in progress}
    spent = sum(r["cost_usd"] for r in progress)
    total = len(plan["schedule"])

    # Main pass
    for i, unit in enumerate(plan["schedule"], 1):
        if unit_key(unit) in done:
            continue
        if spent >= plan["budget_usd"]:
            stop_for_budget(folder, plan, spent)
            return
        print(f"\n=== unit {i}/{total}: trial {unit['trial']}  {unit['bug']}  {unit['condition']}")
        record = run_unit(unit, plan["fake_llm"])
        append_progress(folder, record)
        spent += record["cost_usd"]
        print(f"=== {record['outcome']}  calls={record['calls_used']}  "
              f"cost={record['cost_usd']:.6f}  total={spent:.6f} USD")

    # Rerun infrastructure failures once (A2 §16 step 6)
    latest = {}
    for r in load_progress(folder):
        latest[unit_key(r)] = r
    to_rerun = [r for r in latest.values()
                if r["outcome"] == "infra_failure" and not r.get("is_rerun")]
    for r in to_rerun:
        if spent >= plan["budget_usd"]:
            stop_for_budget(folder, plan, spent)
            return
        unit = {"trial": r["trial"], "bug": r["bug"], "condition": r["condition"]}
        print(f"\n=== rerun after infra failure: trial {unit['trial']}  {unit['bug']}  {unit['condition']}")
        record = run_unit(unit, plan["fake_llm"])
        record["is_rerun"] = True
        append_progress(folder, record)
        spent += record["cost_usd"]

    write_json(folder / "finished.json", {"at": now_utc(), "spent_usd": spent})
    print(f"\nExperiment {plan['experiment_id']} finished: {total} units, "
          f"spent {spent:.6f} USD ({spent / plan['usd_per_cad']:.4f} CAD).")
    print("Progress file:", (folder / "progress.jsonl").relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()