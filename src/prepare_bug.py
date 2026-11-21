"""Stage 3 helper: build bugs/<id>.json, extract the buggy and fixed source file,
run the Bug Validator, and log the verdict.

Run from the repo root (Ubuntu, .venv active):
    python -m src.prepare_bug luigi-25

It never changes anything inside the pyter image. It only reads from it with
`docker run --rm pyter ...`.
"""
import ast
import difflib
import json
import subprocess
import sys

from src.ast_tools import parse_source
from src.test_runner import REPO_ROOT
from src.validator import _run_and_parse, save_baseline, validate_bug

IMAGE = "pyter"
ENV_SETUP = [
    "export PYENV_ROOT=/home/wonseok/.pyenv",
    'export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"',
]
LOG_PATH = REPO_ROOT / "bugs" / "stage3-log.jsonl"
FAIL = ("failed", "error")


def sh(script, binary=False):
    proc = subprocess.run(
        ["docker", "run", "--rm", IMAGE, "bash", "-c", script],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker command failed ({proc.returncode}): {script}\n"
            + "stderr: " + proc.stderr.decode("utf-8", "replace")
            + "\nstdout: " + proc.stdout.decode("utf-8", "replace")[:2000]
        )
    return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")


def lines(text):
    return [x for x in text.splitlines() if x.strip()]


def container_facts(bug_id):
    """Return workdir, source file, test file, bug-exposing hints, and the file texts."""
    if bug_id.startswith("requests-"):
        workdir = f"/pyter/benchmark/{bug_id}"
        sources = lines(sh(f"cd {workdir} && git diff --cached --name-only"))
        tests = lines(sh(f"cd {workdir} && git diff --name-only"))
        hinted = []
        if len(sources) != 1:
            return dict(workdir=workdir, sources=sources, tests=tests, hinted=hinted)
        src = sources[0]
        buggy = sh(f"cat {workdir}/{src}", binary=True)
        fixed = sh(f"cd {workdir} && git show HEAD:{src}", binary=True)
    elif bug_id.startswith("luigi-"):
        workdir = f"/pyter/BugsInPy/benchmark/{bug_id}"
        info = sh(f"cat {workdir}/bugsinpy_bug.info")
        fixed_commit = next(
            l.split('"')[1] for l in info.splitlines() if l.startswith("fixed_commit_id")
        )
        # PyTER's own test definitions: "pos" = the passing test file, "neg" = the
        # bug-exposing tests (PyTER moved them into *_test_neg.py files).
        spec = json.loads(sh("cat /pyter/pyter_tool/bugsinpy/pytest-luigi.json"))
        neg_ids = [a for key in (bug_id, bug_id + "-noassert") if key in spec
                   for a in spec[key]["neg"] if "::" in a]
        pos_files = [a for a in spec[bug_id]["pos"] if a.endswith(".py")]
        neg_files = sorted({a.split("::")[0] for a in neg_ids})
        tests = [" ".join(pos_files + neg_files)]  # neg file last, so its results win on a name clash
        hinted = sorted({a.split("::")[-1] for a in neg_ids})
        sources = lines(sh(
            f"cd {workdir} && git diff --name-only HEAD {fixed_commit} -- . ':!test' ':!tests'"
        ))
        if len(sources) != 1:
            return dict(workdir=workdir, sources=sources, tests=tests, hinted=hinted)
        src = sources[0]
        buggy = sh(f"cd {workdir} && git show HEAD:{src}", binary=True)
        fixed = sh(f"cd {workdir} && git show {fixed_commit}:{src}", binary=True)
    else:
        raise SystemExit(f"unknown bug id: {bug_id}")
    return dict(workdir=workdir, sources=sources, tests=tests, hinted=hinted,
                buggy=buggy, fixed=fixed)


def changed_buggy_lines(buggy_text, fixed_text):
    a, b = buggy_text.splitlines(), fixed_text.splitlines()
    changed = set()
    for tag, i1, i2, _, _ in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag in ("replace", "delete"):
            changed.update(range(i1 + 1, i2 + 1))
        elif tag == "insert":
            changed.update({i1, i1 + 1})
    return sorted(x for x in changed if x >= 1)


def find_targets(buggy_text, changed):
    """Outermost function or method (a direct child of the module or of a class) per changed line."""
    tree = parse_source(buggy_text)
    candidates = []
    for scope in [tree] + [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for node in scope.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls = scope.name if isinstance(scope, ast.ClassDef) else None
                candidates.append((cls, node.name, node.lineno, node.end_lineno))
    hits = []
    for line in changed:
        for cls, name, lo, hi in candidates:
            if lo <= line <= hi and (cls, name) not in hits:
                hits.append((cls, name))
    return hits


def log(entry):
    with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry) + "\n")


def main(bug_id):
    facts = container_facts(bug_id)
    if len(facts["sources"]) != 1 or len(facts["tests"]) < 1:
        reason = (f"fix touches {len(facts['sources'])} source files {facts['sources']}; "
                  f"test files {facts['tests']} (validator mounts exactly one source file)")
        print("EXCLUDED:", reason)
        log({"bug_id": bug_id, "valid": False, "exclusion_reason": reason})
        return
    src = facts["sources"][0]
    stem = src.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    bug_dir = REPO_ROOT / "bugs" / bug_id
    bug_dir.mkdir(parents=True, exist_ok=True)
    buggy_rel = f"bugs/{bug_id}/{stem}_buggy.py"
    fixed_rel = f"bugs/{bug_id}/{stem}_fixed.py"
    (REPO_ROOT / buggy_rel).write_bytes(facts["buggy"])
    (REPO_ROOT / fixed_rel).write_bytes(facts["fixed"])

    buggy_text = facts["buggy"].decode("utf-8", "replace")
    fixed_text = facts["fixed"].decode("utf-8", "replace")
    hits = find_targets(buggy_text, changed_buggy_lines(buggy_text, fixed_text))
    print("functions touched by the fix:", hits)
    if not hits:
        reason = "no function or method contains the changed lines (module-level change)"
        print("EXCLUDED:", reason)
        log({"bug_id": bug_id, "valid": False, "exclusion_reason": reason})
        return
    if len(hits) > 1:
        print("WARNING: the fix touches more than one function; using the first. Review this by hand.")
    target_class, target_function = hits[0]

    bug = {
        "id": bug_id,
        "image": IMAGE,
        "workdir": facts["workdir"],
        "target_file": src,
        "target_class": target_class,
        "target_function": target_function,
        "test_command": "pytest " + facts["tests"][0],
        "bug_exposing_tests": [],
        "env_setup": ENV_SETUP,
        "buggy_file": buggy_rel,
        "fixed_file": fixed_rel,
    }

    # Find the bug-exposing tests: fail on buggy code with a TypeError, pass with the fix.
    buggy_cases, p1 = _run_and_parse(bug, buggy_rel)
    fixed_cases, p2 = _run_and_parse(bug, fixed_rel)
    if p1 or p2:
        reason = "could not run the tests: " + (("buggy: " + p1) if p1 else ("fixed: " + p2))
        print("EXCLUDED:", reason)
        log({"bug_id": bug_id, "valid": False, "exclusion_reason": reason})
        return
    found = sorted(
        n for n, c in buggy_cases.items()
        if c["status"] in FAIL and c["message"].startswith("TypeError")
        and n in fixed_cases and fixed_cases[n]["status"] == "passed"
    )
    print("bug-exposing tests found (TypeError on buggy, pass on fixed):", found)
    if facts["hinted"]:
        print("bug-exposing tests named by PyTER (pytest-luigi.json):", facts["hinted"])
        if set(found) != set(facts["hinted"]):
            print("NOTE: the two lists differ. Using the PyTER names that I could confirm; check by hand.")
            found = sorted(set(found) & set(facts["hinted"])) or found
    if not found:
        reason = "no test fails with a TypeError on the buggy code and passes with the fix"
        print("EXCLUDED:", reason)
        log({"bug_id": bug_id, "valid": False, "exclusion_reason": reason,
             "buggy_failing": sorted(n for n, c in buggy_cases.items() if c["status"] in FAIL),
             "fixed_failing": sorted(n for n, c in fixed_cases.items() if c["status"] in FAIL)})
        return
    bug["bug_exposing_tests"] = found
    with open(REPO_ROOT / "bugs" / f"{bug_id}.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(bug, f, indent=2)
        f.write("\n")

    verdict = validate_bug(bug)
    # Flakiness check: two more runs must give identical results.
    keys = ("valid", "buggy_failing", "fixed_failing", "baseline_passing")
    for i in (2, 3):
        again = validate_bug(bug)
        if any(again[k] != verdict[k] for k in keys):
            diff = sorted(
                set(again["buggy_failing"]) ^ set(verdict["buggy_failing"])
                | set(again["fixed_failing"]) ^ set(verdict["fixed_failing"])
                | set(again["baseline_passing"]) ^ set(verdict["baseline_passing"])
            )
            verdict["valid"] = False
            verdict["exclusion_reason"] = f"flaky: run {i} differs from run 1 on tests {diff[:10]}"
            break
    print("valid:", verdict["valid"])
    print("exclusion reason:", verdict["exclusion_reason"])
    print("buggy failing:", len(verdict["buggy_failing"]), "fixed failing:", len(verdict["fixed_failing"]),
          "baseline passing:", len(verdict["baseline_passing"]))
    if verdict["valid"]:
        save_baseline(bug, verdict)
        print("saved baseline")
    log({"bug_id": bug_id, "valid": verdict["valid"],
         "exclusion_reason": verdict["exclusion_reason"],
         "bug_exposing_tests": bug["bug_exposing_tests"],
         "target": [target_class, target_function],
         "buggy_failing": verdict["buggy_failing"], "fixed_failing": verdict["fixed_failing"],
         "baseline_passing_count": len(verdict["baseline_passing"])})


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m src.prepare_bug <bug-id>")
    main(sys.argv[1])
