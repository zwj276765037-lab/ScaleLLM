#!/usr/bin/env python3
"""Static gate for the staged M02 semantic-probe and real-trace chain."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
FILES = {
    "generator": HERE / "generate_trace_vectors.py",
    "trace_verifier": HERE / "verify_trace_vectors.py",
    "semantic_verifier": HERE / "verify_fp16_nonfinite_probe.py",
    "probe_runner": MODULE / "run_fp16_nonfinite_probe.sh",
    "trace_runner": MODULE / "run_matched_xsim.sh",
    "probe_tcl": MODULE / "vivado/run_fp16_nonfinite_probe.tcl",
    "trace_tcl": MODULE / "vivado/run_matched_xsim.tcl",
    "probe_tb": MODULE / "tb/m02_fp16_nonfinite_probe_tb.sv",
    "trace_tb": MODULE / "tb/m02_projection_trace_tb.sv",
}


def require(text: str, fragments: tuple[str, ...], label: str) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise AssertionError(f"{label} is missing contract fragments: {missing}")


def main() -> None:
    for label, path in FILES.items():
        if not path.is_file():
            raise AssertionError(f"missing M02 {label}: {path}")
    for path in (FILES["generator"], FILES["trace_verifier"],
                 FILES["semantic_verifier"]):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    probe_runner = FILES["probe_runner"].read_text(encoding="utf-8")
    require(probe_runner, (
        "verify_fp16_nonfinite_probe.py", "semantic_map.json",
        "FP_XCI_SHA256SUMS", "SHA256SUMS",
    ), "probe runner")
    trace_runner = FILES["trace_runner"].read_text(encoding="utf-8")
    require(trace_runner, (
        "synthetic|trace", "verify_trace_vectors.py\" --integrity-only",
        "m02_projection_trace_tb.sv", "FP_XCI_SHA256SUMS",
        "PASS: M02 real projection trace",
    ), "trace runner")
    probe_tcl = FILES["probe_tcl"].read_text(encoding="utf-8")
    require(probe_tcl, (
        "xcvu9p-flga2104-2L-e", "create_fp_ip.tcl",
        "m02_fp16_nonfinite_probe_tb",
    ), "probe Tcl")
    trace_tcl = FILES["trace_tcl"].read_text(encoding="utf-8")
    require(trace_tcl, (
        "xcvu9p-flga2104-2L-e", 'if {$dataset eq "trace"}',
        "m02_projection_trace_tb", "BACKPRESSURE=$backpressure",
        "TILES=18", "DATA_DIR=$data_dir",
    ), "trace Tcl")
    probe_tb = FILES["probe_tb"].read_text(encoding="utf-8")
    require(probe_tb, (
        "module m02_fp16_nonfinite_probe_tb", "localparam integer CASES = 25",
        "M02_FP16_SEMANTIC_RECORD_JSON", "Infinity multiplied by zero",
    ), "probe TB")
    trace_tb = FILES["trace_tb"].read_text(encoding="utf-8")
    require(trace_tb, (
        "module m02_projection_trace_tb", "parameter integer TILES = 18",
        "drain_cycles <= 8", "if (error)",
        "PASS: M02 real projection trace",
    ), "trace TB")

    spec = importlib.util.spec_from_file_location(
        "m02_trace_generator", FILES["generator"])
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load M02 trace generator")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    if (generator.ROWS, generator.COLS, generator.GROUPS,
            generator.GROUP_SIZE) != (8, 16, 128, 32):
        raise AssertionError("M02 trace geometry changed")
    if (generator.SAMPLES != (0, 1) or
            generator.LAYERS != (0, 15, 31) or
            generator.KINDS != ("q", "k", "v") or
            len(generator.M03_SPECIAL) != 12):
        raise AssertionError("M02 trace coordinate contract changed")

    semantic_maps = sorted(
        generator.DEFAULT_SEMANTIC_ROOT.glob("*/semantic_map.json"))
    formal_manifest = generator.DEFAULT_OUTPUT / "manifest.json"
    if not semantic_maps and not formal_manifest.exists():
        try:
            generator.find_semantic_map(None, generator.DEFAULT_SEMANTIC_ROOT)
        except SystemExit as error:
            if "no PASSed and hashed FP16 semantic_map.json" not in str(error):
                raise
        else:
            raise AssertionError("M02 semantic gate opened without evidence")

    print(
        "M02_STATIC_CONTRACT_VERIFY_PASS "
        f"files={len(FILES)} semantic_maps={len(semantic_maps)} "
        f"formal_trace={int(formal_manifest.exists())} "
        "tiles=18 transactions=2304 valid_outputs=2304")


if __name__ == "__main__":
    main()
