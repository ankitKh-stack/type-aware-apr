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

## Planned layout

```
harness/   pipeline code
bugs/      bug metadata and filter output
docker/    Dockerfiles
notes/     bug cards, decisions.md, meeting notes
results/   experiment logs
```

## How to run

TBD.

## API key

The DeepSeek API key goes in a local `.env` file, which `.gitignore` already excludes. Never commit the key.

## Authors

- Ankit
- Pravesh
