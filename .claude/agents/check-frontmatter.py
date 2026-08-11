#!/usr/bin/env python3
"""Validate agent-markdown frontmatter in this directory.

Broken frontmatter fails SILENTLY: the project agent doesn't register and the
built-in (or default model) runs instead. Run this after any edit to *.md here:

    python3 .claude/agents/check-frontmatter.py
"""
import re
import sys
from pathlib import Path

REQUIRED = ("name", "description")
KNOWN = {"name", "description", "model", "effort", "color", "tools", "disallowedTools"}

failures = 0
agents_dir = Path(__file__).parent

for md in sorted(agents_dir.glob("*.md")):
    problems = []
    text = md.read_text()
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        problems.append("missing or unterminated frontmatter block (needs opening AND closing '---' lines)")
        fields = {}
    else:
        fields = {}
        for line in m.group(1).splitlines():
            km = re.match(r"^([A-Za-z]+):\s*(.*)$", line)
            if not km:
                problems.append(f"unparseable frontmatter line: {line!r}")
                continue
            key, val = km.group(1), km.group(2)
            fields[key] = val
            if key not in KNOWN:
                problems.append(f"unknown key {key!r}")
            # An unquoted value containing ': ' is an invalid YAML plain scalar.
            if val and val[0] not in "\"'" and ": " in val:
                problems.append(f"{key}: value contains unquoted ': ' — wrap the whole value in double quotes")
            if val and val[0] in "\"'" and (len(val) < 2 or val[-1] != val[0]):
                problems.append(f"{key}: quoted value has no matching closing quote")
        for req in REQUIRED:
            if req not in fields:
                problems.append(f"missing required key {req!r}")

    if problems:
        failures += 1
        print(f"FAIL {md.name}")
        for p in problems:
            print(f"  - {p}")
    else:
        print(f"ok   {md.name} (model: {fields.get('model', '<default>')})")

sys.exit(1 if failures else 0)
