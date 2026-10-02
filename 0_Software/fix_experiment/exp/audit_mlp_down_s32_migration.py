#!/usr/bin/env python3
"""Static migration audit for final format-v5 S45/S54/S32 and stream256.

This inspects source contracts, not runtime bit-exactness or board signoff.
The legacy format-v4 audit reports remain historical; new reports use a
separate output directory and never require a central 8192-bit physical bus.
"""

from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import operator
from pathlib import Path
import re
from typing import Any, Iterable


WORKSPACE = Path("/home/user/EDA-202/zhuowenjun")
HAP_REL = Path("fpga_llm_project/0_fix_newdataflow_Hadamard/HAP")
DEFAULT_OUTPUT = Path(
    "ScaleLLM/0_Software/fix_experiment/results/"
    "mission0215_mlp_format_v5_migration"
)
PRODUCTION_MANIFEST = Path(
    "vivado/manifests/attention_mlp_production_v5_cohort16_sources.list"
)
NEW_FORMAT_ID = 0x48384605


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write the audit but return success while migration checks fail.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
    )


def manifest_closure(hap: Path, entry: Path, manifests: list[Path] | None = None) -> list[Path]:
    observed: list[Path] = []
    visited: set[Path] = set()

    def visit(relative: Path) -> None:
        if relative in visited:
            return
        visited.add(relative)
        path = hap / relative
        if not path.is_file():
            raise FileNotFoundError(f"production manifest entry is missing: {path}")
        if path.suffix != ".list":
            observed.append(relative)
            return
        if manifests is not None:
            manifests.append(relative)
        for raw in path.read_text(encoding="utf-8").splitlines():
            item = raw.split("#", 1)[0].strip()
            if item:
                visit(Path(item))

    visit(entry)
    return observed


def has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.MULTILINE | re.DOTALL) is not None


def integer_constants(text: str) -> dict[str, int]:
    """Resolve module-level integer expressions without importing target code."""
    values: dict[str, int] = {}
    operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.LShift: operator.lshift}

    def resolve(node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](resolve(node.left), resolve(node.right))
        raise ValueError("not a supported integer constant")

    for statement in ast.parse(text).body:
        if isinstance(statement, ast.Assign):
            try:
                value = resolve(statement.value)
            except (KeyError, ValueError):
                continue
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value
    return values


def build_report(workspace: Path) -> dict[str, Any]:
    workspace = workspace.resolve()
    hap = workspace / HAP_REL
    manifests: list[Path] = []
    closure = manifest_closure(hap, PRODUCTION_MANIFEST, manifests)
    closure_set = {str(path) for path in closure}

    files = {
        "accumulator": hap / "rtl/mlp/hap_mlp_down_group_major_accum_s54.sv",
        "shared": hap / "rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv",
        "scheduler": hap / "rtl/mlp/hap_mlp_down_v5_scheduler16_s54.sv",
        "serial": hap / "rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv",
        "full": hap / "rtl/mlp/hap_mlp_full_command16_v5_s54.sv",
        "lane": hap / "rtl/mlp/hap_a8w4_group32_lane2_s37.sv",
        "pkg": hap / "rtl/mlp/hap_mlp_pkg.sv",
        "silu": hap / "rtl/mlp/hap_mlp_silu_mul.sv",
        "repack": hap / "rtl/mlp/hap_mlp_projection_repack12_to16_s32_history2.sv",
        "branch_stream": hap / "rtl/mlp/hap_mlp_down_branch_repack_stream256.sv",
        "pair_join": hap / "rtl/mlp/hap_mlp_down_pair_join_stream256.sv",
        "resource": hap / "rtl/integration/hap_attention_mlp_resource_top.sv",
        "production": hap / "rtl/integration/hap_attention_mlp_production_core.sv",
        "dma": hap / "rtl/integration/hap_mlp_tensor_dma_bridge.sv",
        "axil": hap / "rtl/integration/hap_mlp_axil_control.sv",
        "memory": hap / "host/scalellm_memory.py",
        "hostops": hap / "host/scalellm_hostops.py",
        "hardware": hap / "host/scalellm_hardware.py",
        "artifact": hap / "artifacts/llama31_8b_scalellm_v5/scalecode_manifest.json",
    }
    texts = {
        name: path.read_text(encoding="utf-8") for name, path in files.items()
    }
    digests = {name: sha256(path) for name, path in files.items()}
    artifact = json.loads(texts["artifact"])

    checks: list[dict[str, Any]] = []

    def check(
        check_id: str,
        component: str,
        passed: bool,
        expected: str,
        observed: str,
        sources: Iterable[str],
        action: str,
        severity: str = "critical",
    ) -> None:
        source_names = list(sources)
        checks.append(
            {
                "check_id": check_id,
                "component": component,
                "pass": bool(passed),
                "severity": severity,
                "expected": expected,
                "observed": observed,
                "required_action": action,
                "sources": [str(files[name]) for name in source_names],
                "source_sha256": {name: digests[name] for name in source_names},
            }
        )

    acc = texts["accumulator"]
    finalizer_ok = (
        has(acc, r"output\s+wire\s+signed\s*\[LANES\s*\*\s*32\s*-\s*1:0\]")
        and has(acc, r"function\s+automatic\s+signed\s*\[31:0\]\s+saturate_s32")
        and has(acc, r"function\s+automatic\s+signed\s*\[53:0\]\s+round_q24_to_q16")
        and not has(acc, r"assign\s+finalized_projection_s24")
    )
    check(
        "down_finalizer_s32_f16",
        "Down S54/F24 accumulator finalizer",
        finalizer_ok,
        "round-away Q*.24→F16 followed by signed-32 saturation and LANES*32 output",
        "matched" if finalizer_ok else "S54/S32 finalizer contract missing",
        ["accumulator"],
        "Keep S54/F24 accumulation and one terminal round-away-to-F16/S32 saturation.",
    )

    pkg, lane = texts["pkg"], texts["lane"]
    ranges_ok = all(has(pkg, rf"{name}\s*=\s*{value}\s*;") for name, value in (
        ("MLP_GATE_UP_TOTAL_SHIFT_MIN", 20), ("MLP_DOWN_TOTAL_SHIFT_MIN", 12),
        ("MLP_TOTAL_SHIFT_MAX", 44), ("MLP_GATE_UP_GROUP_GUARD_W", 37),
        ("MLP_DOWN_GROUP_GUARD_W", 45), ("MLP_GATE_UP_ACCUM_W", 44),
        ("MLP_DOWN_ACCUM_W", 54),
    )) and has(lane, r"minimum_shift\s*=\s*down_mode\s*\?\s*7'd12\s*:\s*7'd20")
    ranges_ok = ranges_ok and has(lane, r"extended_s45\s*=\s*\{\{12\{raw_s33\[32\]\}\},\s*raw_s33\}")
    ranges_ok = ranges_ok and all(has(lane, pattern) for pattern in (
        r"output\s+wire\s+signed\s*\[36:0\]\s+guard0_s37",
        r"output\s+wire\s+signed\s*\[44:0\]\s+guard0_s45",
        r"total_shift_u7\s*>\s*7'd44",
    )) and ".ACC_W(44)" in texts["shared"]
    check("final_v5_ranges_and_guards", "Gate/Up and Down recovery", ranges_ok,
          "Gate/Up [20,44] S37/S44; Down [12,44] S45/S54; extend before shift",
          "matched" if ranges_ok else "range/width/extension contract missing",
          ["pkg", "lane"], "Implement final format-v5 ranges without narrowing the guard.")
    accum_ok = has(acc, r"wire\s+signed\s*\[54:0\]\s+lane_sum_ext") and has(
        acc, r"lane_sum_ext\[54\]\s*!=\s*lane_sum_ext\[53\]")
    check("down_s54_s55_overflow", "Down accumulator", accum_ok,
          "S54 accumulation with S55 overflow detection", str(accum_ok),
          ["accumulator"], "Preserve S55 sum and sign-consistency overflow detection.")
    silu_ok = all(has(texts["silu"], rf"input\s+wire\s+signed\s*\[23:0\]\s+{name}\b")
                  for name in ("gate_s24", "up_s24")) and has(
                      texts["silu"], r"output\s+reg\s+signed\s*\[31:0\]")
    check("swiglu_signed_s24_to_s32", "SwiGLU signed boundary", silu_ok,
          "Signed S24 Gate/Up inputs and signed S32 output", str(silu_ok),
          ["silu"], "Preserve signed operands; literal extension wires are not required.")

    shared = texts["shared"]
    gate_stays_s24 = has(
        shared, r"output\s+wire\s+signed\s*\[16\s*\*\s*12\s*\*\s*24\s*-\s*1:0\]\s+gate_s24"
    )
    down_becomes_s32 = has(shared, r"output\s+wire\s*\[255:0\]\s+down_stream_data") and all(
        name in shared for name in ("down_stream_valid", "down_stream_ready", "down_stream_beat"))
    check(
        "shared_gate_s24_preserved",
        "Shared Gate/Up result boundary",
        gate_stays_s24,
        "Gate/Up remains 16x12x24 S24/F16",
        "present" if gate_stays_s24 else "missing or widened",
        ["shared"],
        "Do not widen the Gate/Up path while migrating Down.",
        severity="high",
    )
    check(
        "shared_down_s32",
        "Shared Down result boundary",
        down_becomes_s32,
        "Branch-local S32 finalization, exported as a 256-bit stream",
        "matched" if down_becomes_s32 else "stream256 interface missing",
        ["shared"],
        "Keep branch-local S32 output and ordered stream256; do not restore a central wide bus.",
    )

    scheduler = texts["scheduler"]
    scheduler_ok = (
        has(scheduler, r"input\s+wire\s*\[255:0\]\s+projection_stream_data")
        and has(scheduler, r"output\s+wire\s*\[255:0\]\s+out_data")
        and has(texts["repack"], r"\.ELEMENT_W\(32\)")
        and has(texts["branch_stream"], r"output\s+wire\s*\[255:0\]\s+stream_data")
        and "out_beat = {select_branch1_r, selected_beat}" in texts["pair_join"]
    )
    check(
        "down_scheduler_repack_s32",
        "Down scheduler and 12→16 inverse repack",
        scheduler_ok,
        "Branch-local S32 12-to-16 repack and 32 AXI256 beats per logical tile",
        "matched" if scheduler_ok else "stream/repack contract missing",
        ["scheduler", "repack", "branch_stream", "pair_join"],
        "Verify the S32 repack and beat ordering without a central 8192-bit bus.",
    )

    for name, check_id, label in (
        ("serial", "serial_command_s32", "serial command"),
        ("full", "full_command_s32", "full command"),
        ("resource", "resource_top_s32", "resource top"),
    ):
        text = texts[name]
        prefix = "mlp_out" if name == "resource" else "out"
        ok = has(text, rf"output\s+wire\s*\[255:0\]\s+{prefix}_data\b") and all(
            f"{prefix}_{field}" in text for field in ("valid", "ready", "beat_index", "last"))
        check(
            check_id,
            label,
            ok,
            "Down output uses ordered stream256 with beat index and last",
            "matched" if ok else "stream256 boundary missing",
            [name],
            f"Propagate the Down S32 payload through the {label} ABI.",
        )

    production = texts["production"]
    production_ok = has(production, r"wire\s*\[255:0\]\s*mlp_out_data") and has(
        production, r"\.mlp_out_data\(mlp_out_data\)") and "[8191:0]" not in production
    check(
        "production_core_s32",
        "Production core wiring",
        production_ok,
        "256-bit Down stream connects directly to DMA; no central 8192-bit bus",
        "matched" if production_ok else "production stream connection missing",
        ["production"],
        "Connect the branch-local S32 byte stream to DMA without central tile buffering.",
    )

    dma = texts["dma"]
    dma_output_ok = has(dma, r"\[255:0\]\s*mlp_out_data")
    dma_beats_ok = has(dma, r"OUTPUT_TILES\s*\*\s*32")
    dma_banks_ok = (
        "output_tile_beat_r" not in dma
        and "output_tile_hold_r" not in dma
        and has(dma, r"assign\s+dma_wr_data\s*=\s*mlp_out_data")
        and "output_stream_legal" in dma
    )
    check(
        "tensor_dma_s32_payload",
        "MLP tensor DMA output",
        dma_output_ok and dma_beats_ok and dma_banks_ok,
        "8192-bit logical tile; 32 AXI256 beats/tile; direct stream, no legacy tile bank",
        "matched" if dma_output_ok and dma_beats_ok and dma_banks_ok else "DMA contract missing",
        ["dma"],
        "Keep 32 beats per logical tile and verify streamed length/order/backpressure.",
    )
    dma_input_preserved = (
        has(dma, r"\[12287:0\]\s+mlp_input_s24x16x32")
        and has(dma, r"INPUT_GROUPS\s*\*\s*48")
    )
    check(
        "tensor_dma_input_s24_preserved",
        "MLP tensor DMA input",
        dma_input_preserved,
        "S24/F16 input remains 12288 bits and 48 AXI256 beats/group",
        "present" if dma_input_preserved else "input ABI drifted",
        ["dma"],
        "Keep the proven post-RMSNorm input ABI unchanged.",
        severity="high",
    )

    memory = texts["memory"]
    hostops = texts["hostops"]
    memory_values = integer_constants(memory)
    host_payload_ok = memory_values.get("ACTIVATION_OUTPUT_PAYLOAD_BYTES") == 262144
    host_unpack_ok = has(hostops, r"def\s+unpack_s32_(?:q16|f16)\s*\(")
    host_read_ok = (
        has(hostops, r'elif stage == "after_mlp":\s*expected_bytes = ACTIVATION_OUTPUT_PAYLOAD_BYTES\s*decoder = unpack_s32_q16')
        and has(hostops, r"received\s*!=\s*expected_bytes")
        and 'np.frombuffer(view, dtype="<i4")' in hostops
        and integer_constants(hostops).get("S32_SCALE") == 65536
    )
    check(
        "host_s32_output_boundary",
        "Host C2H MLP output boundary",
        host_payload_ok and host_unpack_ok and host_read_ok,
        "256 KiB little-endian S32/F16 output buffer and dedicated unpack/read path",
        "matched" if host_payload_ok and host_unpack_ok and host_read_ok else "Host S32 boundary incomplete",
        ["memory", "hostops"],
        "Split H2C input and C2H output payload sizes; decode int32/2^16 before FP32 residual.",
    )
    host_input_preserved = (
        memory_values.get("ACTIVATION_INPUT_PAYLOAD_BYTES") == 196608
        and has(hostops, r"def\s+pack_s24_q16\s*\(")
    )
    check(
        "host_s24_input_preserved",
        "Host H2C post-RMSNorm input",
        host_input_preserved,
        "192 KiB packed S24/F16 H2C input remains available",
        "present" if host_input_preserved else "S24 input path drifted",
        ["memory", "hostops"],
        "Keep S24/F16 input packing separate from the new S32/F16 output path.",
        severity="high",
    )

    format_hex_rtl = f"32'h{NEW_FORMAT_ID >> 16:04x}_{NEW_FORMAT_ID & 0xffff:04x}"
    rtl_format_ok = format_hex_rtl.lower() in texts["axil"].lower()
    host_format_ok = has(
        texts["hardware"], r"MLP_FORMAT_ID\s*=\s*0x4838_4605"
    )
    artifact_format = int(artifact.get("mlp_format_id", -1))
    check(
        "format_id_v5_synchronized",
        "RTL/Host/artifact incompatible ABI identity",
        rtl_format_ok and host_format_ok and artifact_format == NEW_FORMAT_ID,
        "RTL, Host and artifact all use 0x48384605",
        "rtl_05={}; host_05={}; artifact={}".format(
            rtl_format_ok, host_format_ok, hex(artifact_format)
        ),
        ["axil", "hardware", "artifact"],
        "Bind all identities to final format-v5; reject format-v2/v3/v4 mixing.",
    )

    telemetry_ok = (
        has(texts["resource"], r"\.down_output_saturation_count\(x9\)")
        and has(texts["resource"], r"assign\s+mlp_telemetry\s*=\s*\{x11,x10,x9,")
        and has(texts["axil"], r"12'h2ac\s*:\s*rdata_r\s*<=\s*mlp_telemetry\[49\*32\s*\+:\s*32\]")
        and integer_constants(texts["hardware"]).get("MLP_DOWN_SATURATION_COUNT") == 0x2AC
        and '"down_output_saturation_count": MLP_DOWN_SATURATION_COUNT' in texts["hardware"]
        and 'if telemetry["down_output_saturation_count"]:' in texts["hardware"]
    )
    check(
        "down_s32_saturation_telemetry",
        "Down S32 terminal saturation observability",
        telemetry_ok,
        "down_output_saturation_count is exported by AXI-Lite and read by Host",
        "matched" if telemetry_ok else "Down saturation telemetry missing",
        ["resource", "axil", "hardware"],
        "Export a dedicated counter and make non-zero saturation a fail-closed run status.",
    )

    required_sources = {
        "rtl/mlp/hap_mlp_down_group_major_accum_s54.sv",
        "rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s54.sv",
        "rtl/mlp/hap_mlp_down_v5_scheduler16_s54.sv",
        "rtl/mlp/hap_mlp_serial_ddr_command16_v5_s54.sv",
        "rtl/mlp/hap_mlp_full_command16_v5_s54.sv",
        "rtl/mlp/hap_mlp_projection_repack12_to16_s32_history2.sv",
        "rtl/mlp/hap_mlp_down_branch_repack_stream256.sv",
        "rtl/mlp/hap_mlp_down_pair_join_stream256.sv",
        "rtl/integration/hap_slr_registered_credit_channel256.sv",
        "rtl/integration/hap_attention_mlp_resource_top.sv",
        "rtl/integration/hap_mlp_tensor_dma_bridge.sv",
        "rtl/integration/hap_attention_mlp_production_core.sv",
    }
    # The package is a checked contract mirror; live modules use local widths.
    required_sources.update(str(path.relative_to(hap)) for name, path in files.items()
                            if path.suffix == ".sv" and name != "pkg")
    legacy_sources = {path.replace("s54", "s46") for path in required_sources if "s54" in path}
    closure_ok = required_sources.issubset(closure_set) and not (legacy_sources & closure_set)
    checks.append(
        {
            "check_id": "production_source_closure",
            "component": "Active V5 production manifest",
            "pass": closure_ok,
            "severity": "critical",
            "expected": "all audited Down/DMA integration sources are in active closure",
            "observed": f"{len(required_sources & closure_set)}/{len(required_sources)} required sources present",
            "required_action": "Add every new S32 repack/adapter source to the active production manifest and rerun this audit.",
            "sources": [str(hap / PRODUCTION_MANIFEST)],
            "source_sha256": {str(PRODUCTION_MANIFEST): sha256(hap / PRODUCTION_MANIFEST)},
        }
    )

    passed = sum(1 for row in checks if row["pass"])
    status = "static_contract_pass" if passed == len(checks) else "migration_incomplete"
    report = {
        "schema": "scalellm_mlp_down_s32_migration_audit_v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks_passed": passed,
        "checks_total": len(checks),
        "evidence_class": "source_static_only",
        "board_signoff": False,
        "runtime_bit_exact_verified": False,
        "model_and_reference_identity_verified": False,
        "audit_script_sha256": sha256(Path(__file__)),
        "target_format": {
            "name": "S32/F16",
            "range": [-32768.0, 32767.99998474121],
            "tile_bits": 8192,
            "axi256_beats_per_tile": 32,
            "cohort_output_bytes": 262144,
            "format_id": "0x48384605",
            "down_total_shift": [12, 44],
            "down_guard_bits": 45,
            "down_accumulator_bits": 54,
            "physical_output_bus_bits": 256,
        },
        "production_manifest": str(hap / PRODUCTION_MANIFEST),
        "production_source_count": len(closure),
        "production_manifest_sha256": {str(path): sha256(hap / path) for path in manifests},
        "checks": checks,
    }
    return report


def main() -> None:
    args = parse_args()
    workspace = args.workspace.resolve()
    output = (args.output_root if args.output_root.is_absolute()
              else workspace / args.output_root).resolve()
    if (output / "mlp_down_s32_migration_audit.json").exists():
        raise SystemExit("Audit output already exists; choose a fresh --output-root.")
    report = build_report(workspace)
    checks = report["checks"]
    passed = report["checks_passed"]
    status = report["status"]
    atomic_json(output / "mlp_down_s32_migration_audit.json", report)

    csv_path = output / "mlp_down_s32_migration_audit.csv"
    temporary_csv = csv_path.with_suffix(".csv.tmp")
    with temporary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "check_id",
                "component",
                "pass",
                "severity",
                "expected",
                "observed",
                "required_action",
                "sources",
            ),
        )
        writer.writeheader()
        for row in checks:
            writer.writerow(
                {
                    **{key: row.get(key) for key in writer.fieldnames},
                    "sources": "; ".join(row.get("sources", [])),
                }
            )
    temporary_csv.replace(csv_path)

    lines = [
        "# MLP Down S32/F16 硬件迁移审计",
        "",
        f"状态：`{status}`（{passed}/{len(checks)}）",
        "",
        "本报告只检查最终 format-v5 源码合同；不是动态逐位一致性、模型/reference 身份或板级签核。",
        "",
        "| 检查项 | 模块 | 结果 | 当前观察 | 必须动作 |",
        "|---|---|---|---|---|",
    ]
    for row in checks:
        clean = lambda value: str(value).replace("|", "\\|").replace("\n", " ")
        lines.append(
            "| {check_id} | {component} | {result} | {observed} | {action} |".format(
                check_id=clean(row["check_id"]),
                component=clean(row["component"]),
                result="PASS" if row["pass"] else "FAIL",
                observed=clean(row["observed"]),
                action=clean(row["required_action"]),
            )
        )
    atomic_text(
        output / "mlp_down_s32_migration_audit.md", "\n".join(lines) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if status != "static_contract_pass" and not args.allow_incomplete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
