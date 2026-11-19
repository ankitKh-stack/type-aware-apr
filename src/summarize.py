"""B5: summarise an experiment, per condition (A2 §14).

For each condition: runs, plausible rate, and the average calls, wall-clock time
(and its LLM and test parts), tokens and cost per run. Then a projection of
the main experiment's cost and time from those averages.

Usage:  python -m src.summarize <experiment id> [--bugs-n 12] [--trials-n 3]
Writes summary.json into the experiment's folder.
"""
import argparse
import json
import sys
from statistics import mean

from src.experiment import CONFIG_PATH, EXPERIMENTS_DIR, load_progress, unit_key, write_json
from src.logger import RESULTS_DIR


def read_attempts(run_id):
    """The per-call records of one run, from results/<run_id>.jsonl."""
    path = RESULTS_DIR / f"{run_id}.jsonl"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    return [r for r in records if r.get("type") == "attempt"]


def measure(record):
    """The numbers for one unit (one bug x condition x trial)."""
    attempts = read_attempts(record["run_id"])
    return {
        "plausible": record["outcome"] == "plausible",
        "calls": record["calls_used"],
        "wall_s": record.get("wall_seconds"),
        "llm_s": sum(a.get("latency_s") or 0 for a in attempts),
        "test_s": sum(a.get("test_seconds") or 0 for a in attempts),
        "tokens_hit": sum(a.get("input_cache_hit_tokens", 0) for a in attempts),
        "tokens_miss": sum(a.get("input_cache_miss_tokens", 0) for a in attempts),
        "tokens_out": sum(a.get("output_tokens", 0) for a in attempts),
        "cost_usd": record["cost_usd"],
    }


def avg(values):
    values = [v for v in values if v is not None]
    return mean(values) if values else None


def fmt(value, digits=1):
    return "-" if value is None else f"{value:.{digits}f}"


def main():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment_id")
    parser.add_argument("--bugs-n", type=int, default=12, help="bugs in the main experiment")
    parser.add_argument("--trials-n", type=int, default=config["trials"], help="trials per bug and condition")
    args = parser.parse_args()

    folder = EXPERIMENTS_DIR / args.experiment_id
    if not (folder / "plan.json").exists():
        found = sorted(p.name for p in EXPERIMENTS_DIR.iterdir()) if EXPERIMENTS_DIR.exists() else []
        sys.exit(f"No experiment '{args.experiment_id}'. Experiments found: {', '.join(found) or 'none'}")
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))

    # Keep the latest record per unit, so a rerun replaces its infra failure.
    latest = {}
    for record in load_progress(folder):
        latest[unit_key(record)] = record

    by_condition = {}
    for record in latest.values():
        by_condition.setdefault(record["condition"], []).append(measure(record))

    rows = {}
    header = (f"{'cond':5}{'runs':>5}{'plaus%':>8}{'calls':>7}{'wall s':>8}{'llm s':>8}"
              f"{'test s':>8}{'tok in':>9}{'tok out':>9}{'cost USD':>11}")
    print(f"experiment {plan['experiment_id']}   bugs: {', '.join(plan['bugs'])}"
          + ("   (FAKE LLM)" if plan.get("fake_llm") else ""))
    print(header)
    print("-" * len(header))
    for condition in sorted(by_condition):
        m = by_condition[condition]
        row = {
            "runs": len(m),
            "plausible_rate": 100 * sum(x["plausible"] for x in m) / len(m),
            "avg_calls": avg(x["calls"] for x in m),
            "avg_wall_s": avg(x["wall_s"] for x in m),
            "avg_llm_s": avg(x["llm_s"] for x in m),
            "avg_test_s": avg(x["test_s"] for x in m),
            "avg_tokens_in": avg(x["tokens_hit"] + x["tokens_miss"] for x in m),
            "avg_tokens_out": avg(x["tokens_out"] for x in m),
            "avg_cost_usd": avg(x["cost_usd"] for x in m),
        }
        rows[condition] = row
        print(f"{condition:5}{row['runs']:>5}{row['plausible_rate']:>8.0f}{fmt(row['avg_calls']):>7}"
              f"{fmt(row['avg_wall_s']):>8}{fmt(row['avg_llm_s']):>8}{fmt(row['avg_test_s']):>8}"
              f"{fmt(row['avg_tokens_in'], 0):>9}{fmt(row['avg_tokens_out'], 0):>9}"
              f"{fmt(row['avg_cost_usd'], 6):>11}")

    # Projection for the main experiment
    runs_per_condition = args.bugs_n * args.trials_n
    cost = sum((r["avg_cost_usd"] or 0) * runs_per_condition for r in rows.values())
    hours = sum((r["avg_wall_s"] or 0) * runs_per_condition for r in rows.values()) / 3600
    usd_per_cad = plan["usd_per_cad"]
    print(f"\nProjection for {args.bugs_n} bugs x {args.trials_n} trials x {len(rows)} conditions "
          f"= {runs_per_condition * len(rows)} runs:")
    print(f"  cost  about {cost:.4f} USD = {cost / usd_per_cad:.4f} CAD "
          f"(budget {plan['budget_cad']} CAD)")
    print(f"  time  about {hours:.1f} hours of running")
    print("  These averages come from requests-3179 only if that is the only bug run; "
          "harder bugs need more calls.")

    write_json(folder / "summary.json", {
        "experiment_id": plan["experiment_id"], "bugs": plan["bugs"],
        "fake_llm": plan.get("fake_llm"), "per_condition": rows,
        "projection": {"bugs": args.bugs_n, "trials": args.trials_n,
                       "runs": runs_per_condition * len(rows),
                       "cost_usd": cost, "cost_cad": cost / usd_per_cad, "hours": hours},
    })
    print("Saved", (folder / "summary.json").relative_to(EXPERIMENTS_DIR.parent.parent))


if __name__ == "__main__":
    main()