#!/usr/bin/env python3
"""Fail-closed source closure and static production shape for final hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HW = Path(__file__).resolve().parents[2]
MANIFEST = HW / "vivado/manifests/final/board.list"


def closure():
    selected, active = set(), set()
    def visit(path):
        path = path.resolve(strict=True)
        if not path.is_relative_to(HW) or path.stat().st_size == 0:
            raise ValueError("invalid final input: " + str(path))
        if path in active:
            raise ValueError("source manifest cycle")
        if path in selected:
            return
        selected.add(path)
        if path.suffix == ".list":
            active.add(path)
            for raw in path.read_text().splitlines():
                name = raw.split("#", 1)[0].strip()
                if name:
                    visit(HW / name)
            active.remove(path)
        elif path.suffix in (".sv", ".v"):
            for include in re.findall(r'`include\s+"([^"]+)"', path.read_text()):
                visit(path.parent / include)
    visit(MANIFEST)
    for path in (HW / "source/final/abi.json", Path(__file__).resolve(),
                 HW / "vivado/scripts/final_gen_abi.py"):
        visit(path)
    return sorted(selected)


def shape():
    paths = closure()
    names = {path.name for path in paths}
    required = {"hap_attention_decode16_top.sv", "hap_kv12_request_scratch.sv",
                "hap_mlp_online_compute16_s32.sv", "hap_mlp_swiglu_s32_endpoint16.sv",
                "hap_scalellm_final_board_core.sv", "hap_scalellm_final_core.sv",
                "mlp_silu_q16.mem", "softmax_exp_u17.mem"}
    forbidden = {"hap_attention_board_cohort16_core.sv",
                 "hap_attention_compute_cohort16_top.sv",
                 "hap_attention_mlp_board_core_gu_only.sv",
                 "hap_attention_mlp_production_core_gu_only.sv"}
    if not required <= names or names & forbidden:
        raise ValueError("final source closure has missing/new or forbidden baseline top")
    board = (HW / "rtl/integration/hap_scalellm_final_board_core.sv").read_text()
    mlp = (HW / "rtl/integration/hap_scalellm_final_mlp_engine.sv").read_text()
    if "FREQ_HZ 80000000" not in board or "100000000" in board:
        raise ValueError("final module-reference core clock metadata drift")
    if not re.search(r"INTERMEDIATE_COLUMNS\s*=\s*14336", mlp):
        raise ValueError("production MLP shape drift")
    return dict(rows=16, independent_requests=True, layers=32, hidden=4096,
                intermediate=14336, context=128, core_hz=80000000,
                ddr_ui_hz=200000000, mlp_input_bytes=196608,
                mlp_output_bytes=917504, attention_output_bytes=196608,
                fpga_mlp="H32/A8/GU-scale-restoration/SiLU*Up S32/F16",
                global_step_commit="Host only after all 32 layers", baseline_commit=
                "afa6fc09e7f2ac4a382e51637148b4acc63ad954")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "list-sources", "shape", "manifest"))
    args = parser.parse_args()
    value = shape()
    if args.action == "list-sources": print("\n".join(map(str, closure())))
    elif args.action == "shape": print(json.dumps(value, indent=2))
    else:
        print(json.dumps(dict(schema="scalellm_final_source_closure_v1", shape=value,
                              files={str(p.relative_to(HW)): hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in closure()}), indent=2))


if __name__ == "__main__": main()
