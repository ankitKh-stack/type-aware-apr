# Decisions

> Path note (2026-11-07): `harness/` was renamed to `src/` today because A3 §9 requires a top-level `src/` and forbids other folder names. The older entries below were rewritten to use `src/` (and `python -m src.NAME`, `from src.x import ...`). Entries written before the rename mean the same code. The last entry records the rename.

## 2026-10-15 Harness Python
- Harness runs on Python 3.14.4 on Ubuntu and 3.14.6 on Windows. A2 §7 says 3.14.8: update A2 to note both versions (3.14.4 Ubuntu, 3.14.6 Windows). The code runs the same on both.
- Revisit if the instructor's machine differs; pin package versions in `requirements.txt` before the final hand-in.
- Each bug runs in its own Python inside Docker (e.g. requests-3179 uses 3.5.9 via pyenv).

## 2026-11-03 LLM model and settings
- API model name: `deepseek-flash`, served by DeepSeek-V4.1-Flash-1017 (A2's "DeepSeek V4.1 Flash").
- Non-thinking mode: every call sends `extra_body={"thinking": {"type": "disabled"}}`.
  Thinking mode is on by default and ignores `temperature`.
- temperature = 1.0, max_tokens = 2000 on every call.
- Implemented in `src/llm_interface.py` (task 1.9, see below): request timeout 60 s, 3 retries.

## 2026-11-03 Pricing (USD per 1M tokens, deepseek-flash)
| | Off-peak | Peak |
|---|---|---|
| Input, cache hit | 0.003 | 0.006 |
| Input, cache miss | 0.15 | 0.30 |
| Output | 0.60 | 1.20 |
- Peak: 01:00–04:00 and 06:00–10:00 UTC, Mon–Fri. Weekends are off-peak.
- Cost per call uses the rate for that call's timestamp (A2 §14 formula needs updating). Implemented in `src/llm_interface.py`; cost is computed in USD.
- Plan: run the main experiment off-peak.
- Budget currency (decided 2026-11-06): the budget is 50 CAD, as in A2. DeepSeek prices stay in USD, so converting to CAD needs an exchange rate (not yet chosen).

## 2026-11-03 Plausible patch rule (changes A2 §2/§14)
- Some tests fail even with the developer's fix (e.g. requests-3179: test_pyopenssl_redirect
  fails on an expired certificate; test_conflicting_post_params fails because the test uses
  old pytest syntax).
- Rule: a patch is plausible if (1) the bug-exposing tests pass and (2) no test fails
  that passes with the developer's fix.
- The Bug Validator records each bug's "already failing" tests from the fixed version.
- The classifier checks bug-exposing tests by name, never just "TypeError appeared".

## 2026-11-05 Stage 1 is done by both partners, then the tracks split
- Ankit builds the real version in `src/` on `main`. It is the reference version.
- Pravesh builds their own version in `practice/pravesh/` on their own branch, branched from `main` at commit `2f1287a`. It is not merged into `src/` unless decided otherwise.
- After stage 1: Ankit = Track A (bugs and environments, clue extractors), Pravesh = Track B (pipeline and LLM).

## 2026-11-06 Test runner: one fresh container per test run
- Each run mounts the buggy or patched `models.py` read-only over the one in the `pyter` image, so the image is never modified.
- The container prints JUnit XML to stdout (after the marker `===JUNIT===`), so the container writes nothing into the repo.
- Why: clean state per attempt (A2 §5), and XML is sturdier to parse than pytest's text.

## 2026-11-06 Timeout stays at 30 s (A2)
- Measured: the full TestRequests run takes about 4 to 5 s including Docker startup (Ubuntu and Windows), so 30 s leaves about 6x headroom.
- A timed-out run is stopped with `docker kill` by container name.

## 2026-11-06 Exit code is not pytest's exit code
- The container script ends with `cat` of the XML, so the exit code is 0 even when tests fail.
- Test results come from the XML only. A non-zero exit code or a missing XML means INFRA_ERROR (see the classifier labels below).

## 2026-11-06 Tests identified by name, failures compared by error message
- Two of the four failing tests contain a TypeError that has nothing to do with the bug.
- SAME_FAILURE compares the error message of each bug-exposing test with the original, never the traceback (the traceback has memory addresses that change on every run).

## 2026-11-06 Result Classifier labels (task 1.5)
- Five labels, decided in this order: PASS, SAME_FAILURE, NEW_FAILURE, TIMEOUT, INFRA_ERROR.
- PASS needs every bug-exposing test to pass AND every test in `baseline.json` to still pass. A baseline test missing from the results (for example, the module no longer imports) counts as failing.
- INFRA_ERROR means no usable JUnit XML (marker missing or XML unparsable). TIMEOUT means the run timed out.
- Verified on Ubuntu and Windows: the developer fix gives PASS, the buggy code gives SAME_FAILURE, a patch that raises RuntimeError gives NEW_FAILURE, and fake results give TIMEOUT and INFRA_ERROR.

## 2026-11-06 Bug validity check (task 1.4)
- A bug is usable only if every bug-exposing test fails with a TypeError on the buggy code and passes with the developer fix.
- The tests that pass with the fix are the baseline for the PASS rule (applies the plausible-patch rule above; see the classifier labels below).

## 2026-11-06 `baseline.json` is committed
- Location: `bugs/<id>/baseline.json`. Holds `original_errors` (test name to original error message) and `baseline_passing` (names of tests that pass with the fix).
- Generated by `python3 -m src.validator`.
- Why: it is an input to the classifier, it is small, and every machine gets the same one without rerunning the fixed code.
- requests-3179: 133 tests in the baseline (132 passed and 1 xpassed); 2 unrelated tests fail even with the fix.

## 2026-11-06 `src` is a package
- Run modules from the repo root with `python3 -m src.NAME` (Windows: `python -m src.NAME`).
- Import with `from src.x import ...`.

## 2026-11-06 Line endings
- LF everywhere except `.bat` files, which are CRLF (`.gitattributes` enforces the `.bat` rule).
- Files written by the harness use `newline="\n"` so Windows writes the same bytes as Ubuntu (checked: `baseline.json` is identical on both).

## 2026-11-06 Response parser (task 1.6)
- `src/ast_tools.py` holds the shared helpers: `parse_source` (ignores SyntaxWarning from old docstrings) and `find_function(tree, class_name, function_name)`.
- `src/response_parser.py` takes the first python code block of a model answer (language python, py, python3, or none).
  - No block or an empty block: INVALID_OUTPUT. A SyntaxError: SYNTAX_ERROR. A changed parameter list: SIGNATURE_VIOLATION (compares `ast.dump` of the args).
  - These invalid outputs skip test execution but still count as a try (A2).
- The answer is dedented first, so an indented method is accepted, and the function is returned dedented.
- The model answer is the text after `## Response` in attempt files, not the whole file, because the prompt also contains a python block.

## 2026-11-06 Patch applier (task 1.7)
- `src/patch_applier.py` replaces the old function by ast line numbers, starting at the first decorator line if there are decorators.
- It re-indents the parsed function to the original column and writes to a fresh file under `work/` (`work/` is gitignored).

## 2026-11-06 Prompts (task 1.8)
- `src/prompts.py` holds the A2 §6.2 templates.
- The C1 prompt matches the manual `attempt_C1.md` text exactly, with the test shown as the full path built from `test_command`.
- System message: "You are an Automated Program Repair tool."
- Feedback exists for SAME_FAILURE, NEW_FAILURE and the invalid categories. TIMEOUT and INFRA_ERROR had no template when this was written (TIMEOUT is decided in the loop section below).

## 2026-11-06 LLM interface (task 1.9)
- `src/llm_interface.py`: model `deepseek-flash`, temperature 1.0, max_tokens 2000, thinking disabled (see LLM settings above).
- Request timeout 60 s (our choice; A2 gives no number).
- Up to 3 retries with delays of 2, 4 and 8 s on network, timeout, rate-limit and server errors. openai's own retries are turned off.
- An authentication error is not retried and stops the program.
- If retries run out, the call returns text `None` and an error.
- Cost is in USD using the peak/off-peak table above; CAD conversion is still undecided.

## 2026-11-06 Logger (task 1.10)
- `src/logger.py` writes per-attempt folders `results/<run_id>/trial_<k>/call_<n>/`, a readable `run.log`, and `results/<run_id>.jsonl`.
- The whole `results/` folder is gitignored. Sample runs get copied into `examples/` on purpose later.

## 2026-11-06 Windows: use `python -m pip`
- Windows has two Pythons (Store 3.13 and 3.14.6). Bare `pip` installs into the wrong one.
- All install steps use `python -m pip`, including `setup.bat` later.

## 2026-11-06 Experiment loop rules (task 1.11)
- The conversation restarts after 3 exchanges. A trial stops at a plausible patch or 10 counted calls.
- INFRA_ERROR does not count. 3 infra errors in a trial stop it as infra_failure. A Docker infra error is retried once.
- A PASS is rerun 3 more times. A failing rerun gives that rerun's category.
- TIMEOUT feedback (Ankit's choice, not in A2): "The fixed version is still not correct. The tests took too long to finish (over 30 seconds)."
- NEW_FAILURE feedback names the first failing test (bug-exposing, or one that passes with the fix) in the test results order.
- "Plausible" only means the tests pass; correctness is for human review.

## Observations (not decisions; revisit when real runs answer them)
- Stray tokens (task 1.9): two short test calls returned stray tokens at the end of the text (e.g. "Hello! I全国助残日"). The code passes content through unchanged. Watch whether real code answers stay clean.
- First-block rule (task 1.11): A2's first-python-block rule cost one try in trial 1. The answer showed a one-line snippet before the full function, which gave SYNTAX_ERROR. We keep A2's rule for now.
- First real run: 3 C1 trials on requests-3179, all plausible, total cost about 0.00096 USD.

## 2026-11-06 Stage 2 Track A: runtime clue collector
- The runtime type collector runs as a separate small container run after a failed attempt (as A2 says), not inside the normal test run. Why: C0 and C1 runs stay untouched, and it costs about one extra 5 s run per failed patch.
- The runtime clue records the locals plus every name and attribute chain on the failing line (for example `self.content`, `self.encoding`), not only locals (changes A2 §6.2). Why: for requests-3179 the useful facts are attributes, not locals.
- Clue extractors live in new files (`src/clue_static.py`, `src/clue_runtime.py`) so they don't conflict with Pravesh's `run.py` and `prompts.py` work.
- API: `runtime_clue(bug, models_path, test_names=None)` in `src/clue_runtime.py` returns the same `ClueResult(text, failed, error)`. `test_names` defaults to the bug-exposing tests; Pravesh can pass the failing test named in feedback.
- How it runs: a pytest plugin `src/plugins/rt_collector.py` (Python 3.5 compatible), mounted read-only at `/opt/apr` and loaded with `-p rt_collector` in a separate fresh container run (same 30 s timeout, `docker kill` on timeout; Ankit's choice). It records the first watched test that fails, with any exception type, because a patched version can fail differently.
- Frames: the innermost frame inside the project plus the buggy function's frame if different. Per frame: locals (max 10, skipping modules, classes, callables) plus every name and attribute chain on the failing line (max 10), values cut to 60 characters.
- Text format: `in json (requests/models.py), line 7: self: Response = <Response [0]>, kwargs: dict = {}, self.encoding: NoneType = None, self.content: NoneType = None`. Line numbers are relative to the buggy function; in any other function they are the file line. All locals are kept (including `self`) so the clue is not hand-tuned; revisit after more bugs.
- Failure cases return `failed=True` (no marker, timeout, plugin error, unreadable output).
- Checked: on requests-3179 the buggy file gives the clue above and the fixed file gives empty text, identical on Ubuntu and Windows.

## 2026-11-06 Stage 2 Track A: static clue (mypy runner)
- API: `static_clue(bug, source_path)` in `src/clue_static.py` returns `ClueResult(text, failed, error)` from `src/clues.py`. Empty text means nothing to report. `failed=True` means mypy crashed, timed out or the function was not found (A2 §8 tool-failure flag).
- mypy runs on the host with `--check-untyped-defs --ignore-missing-imports --follow-imports=skip` and a 30 s timeout (our choice). It keeps only `error` lines inside the target function's line range (decorators included), recomputed on every patched file.
- Line numbers in clues are relative to the function (line 1 = its first line, the decorator if there is one), because the model sees only the function (Ankit's choice; A2's example "line 4" is ambiguous). mypy's `[code]` suffix is stripped to match A2's example.
- `mypy==2.4.0` is added to `requirements.txt`. Test fixture: `tests/fixtures/toy/shop.py`.

## 2026-11-07 `harness/` renamed to `src/` (A3 layout) (commit 2a36499)
- A3 §9 requires a top-level `src/` and says not to substitute other folder names, so `harness/` became `src/`. Run modules with `python -m src.NAME`; import with `from src.x import ...`.
- The rest of the A3 layout was added in the same pass:
  - `prompts/`: prompt text moved out of `src/prompts.py` into `prompts/*.txt`, loaded by `load_template`. Verified byte-identical output for `build_prompt`, `build_feedback` and the system prompt.
  - `config/model_config.json`: model, base_url, temperature, max_tokens, timeout, retries, thinking and prices; read by `src/llm_interface.py`.
  - `experiments/practice/`: `hello_llm`, `manual_attempt`, `apply_patch`.
  - `examples/*` and `feedback/`: empty placeholders.
  - `notes/toy` removed as a duplicate of `tests/fixtures/toy`.
- Why now: Pravesh had not started Track B, so one move was cheapest.
- Verified on Ubuntu and Windows (validator, clues, real C1 trial PASS).
