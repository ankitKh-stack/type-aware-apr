"""pytest plugin: record variable types at the point a test crashed (A2 section 4, C2/C4).

Runs INSIDE the bug's container, on the bug's old Python (3.5.9 for requests-3179),
so this file must stay Python 3.5 compatible: no f-strings, no variable annotations.

Settings come from environment variables:
  APR_RT_OUT              file to write the JSON result to
  APR_TEST_NAMES          comma-separated test function names to watch
  APR_TARGET_FILE         path of the buggy file, relative to the project (e.g. requests/models.py)
  APR_TARGET_FUNCTION     name of the buggy function
It writes the file once, for the first watched test that fails. If the plugin itself
breaks it writes {"plugin_error": ...} and never makes pytest fail.
"""
import inspect
import json
import os
import re
import linecache
import traceback

MAX_REPR = 60
MAX_LOCALS = 10
MAX_CHAINS = 10
CHAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")

_state = {"root": "", "done": False}


def pytest_configure(config):
    _state["root"] = os.path.abspath(str(config.rootdir))


def _short_repr(value):
    try:
        text = repr(value)
    except Exception:
        return "<unprintable>"
    text = text.replace("\n", "\\n").replace("\r", "\\r")
    if len(text) > MAX_REPR:
        text = text[:MAX_REPR - 3] + "..."
    return text


def _is_noise(value):
    return inspect.ismodule(value) or inspect.isclass(value) or callable(value)


def _entry(name, value):
    return [name, type(value).__name__, _short_repr(value)]


def _resolve(frame, chain):
    parts = chain.split(".")
    if parts[0] in frame.f_locals:
        value = frame.f_locals[parts[0]]
    elif parts[0] in frame.f_globals:
        value = frame.f_globals[parts[0]]
    else:
        return None, False
    for part in parts[1:]:
        try:
            value = getattr(value, part)
        except Exception:
            return None, False
    return value, True


def _frame_variables(frame, lineno):
    code = frame.f_code
    names = list(code.co_varnames) + [n for n in sorted(frame.f_locals) if n not in code.co_varnames]
    variables = []
    for name in names:
        if name.startswith("__") or name not in frame.f_locals:
            continue
        value = frame.f_locals[name]
        if _is_noise(value):
            continue
        variables.append(_entry(name, value))
        if len(variables) >= MAX_LOCALS:
            break
    try:
        line = linecache.getline(code.co_filename, lineno)
    except Exception:
        line = ""
    seen = set()
    chains = 0
    for chain in CHAIN.findall(line):
        parts = chain.split(".")
        for end in range(2, len(parts) + 1):
            text = ".".join(parts[:end])
            if text in seen:
                continue
            seen.add(text)
            value, found = _resolve(frame, text)
            if found and not _is_noise(value) and chains < MAX_CHAINS:
                variables.append(_entry(text, value))
                chains += 1
    return variables


def _record(frame, lineno, root, role):
    filename = os.path.abspath(frame.f_code.co_filename)
    if filename.startswith(root + os.sep):
        filename = filename[len(root) + 1:]
    return {
        "role": role,
        "function": frame.f_code.co_name,
        "file": filename.replace(os.sep, "/"),
        "line": lineno,
        "vars": _frame_variables(frame, lineno),
    }


def _collect(excinfo):
    root = _state["root"]
    target_file = os.environ.get("APR_TARGET_FILE", "").replace("/", os.sep)
    target_function = os.environ.get("APR_TARGET_FUNCTION", "")
    frames = []
    tb = excinfo.tb
    while tb is not None:
        frames.append((tb.tb_frame, tb.tb_lineno))
        tb = tb.tb_next
    innermost = None
    target = None
    for frame, lineno in frames:
        filename = os.path.abspath(frame.f_code.co_filename)
        if filename.startswith(root + os.sep) and "site-packages" not in filename:
            innermost = (frame, lineno)
        if target_file and filename.endswith(os.sep + target_file) and frame.f_code.co_name == target_function:
            target = (frame, lineno)
    records = []
    if innermost is not None:
        records.append(_record(innermost[0], innermost[1], root, "raising"))
    if target is not None and (innermost is None or target[0] is not innermost[0]):
        records.append(_record(target[0], target[1], root, "target"))
    return {"exception": excinfo.typename, "frames": records}


def _write(data):
    out = os.environ.get("APR_RT_OUT")
    if out:
        with open(out, "w") as handle:
            handle.write(json.dumps(data))


def pytest_exception_interact(node, call, report):
    if _state["done"]:
        return
    try:
        names = [n for n in os.environ.get("APR_TEST_NAMES", "").split(",") if n]
        if getattr(node, "name", None) not in names or call.excinfo is None:
            return
        _state["done"] = True
        _write(_collect(call.excinfo))
    except Exception:
        _state["done"] = True
        try:
            _write({"plugin_error": traceback.format_exc()[-500:]})
        except Exception:
            pass