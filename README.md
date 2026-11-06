# type-aware-apr

Type-aware, LLM-based automated program repair (APR) for Python type errors.

> **Status:** early work in progress (course project, due November 30, 2026). This README will grow as the code does.

## What this project is

Python programs often crash with type errors (for example, adding an `int` to a `str`). This project tests whether giving an LLM **type clues** helps it repair those bugs better than a plain conversational repair loop.

The tool takes a real buggy Python project, runs its failing test, sends the bug to an LLM, applies the suggested patch, reruns the tests, and feeds the result back to the LLM for another try (up to 10 tries per run).

## Type clues

- **Runtime clue:** the actual types and values of local variables when the `TypeError` happens, collected while the failing test runs.
- **Static clue:** warnings from the `mypy` type checker for the buggy function.

## Experimental conditions

| Condition | What the LLM gets |
|-----------|-------------------|
| C0 | Single-shot reference: the same first prompt, up to 10 independent tries, no conversation |
| C1 | Baseline: conversational repair loop, no type clues |
| C2 | C1 + runtime clue |
| C3 | C1 + static clue |
| C4 | C1 + both clues |

Each bug and condition pair is run 3 times.

## Setup

- **Benchmark:** bugs from [PyTER](https://github.com/kupl/PyTER), run inside Docker so each bug gets the old Python version it needs.
- **LLM:** DeepSeek (`deepseek-flash`, thinking disabled). Exact model, pricing and other settings are recorded in `notes/decisions.md`.
- **Bug set:** TBD. The first bug being worked on is `requests-3179`.
- **Requirements:**
  - Windows: Python 3 for Windows (3.14 on both our machines), Docker Desktop and the `pyter` image. Nothing else (no bash, WSL or Unix tools).
  - Ubuntu/WSL: Python 3 (3.14), Docker and the `pyter` image.
  - About 20 GB of free disk space for the image (it is about 7.5 GB).
- **Install:**
  1. `pip install -r requirements.txt` (currently `openai` and `python-dotenv`).
  2. The `pyter` image: download the image `.tar` from the figshare link in the [PyTER README](https://github.com/kupl/PyTER), then run `docker import <downloaded-file>.tar pyter`.
  3. Check it worked: `docker images` should list a line starting with `pyter`.

## Layout

```
harness/   pipeline code (a Python package; run modules from the repo root with python3 -m harness.NAME)
bugs/      one JSON file per bug (bugs/requests-3179.json) plus a folder per bug
           (bugs/requests-3179/: models_buggy.py, models_fixed.py, baseline.json)
docker/    Dockerfiles
notes/     bug cards, decisions.md, meeting notes
results/   experiment logs
```

## How to run

Run everything from the repo root.

```
python3 -m harness.validator      (Windows: python -m harness.validator)
```

Runs requests-3179 on the buggy and the fixed file, checks the bug, and writes `bugs/requests-3179/baseline.json` (the original errors and the tests that pass with the fix).

```
python3 -m harness.classifier     (Windows: python -m harness.classifier)
```

Runs requests-3179 on the developer fix, the buggy code and the saved C1 answer, and prints the result for each (expected: PASS, SAME_FAILURE, PASS).
`run.bat` is added at the end of stage 1 (task 1.12).

Full run: TBD

## API key

The DeepSeek API key goes in a local `.env` file, which `.gitignore` already excludes. Never commit the key.

## Conventions

- Line endings: LF everywhere, except `.bat` files, which must be CRLF. `.gitattributes` enforces the `.bat` rule. In VS Code, check the bottom-right corner says LF (CRLF for `.bat`).
- Paths: use `pathlib.Path`, relative to the repo root in config files. No hard-coded `/home/...` or `C:\...`.
- Open files with `encoding="utf-8"`. Run programs as a list with `subprocess.run`, never `shell=True`.

## Authors

- Ankit (ankitKh-stack)
- Pravesh (pravesh500)
