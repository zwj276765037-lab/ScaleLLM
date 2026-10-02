#!/usr/bin/env python3
"""Collect the latest valid SAIF-backed post-route power run per variant."""

from __future__ import annotations

import argparse
import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


VARIANT_ORDER = {"sc": 0, "fp16": 1, "fp32": 2}
WORK_UNITS = {
    "00_scale_apply_microkernel": ("group32", "vectors"),
    "02_attention_a8w8_projection": ("output_tile_8x16", None),
    "03_attention_rope": ("rope_pair", "vectors"),
    "04_attention_kv12_quantizer": ("kv_batch_4x32", "batches"),
    "05_attention_qk_score": ("qk_score", "scores"),
    "06_attention_softmax": ("softmax_row", "rows"),
    "07_attention_pv": ("pv_row_tile16", "rows"),
    "09_mlp_gate_up_a8w4": ("output_tile_16x12", None),
    "10_mlp_silu_multiply": ("silu_product", "vectors"),
}


def table_cells(row: ET.Element) -> list[str]:
    return [
        cell.attrib.get("contents", "").strip()
        for cell in row
        if cell.tag in {"tablecell", "tableheader"}
    ]


def find_section(root: ET.Element, title: str) -> ET.Element | None:
    return next((s for s in root.iter("section") if s.attrib.get("title") == title), None)


def first_table_map(section: ET.Element) -> dict[str, str]:
    table = section.find("table")
    if table is None:
        return {}
    values: dict[str, str] = {}
    for row in table.findall("tablerow"):
        cells = table_cells(row)
        if len(cells) >= 2 and row.find("tablecell") is not None:
            values[cells[0]] = cells[1]
    return values


def text_report_maps(report_text: str) -> tuple[dict[str, str], dict[str, str]]:
    summary: dict[str, str] = {}
    components: dict[str, str] = {}
    summary_labels = {
        "Total On-Chip Power (W)",
        "Dynamic (W)",
        "Device Static (W)",
        "Confidence Level",
        "Design Nets Matched",
    }
    component_labels = {
        "Clocks",
        "CLB Logic",
        "Signals",
        "DSPs",
        "Block RAM",
        "UltraRAM",
    }
    for line in report_text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        if cells[0] in summary_labels and cells[0] not in summary:
            summary[cells[0]] = cells[1]
        if cells[0] in component_labels and cells[0] not in components:
            components[cells[0]] = cells[1]
    return summary, components


def as_float(value: str | None) -> float | None:
    if not value or value.startswith("<"):
        return None
    match = re.search(r"[-+]?[0-9]+(?:\.[0-9]+)?", value)
    return float(match.group(0)) if match else None


def read_manifest(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def read_metric(path: Path) -> tuple[str | None, dict]:
    if not path.exists():
        return None, {}
    for line in path.read_text(errors="replace").splitlines():
        if "METRIC_JSON:" not in line:
            continue
        prefix, payload = line.split("METRIC_JSON:", 1)
        try:
            return prefix.strip().rstrip("_"), json.loads(payload.strip())
        except json.JSONDecodeError:
            return prefix.strip().rstrip("_"), {}
    return None, {}


def read_saif_duration(path: Path) -> tuple[int | None, str | None]:
    duration = None
    timescale = None
    with path.open(errors="replace") as handle:
        for _ in range(40):
            line = handle.readline()
            if not line:
                break
            duration_match = re.search(r"\(DURATION\s+([0-9]+)\)", line)
            scale_match = re.search(r"\(TIMESCALE\s+([^\)]+)\)", line)
            if duration_match:
                duration = int(duration_match.group(1))
            if scale_match:
                timescale = scale_match.group(1).strip()
            if duration is not None and timescale is not None:
                break
    return duration, timescale


def duration_seconds(duration: int | None, timescale: str | None) -> float | None:
    if duration is None or timescale is None:
        return None
    match = re.fullmatch(r"(?:1\s*)?(fs|ps|ns|us|ms|s)", timescale)
    if not match:
        return None
    factor = {
        "fs": 1e-15,
        "ps": 1e-12,
        "ns": 1e-9,
        "us": 1e-6,
        "ms": 1e-3,
        "s": 1.0,
    }[match.group(1)]
    return duration * factor


def parse_run(run_dir: Path) -> dict:
    status = (run_dir / "STATUS").read_text().strip()
    manifest = read_manifest(run_dir / "run_manifest.txt")
    report_text = (run_dir / "power_post_route.rpt").read_text(errors="replace")
    xml_path = run_dir / "power_post_route.xml"
    if xml_path.is_file():
        xml_root = ET.parse(xml_path).getroot()
        summary = first_table_map(find_section(xml_root, "Summary"))
        components = first_table_map(find_section(xml_root, "On-Chip Components"))
    else:
        summary, components = text_report_maps(report_text)
    metric_name, metric = read_metric(run_dir / "simulation_summary.txt")
    duration, timescale = read_saif_duration(run_dir / "activity_100mhz.saif")
    seconds = duration_seconds(duration, timescale)

    match_text = summary.get("Design Nets Matched", "")
    match = re.search(r"([0-9]+)%\s*\(([0-9]+)/([0-9]+)\)", match_text)
    matched_nets = int(match.group(2)) if match else None
    design_nets = int(match.group(3)) if match else None
    matched_exact_percent = (
        100.0 * matched_nets / design_nets
        if matched_nets is not None and design_nets
        else None
    )
    dynamic_w = as_float(summary.get("Dynamic (W)"))
    path_parts = run_dir.parts
    raw_index = path_parts.index("raw")
    module = manifest.get("module", path_parts[raw_index - 1])
    variant = manifest.get("variant", path_parts[raw_index + 1])
    work_name, count_key = WORK_UNITS.get(module, ("work_item", None))
    work_count = int(metric[count_key]) if count_key and count_key in metric else 1
    energy_nj = None
    if dynamic_w is not None and seconds is not None and work_count:
        energy_nj = dynamic_w * seconds * 1e9 / work_count

    design_match = re.search(r"^\| Design\s*:\s*(\S+)", report_text, re.MULTILINE)
    power_console = (run_dir / "power.console.log").read_text(errors="replace")
    x_warning_count = len(re.findall(r"\[Power 33-288\]", power_console))
    capture_mode = manifest.get("saif_capture_mode", "full_dut_internal")

    if status == "INVALID_SAIF_COVERAGE":
        qualification = "diagnostic_low_coverage"
    elif module == "02_attention_a8w8_projection":
        qualification = "diagnostic_high_x"
    elif capture_mode.startswith("sampled_internal") and x_warning_count:
        qualification = "valid_sampled_with_x_warning"
    elif capture_mode.startswith("sampled_internal"):
        qualification = "valid_sampled"
    elif x_warning_count:
        qualification = "valid_with_x_warning"
    else:
        qualification = "valid"

    row = {
        "module": module,
        "variant": variant,
        "status": status,
        "qualification": qualification,
        "run_dir": str(run_dir),
        "design": design_match.group(1) if design_match else None,
        "clock_mhz": int(manifest.get("clock_mhz", "100")),
        "method": manifest.get(
            "method", "post_route_report_power_with_behavioral_saif"
        ),
        "saif_capture_mode": capture_mode,
        "total_on_chip_w": as_float(summary.get("Total On-Chip Power (W)")),
        "dynamic_w": dynamic_w,
        "device_static_w": as_float(summary.get("Device Static (W)")),
        "confidence": summary.get("Confidence Level"),
        "matched_percent": int(match.group(1)) if match else None,
        "matched_exact_percent": matched_exact_percent,
        "matched_nets": matched_nets,
        "design_nets": design_nets,
        "clock_w": as_float(components.get("Clocks")),
        "clb_logic_w": as_float(components.get("CLB Logic")),
        "signals_w": as_float(components.get("Signals")),
        "dsp_w": as_float(components.get("DSPs")) or 0.0,
        "block_ram_w": as_float(components.get("Block RAM")) or 0.0,
        "uram_w": as_float(components.get("UltraRAM")) or 0.0,
        "saif_duration": duration,
        "saif_timescale": timescale,
        "saif_duration_us": seconds * 1e6 if seconds is not None else None,
        "x_over_50pct_warning_count": x_warning_count,
        "metric_name": metric_name,
        "work_unit": work_name,
        "work_count": work_count,
        "dynamic_energy_nj_per_work_unit": energy_nj,
        "metric": metric,
    }
    return row


def measured_runs(result_root: Path) -> list[Path]:
    latest: dict[tuple[str, str], Path] = {}
    for status in result_root.glob("*/raw/*/power/*/STATUS"):
        if status.read_text().strip() not in {"PASS", "INVALID_SAIF_COVERAGE"}:
            continue
        run_dir = status.parent
        required = ["power_post_route.rpt", "activity_100mhz.saif"]
        if not all((run_dir / item).is_file() for item in required):
            continue
        parts = run_dir.relative_to(result_root).parts
        key = (parts[0], parts[2])
        if key not in latest or run_dir.name > latest[key].name:
            latest[key] = run_dir
    return sorted(
        latest.values(),
        key=lambda p: (
            p.relative_to(result_root).parts[0],
            VARIANT_ORDER.get(p.relative_to(result_root).parts[2], 99),
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_root", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    rows = [parse_run(path) for path in measured_runs(args.result_root)]

    json_path = args.json or args.result_root / "power_summary.json"
    csv_path = args.csv or args.result_root / "power_summary.csv"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")

    csv_fields = [key for key in rows[0] if key != "metric"] if rows else []
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in csv_fields})
    print(f"POWER_EXTRACT_PASS runs={len(rows)} csv={csv_path} json={json_path}")


if __name__ == "__main__":
    main()
