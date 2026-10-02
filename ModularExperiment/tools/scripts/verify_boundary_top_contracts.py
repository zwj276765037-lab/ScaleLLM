#!/usr/bin/env python3
"""Verify boundary XSIM/OOC top-to-source contracts without Vivado."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


ROOT = Path("/home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment")


CONFIGS: dict[str, dict[str, Any]] = {
    "03_attention_rope": {
        "lists": ["boundary_sc.sources", "boundary_fp.sources"],
        "top_lists": {
            "m03_sc_projection_rope_pair": "boundary_sc.sources",
            "m03_fp16_projection_rope_pair": "boundary_fp.sources",
            "m03_fp32_projection_rope_pair": "boundary_fp.sources",
        },
        "tb_file": "tb/m03_projection_rope_boundary_tb.sv",
        "tb_top": "m03_projection_rope_boundary_tb",
        "bindings": [],
    },
    "05_attention_qk_score": {
        "lists": [
            "boundary_sc.sources", "boundary_fp.sources",
            "boundary_sc_ooc.sources", "boundary_fp_ooc.sources",
        ],
        "top_lists": {
            "m05_sc_qk_boundary_serial_ooc_wrapper":
                "boundary_sc_ooc.sources",
            "m05_fp16_qk_boundary_serial_ooc_wrapper":
                "boundary_fp_ooc.sources",
            "m05_fp32_qk_boundary_serial_ooc_wrapper":
                "boundary_fp_ooc.sources",
        },
        "tb_file": "tb/m05_qk_boundary_cache_tb.sv",
        "tb_top": "m05_qk_boundary_cache_tb",
        "bindings": [],
    },
    "06_attention_softmax": {
        "lists": ["boundary_sc.sources", "boundary_fp.sources"],
        "top_lists": {
            "m06_sc_softmax_boundary": "boundary_sc.sources",
            "m06_fp16_softmax_boundary": "boundary_fp.sources",
            "m06_fp32_softmax_boundary": "boundary_fp.sources",
        },
        "tb_file": "tb/m06_softmax_boundary_tb.sv",
        "tb_top": "m06_softmax_boundary_tb",
        "binding_file": "rtl/boundary/m06_softmax_boundary.sv",
        "bindings": ["m8_fp16_softmax_x22", "m8_fp32_softmax_x26"],
    },
    "07_attention_pv": {
        "lists": ["boundary_sc.sources", "boundary_fp.sources"],
        "top_lists": {
            "m07_sc_pv_boundary": "boundary_sc.sources",
            "m07_fp16_pv_boundary": "boundary_fp.sources",
            "m07_fp32_pv_boundary": "boundary_fp.sources",
        },
        "tb_file": "tb/m07_pv_boundary_tb.sv",
        "tb_top": "m07_pv_boundary_tb",
        "binding_file": "rtl/boundary/m07_pv_boundary.sv",
        "bindings": ["m9_fp16_pv_x19", "m9_fp32_pv_x21"],
    },
    "10_mlp_silu_multiply": {
        "lists": ["boundary_sc.sources", "boundary_fp.sources"],
        "top_lists": {
            "m10_sc_silu_boundary_x2": "boundary_sc.sources",
            "m10_fp16_silu_boundary_x2": "boundary_fp.sources",
            "m10_fp32_silu_boundary_x2": "boundary_fp.sources",
        },
        "tb_file": "tb/m10_silu_boundary_tb.sv",
        "tb_top": "m10_silu_boundary_tb",
        "bindings": [],
    },
}


def clean_sv(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"//.*", "", source)


def module_names(path: Path) -> set[str]:
    source = clean_sv(path.read_text(encoding="utf-8"))
    return set(re.findall(
        r"\bmodule\s+([A-Za-z_$][A-Za-z0-9_$]*)", source))


def read_source_list(path: Path) -> tuple[list[Path], set[str]]:
    sources = [Path(line.strip()) for line in path.read_text(
        encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")]
    if len(sources) != len(set(sources)):
        raise AssertionError(f"duplicate source path: {path}")
    names: set[str] = set()
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"{path}: {source}")
        names.update(module_names(source))
    return sources, names


def main() -> None:
    source_list_count = 0
    source_entry_count = 0
    top_count = 0
    tb_count = 0
    binding_count = 0
    for module_name, config in CONFIGS.items():
        module = ROOT / "experiment" / module_name
        inventories: dict[str, set[str]] = {}
        for filename in config["lists"]:
            paths, names = read_source_list(module / "vivado" / filename)
            inventories[filename] = names
            source_list_count += 1
            source_entry_count += len(paths)

        runner = (module / "run_boundary_ooc.sh").read_text(encoding="utf-8")
        for variant, top in zip(
                ("sc", "fp16", "fp32"), config["top_lists"], strict=True):
            filename = config["top_lists"][top]
            if top not in inventories[filename]:
                raise AssertionError(
                    f"{module_name}: {top} missing from {filename}")
            if f"{variant}) top={top}" not in runner:
                raise AssertionError(
                    f"{module_name}: OOC runner does not bind {variant} to {top}")
            top_count += 1

        tb_path = module / config["tb_file"]
        if config["tb_top"] not in module_names(tb_path):
            raise AssertionError(f"{module_name}: missing TB top")
        xsim_tcl = (module / "vivado" / "run_boundary_xsim.tcl").read_text(
            encoding="utf-8")
        required_tcl = [
            f"set_property top {config['tb_top']}",
            "set case_id 0", "set case_id 1", "set case_id 2",
            "boundary_sc.sources", "boundary_fp.sources",
        ]
        missing_tcl = [item for item in required_tcl if item not in xsim_tcl]
        if missing_tcl:
            raise AssertionError(
                f"{module_name}: XSIM Tcl missing {missing_tcl}")
        tb_count += 1

        if config["bindings"]:
            binding_text = (module / config["binding_file"]).read_text(
                encoding="utf-8")
            missing_bindings = [name for name in config["bindings"]
                                if name not in binding_text]
            if missing_bindings:
                raise AssertionError(
                    f"{module_name}: missing farm bindings {missing_bindings}")
            binding_count += len(config["bindings"])

    print(
        "BOUNDARY_TOP_CONTRACT_VERIFY_PASS "
        f"modules={len(CONFIGS)} source_lists={source_list_count} "
        f"source_entries={source_entry_count} ooc_tops={top_count} "
        f"tb_tops={tb_count} farm_bindings={binding_count}")


if __name__ == "__main__":
    main()
