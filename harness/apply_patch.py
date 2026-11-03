"""Splice an LLM's json() from attempt_C?.md into a copy of models_buggy.py.

Usage: python harness/apply_patch.py C1   -> writes notes/requests-3179/models_C1.py
"""
import os
import re
import sys
import textwrap

CONDITION = sys.argv[1] if len(sys.argv) > 1 else ""
BUG_DIR = "notes/requests-3179"
FIRST_LINE, LAST_LINE = 789, 812  # json() in models_buggy.py
INDENT = "    "  # json() is a method, so it sits 4 spaces in

with open(os.path.join(BUG_DIR, f"attempt_{CONDITION}.md"), encoding="utf-8") as f:
    response = f.read().split("## Response", 1)[1]

blocks = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
if len(blocks) != 1:
    sys.exit(f"Expected 1 python code block, found {len(blocks)}")

new_function = textwrap.indent(textwrap.dedent(blocks[0]), INDENT)
if not new_function.lstrip().startswith("def json(self, **kwargs):"):
    sys.exit("The function name or parameters changed")

with open(os.path.join(BUG_DIR, "models_buggy.py"), encoding="utf-8") as f:
    lines = f.readlines()
lines[FIRST_LINE - 1:LAST_LINE] = [new_function]

out_path = os.path.join(BUG_DIR, f"models_{CONDITION}.py")
with open(out_path, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("Wrote", out_path)