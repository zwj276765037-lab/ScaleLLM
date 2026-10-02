#!/usr/bin/env python3
"""Verify M12 source/top/payload/IP latency contracts without Vivado."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1]


def text(relative: str) -> str:
    return (MODULE / relative).read_text(encoding="utf-8")


def module_names(source: str) -> set[str]:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    source = re.sub(r"//.*", "", source)
    return set(re.findall(r"\bmodule\s+([A-Za-z_$][A-Za-z0-9_$]*)", source))


def source_inventory(relative: str) -> tuple[list[Path], set[str]]:
    paths = [Path(line.strip()) for line in text(relative).splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if len(paths) != len(set(paths)):
        raise AssertionError(f"duplicate source in {relative}")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise AssertionError(f"missing sources in {relative}: {missing}")
    names: set[str] = set()
    for path in paths:
        names.update(module_names(path.read_text(encoding="utf-8")))
    return paths, names


def require_names(label: str, observed: set[str], required: set[str]) -> None:
    missing = required - observed
    if missing:
        raise AssertionError(f"{label} missing modules: {sorted(missing)}")


def require_fragments(label: str, source: str, fragments: list[str]) -> None:
    missing = [fragment for fragment in fragments if fragment not in source]
    if missing:
        raise AssertionError(f"{label} missing contracts: {missing}")


def main() -> None:
    inventories = {}
    all_modules: set[str] = set()
    source_count = 0
    for relative in ["vivado/sc.sources", "vivado/sc_ooc.sources",
                     "vivado/fp.sources", "vivado/fp_ooc.sources"]:
        paths, names = source_inventory(relative)
        inventories[relative] = names
        all_modules.update(names)
        source_count += len(paths)

    sc_required = {
        "m12_sc_down_group_major",
        "m12_down_serial_ooc_wrapper",
        "m12_sc_down_serial_ooc_wrapper",
    }
    fp_required = {
        "m12_fp_a8w4_lane2_partial",
        "m12_fp_down_group_major",
        "m12_fp16_down_group_major",
        "m12_fp32_down_group_major",
        "m12_down_serial_ooc_wrapper",
        "m12_fp16_down_serial_ooc_wrapper",
        "m12_fp32_down_serial_ooc_wrapper",
    }
    require_names("sc.sources", inventories["vivado/sc.sources"], sc_required)
    require_names("sc_ooc.sources", inventories["vivado/sc_ooc.sources"], sc_required)
    require_names("fp.sources", inventories["vivado/fp.sources"], fp_required)
    require_names("fp_ooc.sources", inventories["vivado/fp_ooc.sources"], fp_required)

    serial_tb_names = module_names(text("tb/m12_down_serial_ooc_wrapper_tb.sv"))
    full_tb_names = module_names(text("tb/m12_down_group_major_tb.sv"))
    require_names("serial TB", serial_tb_names,
                  {"m12_down_serial_ooc_wrapper_tb"})
    require_names("full TB", full_tb_names, {"m12_down_group_major_tb"})
    require_fragments("serial XSIM Tcl", text("vivado/run_serial_xsim.tcl"), [
        "set_property top m12_down_serial_ooc_wrapper_tb",
        "CASE_ID=$case_id BACKPRESSURE=$backpressure DATA_DIR=$data_dir",
        "xsim.elaborate.debug_level off",
        "xsim.simulate.custom_tcl",
        "run_1000ns_no_wave.tcl",
        "sc_ooc.sources", "fp_ooc.sources",
    ])
    require_fragments("serial XSIM runner", text("run_serial_xsim.sh"), [
        "[0|1 backpressure] [wave|nowave]",
        "verify_mini_vectors.py",
        "HAP_DATA_DIR=\"$data_dir\" HAP_WAVE_MODE=\"$wave_mode\"",
        "M12_SERIAL_WORD_HEX:",
        "M12_SERIAL_INPUT_ACCEPT:",
        "input_accepts.txt",
        "source \"$MODULE/guard_vivado_slot.sh\"",
        "wdb_total_bytes.txt",
    ])
    require_fragments("serial A/B runner", text("run_serial_ab.sh"), [
        "source \"$MODULE/guard_vivado_slot.sh\"",
        "verify_child",
        "input_accepts.txt",
        "output_words.txt",
        "functional_metrics.txt",
        "wave_wdb > 0 && nowave_wdb < wave_wdb",
        "outputs_metrics_and_handshake_bit_exact",
    ])
    require_fragments("Vivado concurrency guard", text("guard_vivado_slot.sh"), [
        "M12_VIVADO_GUARD_BLOCKED",
        "flock -n 9",
        "HAP_M12_VIVADO_GUARD_HELD",
        "/tmp/scalellm_modular_vivado.lock",
    ])
    require_fragments("full XSIM Tcl", text("vivado/run_full_xsim.tcl"), [
        "set_property top m12_down_group_major_tb",
        "CASE_ID=$case_id DATA_DIR=",
        "set data_dir [file normalize $::env(HAP_DATA_DIR)]",
        "xsim.elaborate.debug_level off",
        "xsim.simulate.custom_tcl",
        "sc.sources", "fp.sources",
    ])
    require_fragments("full XSIM runner datasets", text("run_full_xsim.sh"), [
        "synthetic|trace_l00|trace_l15|trace_l31",
        "[wave|nowave]",
        "HAP_DATA_DIR=\"$data_dir\"",
        "HAP_WAVE_MODE=\"$wave_mode\"",
        "source \"$MODULE/guard_vivado_slot.sh\"",
        "verify_trace_vectors.py\" --integrity-only",
        "data_sources=(\"$MODULE/model/generate_trace_vectors.py\"\n"
        "            \"$MODULE/model/generate_vectors.py\"",
        "data_trace/layer$layer",
        "data_files=(",
        "expected_sc_s24x16x12.mem",
        "expected_fp16_s24x16x12.mem",
        "expected_fp32_s24x16x12.mem",
        "wdb_total_bytes.txt",
    ])
    require_fragments("OOC runner", text("run_matched_ooc.sh"), [
        "sc) top=m12_sc_down_serial_ooc_wrapper",
        "fp16) top=m12_fp16_down_serial_ooc_wrapper",
        "fp32) top=m12_fp32_down_serial_ooc_wrapper",
        "HAP_OOC_LAUNCHER=\"$MODULE/run_matched_ooc.sh\"",
        "HAP_OOC_GUARD=\"$MODULE/guard_vivado_slot.sh\"",
        "HAP_OOC_PRE_SYNTH_TCL",
    ])

    wrapper = text("rtl/m12_down_serial_ooc_wrapper.sv")
    require_fragments("serial payload", wrapper, [
        "VARIANT == 0 ? 6559",
        "VARIANT == 1 ? 6615 : 7063",
        "localparam integer RESULT_WORDS = 18",
        ".VARIANT(0)", ".VARIANT(1)", ".VARIANT(2)",
        "load_payload_r[6558]", "load_payload_r[6614]",
        "load_payload_r[7062]",
    ])
    serial_tb = text("tb/m12_down_serial_ooc_wrapper_tb.sv")
    require_fragments("serial TB geometry", serial_tb, [
        "localparam integer GROUPS = 5",
        "localparam integer TILES = 16",
        "localparam integer LOAD_WORDS = CASE_ID == 2 ? 28 : 26",
        "localparam integer RESULT_WORDS = 18",
        "parameter string DATA_DIR = \"data_mini\"",
        "payload_mem [0:TRANSACTIONS-1]",
        "expected_mem [0:TILES-1]",
        "M12_SERIAL_WORD_HEX:",
        "M12_SERIAL_INPUT_ACCEPT:",
        "nonzero_result_words == 0",
    ])
    full_tb = text("tb/m12_down_group_major_tb.sv")
    require_fragments("full TB geometry", full_tb, [
        "localparam integer GROUPS = 448",
        "localparam integer TILES = 342",
        "localparam integer TRANSACTIONS = GROUPS*TILES",
        "case (CASE_ID)",
        "expected_sc_s24x16x12.mem",
        "expected_fp16_s24x16x12.mem",
        "expected_fp32_s24x16x12.mem",
    ])

    manifest = json.loads(text("data/manifest.json"))
    expected_manifest = {
        "groups": 448,
        "tiles": 342,
        "transactions": 153216,
        "rows": 16,
        "valid_output_columns": 4096,
    }
    for key, expected in expected_manifest.items():
        if manifest.get(key) != expected:
            raise AssertionError(
                f"manifest {key}: expected {expected}, got {manifest.get(key)}")
    if manifest["rows"] * manifest["valid_output_columns"] != 65536:
        raise AssertionError("manifest valid output count is not 65,536")
    synthetic_generator = Path(manifest["generator"])
    expected_synthetic_generator = MODULE / "model/generate_vectors.py"
    if synthetic_generator.resolve() != expected_synthetic_generator.resolve():
        raise AssertionError("synthetic manifest generator path changed")
    if hashlib.sha256(synthetic_generator.read_bytes()).hexdigest() != (
            manifest["generator_sha256"]):
        raise AssertionError("synthetic manifest generator hash changed")

    trace_manifest = json.loads(text("data_trace/manifest.json"))
    expected_trace = {
        "schema": "scalellm_modular_m12_down_real_trace_v1",
        "layers": [0, 15, 31],
        "rows_per_layer": 16,
        "groups": 448,
        "tiles": 342,
        "transactions_per_layer": 153216,
        "valid_output_columns": 4096,
        "tail_mask": "0x00f",
    }
    for key, expected in expected_trace.items():
        if trace_manifest.get(key) != expected:
            raise AssertionError(
                f"trace manifest {key}: expected {expected}, "
                f"got {trace_manifest.get(key)}")
    if len(trace_manifest.get("files", {})) != 37:
        raise AssertionError("trace manifest must bind 37 payload/provenance files")
    fp_semantics_model = Path(trace_manifest["fp_semantics_model"])
    expected_fp_semantics_model = MODULE / "model/generate_vectors.py"
    if fp_semantics_model.resolve() != expected_fp_semantics_model.resolve():
        raise AssertionError("trace manifest FP semantics model path changed")
    if hashlib.sha256(fp_semantics_model.read_bytes()).hexdigest() != (
            trace_manifest["fp_semantics_model_sha256"]):
        raise AssertionError("trace manifest FP semantics model hash changed")

    mini_manifest = json.loads(text("data_mini/manifest.json"))
    expected_mini = {
        "schema": "scalellm_m12_down_a8w4_full_lane_mini_v1",
        "rows": 16,
        "physical_columns": 12,
        "groups": 5,
        "tiles": 16,
        "transactions": 80,
        "source_tiles": list(range(15)) + [341],
        "tail_mask": "0x00f",
        "fp16_boundary_cases": 3,
    }
    for key, expected in expected_mini.items():
        if mini_manifest.get(key) != expected:
            raise AssertionError(
                f"mini manifest {key}: expected {expected}, "
                f"got {mini_manifest.get(key)}")
    if len(mini_manifest.get("files", {})) != 6:
        raise AssertionError("mini manifest must bind six payload/golden files")
    if any(mini_manifest["payload_nonzero_transactions"].get(variant) != 80
           for variant in ("sc", "fp16", "fp32")):
        raise AssertionError("mini workload contains a zero input transaction")
    if any(mini_manifest["expected_nonzero_elements"].get(variant, 0) <= 0
           for variant in ("sc", "fp16", "fp32")):
        raise AssertionError("mini workload contains an all-zero result variant")
    if any(mini_manifest["arithmetic_nonzero_group_tiles"].get(variant, 0) <= 0
           for variant in ("correlation", "sc", "fp16", "fp32")):
        raise AssertionError("mini workload contains an all-zero arithmetic path")
    mini_generator = Path(mini_manifest["generator"])
    expected_mini_generator = MODULE / "model/generate_mini_vectors.py"
    if mini_generator.resolve() != expected_mini_generator.resolve():
        raise AssertionError("mini manifest generator path changed")
    if hashlib.sha256(mini_generator.read_bytes()).hexdigest() != (
            mini_manifest["generator_sha256"]):
        raise AssertionError("mini manifest generator hash changed")

    ip_tcl = text("vivado/create_fp_ip.tcl")
    latency_matches = dict(re.findall(
        r"make_m12_ip\s+(m12_[A-Za-z0-9_]+).*?\]\s+(\d+)\s*$",
        ip_tcl, flags=re.M | re.S))
    expected_latencies = {
        "m12_int17_to_fp32": "6",
        "m12_fp32_add": "11",
        "m12_fp32_to_s24": "6",
        "m12_fp32_to_fp16": "3",
        "m12_fp16_mul": "6",
        "m12_fp16_to_fp32": "2",
        "m12_fp32_mul": "8",
    }
    if latency_matches != expected_latencies:
        raise AssertionError(
            f"IP latency contract mismatch: {latency_matches}")
    fp_core = text("rtl/m12_fp_down_group_major.sv")
    lane = text("rtl/m12_fp_a8w4_lane2_partial.sv")
    require_fragments("FP core latency", fp_core, [
        "localparam integer ADD_LAT = 11",
        "localparam integer FIXED_LAT = 6",
    ])
    require_fragments("FP lane latency", lane, [
        "localparam integer INT_LAT = 6",
        "localparam integer MUL_LAT = 8",
        "localparam integer NARROW_LAT = 3",
        "localparam integer MUL_LAT = 6",
    ])

    print(
        "M12_STATIC_CONTRACT_VERIFY_PASS "
        f"source_entries={source_count} modules={len(all_modules)} "
        "tops=6 ip_latencies=7 payload_variants=3 trace_layers=3 "
        "nonzero_mini=1 wave_ab=1 vivado_guard=1")


if __name__ == "__main__":
    main()
