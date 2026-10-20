#!/usr/bin/env python3
"""Check literal proposed LUT INITs against the original sequential NBA rule."""
import itertools
import json
from pathlib import Path

cases = 0
for system_clear, launch, response in itertools.product((0, 1), repeat=3):
    ce = (0xFE >> (system_clear + 2 * launch + 4 * response)) & 1
    increment = (0x2 >> (response + 2 * system_clear)) & 1
    for old in range(1 << 17):
        reference = old
        if system_clear:
            reference = 0
        else:
            if launch:
                reference = 0
            if response:
                reference = (old + 1) & 0x1FFFF
        data = ((old + 1) & 0x1FFFF) if increment else 0
        local = data if ce else old
        assert local == reference
        cases += 1

result = {
    "execution": "all 17-bit prestate and S/L/R combinations completed",
    "verdict": "literal LUT3 INIT_FE and LUT2 INIT_2 implement original NBA precedence with own-state increment",
    "cases": cases,
    "LUT3_inputs": {"I0": "S", "I1": "L", "I2": "R"},
    "LUT2_inputs": {"I0": "R", "I1": "S"},
    "review": "independent A007 exhaustive design equation check",
    "limitations": [
        "Induction assumes equal old address and common asynchronous reset to zero.",
        "Does not simulate future RTL or prove its sideband wiring, memory inference, RDW mode or physical implementation."
    ]
}
with Path(__file__).with_name("A3_LUT_equation_check.json").open("x") as stream:
    json.dump(result, stream, indent=2)
    stream.write("\n")
print(json.dumps(result))
