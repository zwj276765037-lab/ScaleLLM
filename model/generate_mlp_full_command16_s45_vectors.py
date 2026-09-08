#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

import generate_mlp_input_frontend16_cache_vectors as input_frontend
import generate_mlp_serial_ddr_command16_s45_vectors as serial_command


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "mlp_full_command16_s45"


def main() -> None:
    # Both generators use the same fixed activation seed and numeric model.
    # The serial golden therefore consumes exactly the A8 cache image produced
    # by the S24 input frontend, while the full test supplies the original S24.
    input_frontend.main()
    serial_command.main()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps({
        "input_groups": input_frontend.GROUPS,
        "gate_tiles": 4,
        "gate_transactions": 4 * input_frontend.GROUPS,
        "down_groups": 1,
        "down_tiles": 8,
        "scheme": "Dell S24 -> FPGA Hadamard/A8 -> gate/up/down -> S24",
        "input_source": "../mlp_input_frontend16_cache/input_s24x16x32.mem",
        "serial_golden": "../mlp_serial_ddr_command16_s45/",
    }, indent=2) + "\n", encoding="utf-8")
    print("PASS: generated full S24-input MLP command vector manifest")


if __name__ == "__main__":
    main()
