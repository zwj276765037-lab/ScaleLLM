#!/usr/bin/env python3
"""Exhaustive proposed CE/data equation check, not RTL implementation signoff."""
import itertools
import json
from pathlib import Path

cases = 0
for g, push, pop, empty, full, old_head, old_tail, incoming in itertools.product((0, 1), repeat=8):
    expected_head, expected_tail = old_head, old_tail
    if g:
        if push and not pop:
            if empty:
                expected_head = incoming
            else:
                expected_tail = incoming
        elif pop and not push:
            if full:
                expected_head = old_tail
        elif push and pop:
            expected_head = incoming
    head_ce = g and ((push and not pop and empty) or (not push and pop and full) or (push and pop))
    tail_ce = g and push and not pop and not empty
    head_data = old_tail if not push and pop and full else incoming
    actual_head = head_data if head_ce else old_head
    actual_tail = incoming if tail_ce else old_tail
    assert (actual_head, actual_tail) == (expected_head, expected_tail)
    cases += 1

for value in (0, 1):
    assert (0b10 >> value) & 1 == value

result = {
    "execution": "exhaustive scalar next-state formula and LUT1 identity check completed",
    "formula_cases": cases,
    "LUT1_identity_cases": 2,
    "verdict": "proposed CE/data equations equal current case-assignment semantics for every tested Boolean combination",
    "applicability": "all g/push/pop/empty/full and one-bit old/input combinations, including unreachable combinations; pointwise extension to each payload bit",
    "limitations": [
        "Reference is independently transcribed from current RTL case semantics; this is not simulation of a modified RTL implementation.",
        "No new count/ready/valid state logic is introduced by this proposal; implementation must preserve those signals and original update logic.",
        "LUT1 combinational identity proves no logical cycle delay; its physical propagation delay remains a timing cost."
    ]
}
target = Path(__file__).with_name("M2_equation_check.json")
with target.open("x") as stream:
    json.dump(result, stream, indent=2)
    stream.write("\n")
print(json.dumps(result))
