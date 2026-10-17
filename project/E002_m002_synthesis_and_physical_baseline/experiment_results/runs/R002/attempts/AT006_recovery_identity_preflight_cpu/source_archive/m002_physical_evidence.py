#!/usr/bin/env python3
"""Identity and diagnostic evidence for M002. Never qualifies physical signoff."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
import re

from emit_current_board_evidence import file_id, input_manifest, key_values, require, sha256, status_id

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "m002_physical_diagnostic_v1"


SYNTH_ANCHORS = {
    "inputs.sha256": "1dc14fef9dbe62ba0a55a7eebef3a5c0a277574c674e2d3310d5d69e10f711d3",
    "build_identity.txt": "4647130ebdfe11b9b853698a30d1cc6455e06e551307867421978411c71baa10",
    "fresh_synth_complete.txt": "346cceddd7180ad519b5862da92994c7067284568b3d1b765d50c28a886444b6",
    "synth_checkpoint_bindings.sha256": "9f2fffaca87d3afe0bb512cb381c72902239a3c57418b95579bafc73cb365f46",
    "synth_checkpoint_bindings.json": "68ab2cf88b4462a574cfff3b4abb6b088ab672402f7533fad622afcbc38eb39d",
    "status.json": "877b0eecf2736cb954aa72b2f37465ca4dd957f08f0587c27f98858e8b508937",
}


def synth_lineage(project: Path, report: Path, attempt: Path) -> dict:
    for name, digest in SYNTH_ANCHORS.items():
        anchor = (report if name in {"inputs.sha256", "build_identity.txt", "fresh_synth_complete.txt"} else attempt) / name
        require(sha256(anchor) == digest, f"frozen synthesis identity record changed: {anchor}")
    status_id(report / "launcher_status.txt", "synth", project)
    status = json.loads((attempt / "status.json").read_text())
    require(status["exit_code"] == 0 and status["native_exit_code"] == 0,
            "original synthesis launcher/supervisor did not succeed")
    require(not status["stop_reason"] and not status["owned_survivors"],
            "original synthesis was stopped or retains owned processes")
    rows = input_manifest(report / "inputs.sha256")
    dcps = input_manifest(attempt / "synth_checkpoint_bindings.sha256")
    binding = json.loads((attempt / "synth_checkpoint_bindings.json").read_text())
    require(status.get("stage") == "synth" and status.get("project") == str(project) and
            status.get("report") == str(report) and binding.get("project") == str(project),
            "original synthesis project/report identity mismatch")
    require(len(rows) == 339 and len(dcps) == 45, "incomplete frozen source/checkpoint manifests")
    require(len(binding["run_records"]) == 23 and len(binding["consumed_ip_records"]) == 22,
            "incomplete actual top/OOC checkpoint lineage")
    produced, consumed, names = set(), set(), set()
    for run in binding["run_records"]:
        name = run["run"]
        require(name not in names and (name == "synth_1" or
                (name.startswith("scalellm_vcu118_f05_bd_") and name.endswith("_synth_1"))),
                "duplicate/foreign synthesis run")
        names.add(name)
        directory = project / "scalellm_vcu118_f05.runs" / name
        expected_name = "scalellm_vcu118_f05_bd_wrapper.dcp" if name == "synth_1" else name.removesuffix("_synth_1") + ".dcp"
        require(Path(run["checkpoint"]) == directory / expected_name and
                Path(run["end_receipt"]) == directory / ".vivado.end.rst", "run artifact outside its actual run")
        produced.add(Path(run["checkpoint"]))
        receipt = Path(run["end_receipt"])
        require(receipt.is_file() and not receipt.with_name(".vivado.error.rst").exists(),
                f"missing/failed original synthesis receipt: {receipt}")
        require(Path(run["checkpoint"]) in dcps, "unbound synthesis checkpoint")
    for record in binding["consumed_ip_records"]:
        path = Path(record["path"])
        require(path.is_relative_to(project / "scalellm_vcu118_f05.gen") and path not in consumed and
                record["cell"].startswith("scalellm_vcu118_f05_bd_i/"), "duplicate/foreign consumed checkpoint")
        consumed.add(path)
        matches = [p for p in produced if p.name == path.name]
        require(len(matches) == 1 and dcps.get(path) == dcps[matches[0]], "actual IP read is not its frozen synthesized copy")
    require("synth_1" in names and len(produced) == 23 and len(consumed) == 22 and
            produced.isdisjoint(consumed) and set(dcps) == produced | consumed and
            set(binding["checkpoints"]) == {str(p) for p in dcps}, "DCP manifest is not the complete actual 45-path set")
    for path, digest in dcps.items():
        require(binding["checkpoints"][str(path)]["sha256"] == digest, "DCP binding hash mismatch")
    return {
        "project": str(project), "source_rows": len(rows), "checkpoint_paths": len(dcps),
        "manifest": file_id(report / "inputs.sha256"),
        "identity": file_id(report / "build_identity.txt"),
        "completion": file_id(report / "fresh_synth_complete.txt"),
        "checkpoint_manifest": file_id(attempt / "synth_checkpoint_bindings.sha256"),
        "checkpoint_bindings": file_id(attempt / "synth_checkpoint_bindings.json"),
        "managed_status": file_id(attempt / "status.json"),
    }


def timing_metrics(path: Path) -> dict:
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        if "WNS(ns)" in line and "TNS Failing Endpoints" in line:
            for row in lines[i + 1:i + 6]:
                words = row.split()
                if len(words) != 12:
                    continue
                try:
                    values = [float(x) for x in words]
                except ValueError:
                    continue
                names = ("wns", "tns", "setup_failing_endpoints", "setup_total_endpoints",
                         "whs", "ths", "hold_failing_endpoints", "hold_total_endpoints",
                         "wpws", "tpws", "pw_skew_failing_endpoints", "pw_skew_total_endpoints")
                return dict(zip(names, values))
    raise ValueError(f"missing complete timing summary: {path}")


def timing_verdict(metrics: dict) -> str:
    keys = ("wns", "whs", "wpws", "tns", "ths", "tpws",
            "setup_failing_endpoints", "hold_failing_endpoints", "pw_skew_failing_endpoints")
    if not all(math.isfinite(metrics[x]) for x in keys):
        return "NOT_EVALUABLE"
    return "PASS" if (all(metrics[x] >= 0 for x in keys[:6]) and
                      all(metrics[x] == 0 for x in keys[6:])) else "FAIL"


def cdc_critical_records(path: Path) -> set[tuple[str, str, str, str, str]]:
    from collections import Counter
    lines = path.read_text().splitlines()
    require("CDC Report" in lines, "missing actual CDC report header")
    declared, observed = {}, Counter()
    clocks, result, critical_count = {}, set(), 0
    for line in lines:
        summary = re.match(r"^(CDC-\d+)\s+(Info|Warning|Critical)\s+(\d+)\s", line)
        if summary:
            key = summary.group(1, 2)
            require(key not in declared, "duplicate CDC summary category")
            declared[key] = int(summary.group(3))
        for key in ("Source Clock", "Destination Clock"):
            if line.startswith(key + ":"):
                clocks[key] = line.split(":", 1)[1].strip()
        match = re.match(r"^\s*\d+\s+(CDC-\d+)\s+(Info|Warning|Critical)\s+", line)
        if match:
            require("Source Clock" in clocks and "Destination Clock" in clocks, "CDC detail lacks actual clock group")
            observed[match.group(1, 2)] += 1
            if match.group(2) != "Critical":
                continue
            critical_count += 1
            fields = re.split(r"\s{2,}", line.strip())
            require(len(fields) >= 5, "unparsed critical CDC row")
            result.add((match.group(1), clocks["Source Clock"], clocks["Destination Clock"], fields[-2], fields[-1]))
    require(bool(declared) and bool(observed) and dict(observed) == {k:v for k,v in declared.items() if v} and
            len(result) == critical_count, "CDC report has unparsed/missing/duplicate rows or incomplete summary")
    return result


def critical_coverage(report: Path, original: Path) -> dict:
    expected = cdc_critical_records(original)
    actual = cdc_critical_records(report)
    require(len(expected) == 6 and actual <= expected, "new/unclassified critical CDC path")
    return {"known_original": len(expected), "remaining_known": len(actual), "new_critical": 0}


def check_timing_counts(path: Path) -> dict:
    rows = re.findall(r"^\d+\. checking ([a-z_]+) \((\d+)\)", path.read_text(), re.M)
    require(bool(rows), f"missing check_timing categories: {path}")
    return {name: int(count) for name, count in rows}


def timing_objects(path: Path, category: str) -> set[str]:
    lines = path.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(rf"^\d+\. checking {re.escape(category)} \(", line)]
    require(bool(starts), f"missing check_timing section {category}")
    start = starts[-1]
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^\d+\. checking ", lines[i])), len(lines))
    objects = set()
    for line in lines[start + 1:end]:
        if not line or line[0].isspace() or line.startswith("-"):
            continue
        if category in {"no_input_delay", "no_output_delay"}:
            require(re.fullmatch(r"[A-Za-z_][\w\[\].]*", line) is not None, "unparsed IO timing object")
        else:
            require("/" in line, f"unparsed timing endpoint: {line}")
        require(line not in objects, "duplicate timing endpoint")
        objects.add(line)
    expected = check_timing_counts(path)[category]
    require(len(objects) == expected, f"{category} endpoint count mismatch: {len(objects)} != {expected}")
    return objects


def debug_gap_coverage(path: Path, fanout: set[str], verified: bool) -> bool:
    no_clock = timing_objects(path, "no_clock")
    unconstrained = timing_objects(path, "unconstrained_internal_endpoints")
    pattern = re.compile(r"^scalellm_vcu118_f05_bd_i/ddr4_[01]/inst/u_ddr4_mem_intfc/u_ddr_cal_top/u_ddr_cal/(U_XSDB_SLAVE|u_xsdb_arbiter)/")
    return bool(verified and no_clock and unconstrained and no_clock <= fanout and
                {x.rsplit("/", 1)[0] for x in unconstrained} <= {x.rsplit("/", 1)[0] for x in fanout} and
                all(pattern.match(x) for x in no_clock | unconstrained))


def reset_io_coverage(path: Path) -> dict:
    inputs, outputs = timing_objects(path, "no_input_delay"), timing_objects(path, "no_output_delay")
    require(inputs <= {"pcie_perstn"} and outputs <= {"ddr4_sdram_c1_reset_n", "ddr4_sdram_c2_reset_n"},
            "new/unclassified untimed IO port")
    return {"known_async_reset_inputs": sorted(inputs), "known_ddr_reset_outputs": sorted(outputs)}


def hash_registry(point: str, report: Path) -> tuple[dict, dict]:
    registry = report / f"xdc_registry_{point}.tsv"
    lines = registry.read_text().splitlines()
    require(len(lines) > 1 and lines[0].split("\t") == ["path", "USED_IN", "USED_IN_SYNTHESIS",
        "USED_IN_IMPLEMENTATION", "IS_ENABLED", "SCOPED_TO_REF", "SCOPED_TO_CELLS", "PROCESSING_ORDER", "SHA256"],
        "missing/full XDC metadata header")
    hashed, metadata, hashes = [lines[0]], {}, {}
    for row in lines[1:]:
        cells = row.split("\t")
        require(len(cells) == 9 and cells[0] not in hashes, "malformed/duplicate XDC registry row")
        path = Path(cells[0])
        require(path.is_absolute() and path.is_file(), f"registered XDC missing: {path}")
        cells[-1] = sha256(path)
        hashes[str(path)], metadata[str(path)] = cells[-1], cells[1:-1]
        hashed.append("\t".join(cells))
    (report / f"xdc_registry_{point}_hashed.tsv").write_text("\n".join(hashed) + "\n")
    (report / f"xdc_sources_{point}.sha256").write_text("".join(
        f"{digest}  {name}\n" for name, digest in sorted(hashes.items())))
    return metadata, hashes


def constraint_chain(point: str, report: Path) -> dict:
    import os
    if os.environ.get("HAP_EXECUTION_MODE") == "checkpoint_restored_commands":
        return recovery_constraints(point, report)
    metadata, hashes = hash_registry(point, report)
    registry = report / f"xdc_registry_{point}_hashed.tsv"
    actual = report / f"actual_xdc_reads_{point}.json"
    run_log = Path(os.environ["HAP_PROJECT_DIR"]) / "scalellm_vcu118_f05.runs/impl_1/runme.log"
    records = []
    if point != "project" and run_log.exists():
        for number, line in enumerate(run_log.read_text(errors="replace").splitlines(), 1):
            match = re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?", line)
            if match:
                path = Path(match.group(1))
                hashes[str(path)] = sha256(path)
                records.append({"line": number, "path": str(path), "scope": match.group(2), "sha256": hashes[str(path)]})
    if point == "init":
        require(bool(records), "INIT has no actual constraint read records")
    actual.write_text(json.dumps({"records": records}, indent=2) + "\n")
    previous = {"init": "project", "opt": "init", "place": "opt", "physopt": "place"}.get(point)
    parent = report / f"constraints_{previous}.json" if previous else None
    if point == "route" or (point == "project" and os.environ.get("HAP_STAGE") == "route"):
        parent = Path(os.environ["HAP_PLACE_REPORT_DIR"]) / "constraints_physopt.json"
    if parent:
        old = json.loads(parent.read_text())
        for name, digest in old["hashes"].items():
            require(Path(name).is_file() and sha256(Path(name)) == digest, f"effective/candidate constraint changed: {name}")
        for name, properties in old["metadata"].items():
            require(name in metadata and metadata[name] == properties, f"XDC missing/scope/order/USED_IN changed: {name}")
        additions = set(hashes) - set(old["hashes"])
        if point != "init":
            allowed_path = report / f"tool_debug_xdc_{point}.txt"
            allowed = set(allowed_path.read_text().splitlines()) if allowed_path.exists() else set()
            require(not additions or (point == "opt" and additions <= allowed), f"unclassified new constraints: {sorted(additions)}")
        hashes = {**old["hashes"], **hashes}
    result = {"phase": point, "hashes": hashes, "metadata": metadata,
              "registry": file_id(registry), "actual_reads": file_id(actual),
              "parent": file_id(parent) if parent else None}
    (report / f"constraints_{point}.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def placement_coverage(counts: dict, blackboxes: int) -> bool:
    return blackboxes == 0 and all(counts.get(x, -1) == 0 for x in (
        "no_clock", "unconstrained_internal_endpoints", "multiple_clock", "generated_clocks", "loops", "pulse_width_clock"))


def utilization_metrics(path: Path) -> dict:
    result = {}
    for line in path.read_text().splitlines():
        cells = [x.strip() for x in line.split("|")[1:-1]]
        if len(cells) == 6 and cells[0].rstrip("*") in {"CLB LUTs", "CLB Registers", "DSPs", "Block RAM Tile", "URAM"}:
            result[cells[0].rstrip("*")] = {"used": float(cells[1]), "available": float(cells[4]), "percent": float(cells[5])}
    require(len(result) == 5, "incomplete actual resource capacity report")
    require(all(x["used"] <= x["available"] for x in result.values()), "aggregate device capacity exceeded")
    return result


def reset_structure(path: Path) -> dict:
    """Bounded primitive/connectivity proof. Unknown structures remain a gate failure."""
    import itertools
    cells, pins, receivers, outputs, gate_inputs, targets = {}, {}, [], {}, {}, set()
    for row in path.read_text().splitlines():
        f = row.split("\t")
        if f[0] == "CELL":
            require(len(f) >= 5 and f[1] not in cells, "duplicate/malformed structural cell")
            cells[f[1]] = {"ref": f[2], "init": f[3], "async": f[4], **dict(x.split("=",1) for x in f[5:])}
        elif f[0] == "PIN":
            require(len(f) == 7 and f[1] not in pins, "duplicate/malformed structural pin")
            pins[f[1]] = {"refpin": f[2], "direction": f[3], "nets": f[4].split(),
                          "clocks": f[5].split(), "drivers": [x.strip("{}") for x in f[6].split()]}
        elif f[0] == "TARGET":
            targets.add(f[1])
        elif f[0] == "IO_RECEIVER":
            receivers.append(f[1:])
        elif f[0] == "IO_OUTPUT":
            outputs[f[1]] = [x.strip("{}") for x in f[2].split()]
        elif f[0] == "GATE_INPUT":
            gate_inputs[f[1]] = [x.strip("{}") for x in f[2].split()]
    issues, chains, aux = [], [], []
    def check(ok, message):
        if not ok:
            issues.append(message)
    def same(a, b):
        return bool(set(pins.get(a, {}).get("nets", [])) & set(pins.get(b, {}).get("nets", [])))
    def init_one(text):
        return text.lower() in {"1", "1'b1", "1'h1"}
    def evaluate(pin, symbols, seen=frozenset()):
        if pin in symbols:
            return symbols[pin]
        for symbolic_pin, value in symbols.items():
            if same(pin, symbolic_pin):
                return value
        require(pin not in seen and pin in pins, f"unresolved/cyclic logic pin {pin}")
        seen = seen | {pin}
        cell, refpin = pin.rsplit("/", 1)
        obj = cells.get(cell, {})
        ref = obj.get("ref", "")
        if pins[pin]["direction"] == "IN":
            drivers = pins[pin]["drivers"]
            require(len(drivers) == 1, f"nonunique/missing driver for {pin}: {drivers}")
            return evaluate(drivers[0], symbols, seen)
        if ref in {"VCC", "GND"}:
            return ref == "VCC"
        if re.fullmatch(r"LUT[1-6]", ref) and refpin == "O":
            n = int(ref[-1])
            value = obj["init"].lower()
            match = re.fullmatch(r"(?:\d+)'h([0-9a-f]+)", value)
            require(match is not None, f"unparsed LUT INIT {value}")
            address = sum(int(evaluate(f"{cell}/I{i}", symbols, seen)) << i for i in range(n))
            return bool((int(match.group(1), 16) >> address) & 1)
        if ref in {"IBUF", "OBUF", "BUF", "BUFG", "BUFGCE"} and refpin == "O":
            return evaluate(cell + "/I", symbols, seen)
        raise ValueError(f"unclassified logic primitive {cell} {ref}/{refpin}")
    def constant(pin, expected):
        try:
            return evaluate(pin, {}) == expected
        except ValueError:
            return False
    def function(pin, symbols, expected):
        try:
            for values in itertools.product((False, True), repeat=len(symbols)):
                if evaluate(pin, dict(zip(symbols, values))) != expected(values):
                    return False
            return True
        except ValueError as exc:
            issues.append(str(exc))
            return False
    base = "scalellm_vcu118_f05_bd_i/"
    core_clock = "clk_out1_scalellm_vcu118_f05_bd_clk_core_0"
    groups = [("core_gate", "u_base_reset_cdc", core_clock),
              ("core_gate", "u_ready0_cdc", core_clock), ("core_gate", "u_ready1_cdc", core_clock)]
    for d in (0, 1):
        groups.extend((f"d{d}_gate", x, "mmcm_clkout0" + ("_1" if d else ""))
                      for x in ("u_base_reset_cdc", "u_ready_cdc"))
    for gate, module, clock in groups:
        root = f"{base}{gate}/inst/{module}"
        stages = [f"{root}/arststages_ff_reg[{i}]" for i in range(4)]
        for i, cell in enumerate(stages):
            obj = cells.get(cell, {})
            check(obj.get("ref") == "FDCE" and init_one(obj.get("init", "")) and
                  obj.get("async", "").lower() in {"1", "true"}, f"async reset stage primitive/INIT/ASYNC_REG {cell}")
            check(pins.get(cell + "/C", {}).get("clocks") == [clock] and obj.get("IS_C_INVERTED", "0").lower() in {"0","false"}, f"async reset destination clock/edge {cell}")
            check(constant(cell + "/CE", True), f"async reset CE {cell}")
            check(constant(cell + "/D", True) if i == 0 else same(cell + "/D", stages[i-1] + "/Q"), f"async reset shift connectivity {cell}")
            check(same(cell + "/CLR", stages[0] + "/CLR"), f"async reset common clear {cell}")
        input_name = "base_aresetn" if module == "u_base_reset_cdc" else (
            "async_ready" + module.removeprefix("u_ready").removesuffix("_cdc"))
        symbolic_pin = base + f"{gate}/inst/{input_name}"
                # Native primitive input inversion is part of the actual polarity.
        inverted = cells.get(stages[0], {}).get("IS_CLR_INVERTED", "0").lower() in {"1","true"}
        check(function(stages[0] + "/CLR", [symbolic_pin], lambda v: v[0] if inverted else not v[0]), f"async assertion polarity/cone {root}")
        chains.append({"root": root, "stages": stages, "clock": clock, "source": symbolic_pin})
    # All known critical CDC receivers are exactly these two ready clears and four AUX inputs.
    expected_targets = {base + f"core_gate/inst/u_ready{d}_cdc/arststages_ff_reg[0]/CLR" for d in (0, 1)}
    for d in (0, 1):
        gate_symbols = [base + f"d{d}_gate/inst/{module}/arststages_ff_reg[3]/Q" for module in ("u_base_reset_cdc", "u_ready_cdc")]
        for psr in ("psr0", "psr_aclk1"):
            root = base + f"d{d}_smc/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX"
            stages = [f"{root}/syncstages_ff_reg[{i}]" for i in range(4)]
            expected_targets.add(stages[0] + "/D")
            for i, cell in enumerate(stages):
                obj = cells.get(cell, {})
                check(obj.get("ref") == "FDRE" and obj.get("async", "").lower() in {"true", "1"}, f"AUX stage primitive/ASYNC_REG {cell}")
                check(pins.get(cell + "/C", {}).get("clocks") == [core_clock], f"AUX destination clock {cell}")
                check(constant(cell + "/CE", True) and constant(cell + "/R", False), f"AUX CE/reset {cell}")
                if i:
                    check(same(cell + "/D", stages[i-1] + "/Q"), f"AUX shift connectivity {cell}")
            check(function(stages[0] + "/D", gate_symbols, lambda v: not all(v)), f"AUX active-low synchronized gate polarity/cone {root}")
            aux.append({"root": root, "stages": stages, "source_synchronized_terms": gate_symbols, "destination_clock": core_clock})
    check(targets == expected_targets and len(targets) == 6, "exact six known CDC targets missing/foreign")
    # The source qualifier's actual fan-in is retained, not inferred from a name.
    for d in (0, 1):
        key = base + f"core_gate/inst/async_ready{d}"
        starts = gate_inputs.get(key, [])
        check(bool(starts) and all(x.startswith(base + f"ddr4_{d}/") for x in starts) and
              any("div_clk_rst_r1_reg/" in x for x in starts) and
              any("calib" in x.lower() for x in starts), f"MIG calibration/reset source qualifiers {key}")
        if len(starts) == 2:
            reset = next((i for i, x in enumerate(starts) if "div_clk_rst_r1_reg/" in x), None)
            check(reset is not None and function(key, starts, lambda v: v[1-reset] and not v[reset]), f"MIG calib && !ui_reset logic {key}")
        else:
            check(False, f"MIG source qualifier terminal count {key}")
        check(same(key, base + f"d{d}_gate/inst/async_ready"), f"core/DDR ready qualifier source identity d{d}")
    check(bool(receivers), "no external PCIe reset receiver evidence")
    for port, pin, ref in receivers:
        cell, terminal = pin.rsplit("/", 1)
        known_sync = (terminal == "D" and "syncstages_ff_reg[0]" in cell and
                      any(cell.startswith(base + x + "/") for x in ("rst_core", "rst_ddr0", "rst_ddr1")))
        known_vendor = cell.startswith(base + "xdma_0/") and (terminal in {"CLR", "PRE", "R", "RST", "SYSRST", "SYSRSTN", "RSTN", "GTRXRESET", "GTTXRESET"} or
                      (terminal == "D" and ("sync" in cell.lower() or "reset" in cell.lower() or "rst" in cell.lower())))
        check(port == "pcie_perstn" and (known_sync or known_vendor), f"unclassified PCIe reset receiver {pin} {ref}")
    for d in (0, 1):
        port = f"ddr4_sdram_c{d+1}_reset_n"
        starts = outputs.get(port, [])
        check(bool(starts) and all(x.startswith(base + f"ddr4_{d}/") for x in starts), f"external DDR reset actual MIG driver {port}")
    return {"qualified": not issues, "issues": issues, "async_reset_chains": chains, "aux_chains": aux,
            "critical_targets": sorted(targets), "gate_source_startpoints": gate_inputs,
            "pcie_reset_receivers": receivers, "ddr_reset_output_startpoints": outputs,
            "assumptions": ["MIG calibration and UI reset are reset-level qualifiers; no data protocol waiver",
                            "external reset IO classification is diagnostic; board reset electrical/timing signoff remains OPEN"],
            "source": file_id(path)}


def checkpoint_package(path: Path) -> dict:
    import hashlib
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as archive:
        raw=archive.read('dcp.xml')
    root=ET.fromstring(raw)
    values={node.tag:node.get('Name') for node in root}
    expected={'Part':'xcvu9p-flga2104-2L-e','Top':'scalellm_vcu118_f05_bd_wrapper',
              'BoardPart':'xilinx.com:vcu118:part0:2.0','BUILD_NUMBER':'6299465','PRODUCT':'Vivado v2025.2 (64-bit)'}
    require(root.tag=='Checkpoint' and all(values.get(k)==v for k,v in expected.items()), 'checkpoint package part/top/board/tool identity mismatch')
    return {**expected,'xml_sha256':hashlib.sha256(raw).hexdigest()}


def recovery_parent(source: Path, project: Path, lineage: dict, report: Path) -> dict:
    """Bind a failed POST's genuine project-init checkpoint, never its success."""
    require(source.is_relative_to(ROOT / 'vivado/reports') and project.is_relative_to(ROOT / 'vivado/project'), 'foreign checkpoint recovery root')
    command = json.loads((source / 'command.json').read_text())
    attempt = Path(command['managed_attempt'])
    status = json.loads((attempt / 'status.json').read_text())
    require(status['project'] == str(project) and status['report'] == str(source) and status['stage'] == 'place' and
            status['exit_code'] == 1 and status['native_exit_code'] == 1 and not status['stop_reason'] and
            not status['owned_survivors'], 'recovery parent is not this completed failed project-init attempt')
    launcher = key_values(source / 'launcher_status.txt')
    require(launcher['exit_code'] == '1' and launcher['native_exit_code'] == '1' and launcher['project'] == str(project),
            'recovery original launcher mismatch')
    require(command['synthesis'] == lineage, 'recovery synthesis lineage changed')
    validate_stage_archive(source, file_id(source / 'stage_inputs.sha256'), file_id(source / 'archived_sources.sha256'))
    result = key_values(source / 'init_result.txt')
    require(result['completed'] == '0' and result['phase'] == 'init', 'recovery must not reinterpret failed INIT as PASS')
    log = source / 'implementation_run.log'
    text = log.read_text(errors='replace')
    checkpoint = file_id(source / 'init.dcp')
    package = checkpoint_package(source / 'init.dcp')
    require('link_design completed successfully' in text and f"The checkpoint '{checkpoint['path']}' has been generated" in text and
            'source ' in text and 'm002_diagnostic_init_post.tcl' in text and
            'M002_DIAGNOSTIC_STEP_COMPLETED init' not in text and '\nCommand: opt_design' not in text,
            'checkpoint is not the actually generated project-init-before-opt state')
    records = []
    registry = source / 'xdc_registry_project_hashed.tsv'
    rows = registry.read_text().splitlines()
    require(len(rows) == 163, 'recovery candidate project XDC registry must contain all 162 files')
    metadata, hashes = {}, {}
    for row in rows[1:]:
        f = row.split('\t')
        require(len(f) == 9 and f[0] not in metadata and sha256(Path(f[0])) == f[-1], 'recovery registered XDC changed/duplicated')
        metadata[f[0]], hashes[f[0]] = f[1:-1], f[-1]
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?", line)
        if match:
            path = Path(match.group(1)); digest = sha256(path)
            require(str(path) not in hashes or hashes[str(path)] == digest, 'recovery loaded XDC changed')
            hashes[str(path)] = digest
            records.append(dict(line=number, path=str(path), scope=match.group(2), sha256=digest))
    require(bool(records), 'recovery has no original actual XDC parse order/scope')
    original = {
        'phase': 'project_init_after_link_before_opt', 'original_execution_state': 'failed_post_probe',
        'original_impl_run_remains': 'FAIL', 'checkpoint': checkpoint, 'checkpoint_package':package,
        'status': file_id(attempt / 'status.json'), 'launcher': file_id(source / 'launcher_status.txt'),
        'child_log': file_id(log), 'command': file_id(source / 'command.json'),
        'stage_inputs': file_id(source / 'stage_inputs.sha256'), 'archive': file_id(source / 'archived_sources.sha256'),
        'implementation_settings': file_id(source / 'implementation_settings.txt'),
        'effective_build_identity': file_id(source / 'effective_build_identity.txt'),
        'source_registry': file_id(registry), 'source_metadata': metadata,
        'hashes': hashes, 'actual_reads': records, 'synthesis': lineage,
        'inherited_reports': {n: file_id(source / n) for n in ('timing_init.rpt','utilization_init.rpt','drc_init.rpt','reset_register_probe_init.tsv')},
        'constraint_mode': 'embedded_checkpoint_inherited',
        'hash_observation': '162 source hashes verified against pre-link registry; actual read sources captured before this continuation',
    }
    (report / 'recovery_parent.json').write_text(json.dumps(original, indent=2) + '\n')
    return original


def recovery_constraints(point: str, report: Path) -> dict:
    import os
    metadata, hashes = hash_registry(point, report)
    parent = report / 'recovery_parent.json'
    if os.environ.get('HAP_STAGE') == 'route':
        parent = Path(os.environ['HAP_PLACE_REPORT_DIR']) / 'constraints_physopt.json'
    old = json.loads(parent.read_text())
    original_metadata = old.get('candidate_metadata', old.get('source_metadata', old.get('metadata')))
    require(metadata == original_metadata, 'current candidate project XDC metadata changed from checkpoint parent')
    for name, digest in old['hashes'].items():
        require(Path(name).is_file() and sha256(Path(name)) == digest, f'inherited effective/candidate XDC changed: {name}')
    hashes = {**old['hashes'], **hashes}
    # Each phase inherits every prior effective constraint, then classifies
    # only actual new tool-debug sources. No fabricated read_xdc operation.
    previous = {'init':'project','opt':'init','place':'opt','physopt':'place'}.get(point)
    prior = report / f'constraints_{previous}.json' if previous else parent
    if point == 'route':
        prior = parent
    previous_value = json.loads(prior.read_text())
    for name, digest in previous_value['hashes'].items():
        require(Path(name).is_file() and sha256(Path(name)) == digest, f'prior effective XDC changed: {name}')
    hashes = {**previous_value['hashes'], **hashes}
    debug_registry = report / f'tool_debug_registry_{point}.tsv'
    debug_metadata = dict(previous_value.get('tool_debug_metadata', {}))
    if debug_registry.exists():
        for row in debug_registry.read_text().splitlines()[1:]:
            f = row.split('\t');require(len(f)==9,'malformed tool debug metadata')
            require(f[0] in set((report / f'tool_debug_xdc_{point}.txt').read_text().splitlines()),'unowned debug constraint')
            require(f[0] not in debug_metadata or debug_metadata[f[0]] == f[1:-1], 'tool debug XDC metadata changed')
            require(f[0] in hashes or point == 'opt', 'new tool debug constraints outside OPT materialization')
            debug_metadata[f[0]] = f[1:-1];hashes[f[0]]=sha256(Path(f[0]))
    actual=[]
    live_log=report/'vivado.log'
    if live_log.exists():
        for number,line in enumerate(live_log.read_text(errors='replace').splitlines(),1):
            match=re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?",line)
            if not match:continue
            name=match.group(1)
            require(name in hashes,'new unclassified effective constraint during checkpoint continuation')
            actual.append(dict(line=number,path=name,scope=match.group(2),sha256=sha256(Path(name))))
    actual_path=report/f'actual_xdc_reads_{point}.json'
    actual_path.write_text(json.dumps(dict(mode='embedded_checkpoint_inherited',inherited_from=file_id(parent),new_actual_reads=actual),indent=2)+'\n')
    result=dict(phase=point,mode='embedded_checkpoint_inherited',candidate_metadata=metadata,metadata=metadata,
                tool_debug_metadata=debug_metadata,hashes=hashes,parent=file_id(prior),
                registry=file_id(report/f'xdc_registry_{point}_hashed.tsv'),actual_reads=file_id(actual_path))
    (report/f'constraints_{point}.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def hook_batch(point: str, report: Path) -> None:
    """One small process validates every frozen row; avoids 339 large forks."""
    import os
    lineage = synth_lineage(*(Path(os.environ[k]).resolve() for k in
        ("HAP_PROJECT_DIR", "HAP_SYNTH_REPORT_DIR", "HAP_SYNTH_ATTEMPT_DIR")))
    input_manifest(report / "stage_inputs.sha256")
    constraints = constraint_chain(point, report)
    counts = check_timing_counts(report / f"check_timing_{point}.rpt")
    require(all(counts.get(x, -1) == 0 for x in ("multiple_clock", "generated_clocks", "loops", "pulse_width_clock")),
            "unresolved clock definition/loop at diagnostic init/physical stage")
    bb = int(key_values(report / f"{point}_result.txt")["blackboxes"])
    internal = placement_coverage(counts, bb)
    coverage = "COMPLETE_INTERNAL"
    if not internal:
        require(point == "init", "unresolved blackbox or internal timing coverage before place")
        proof = key_values(report / "debug_proof_init.txt")["verified"] == "1"
        require(bb == 1, "INIT debug exception requires its unique actual blackbox")
        fanout = {row.split("\t")[2] for row in (report / "debug_init.tsv").read_text().splitlines()
                  if row.startswith("DEBUG_CLOCK_FANOUT\t")}
        require(debug_gap_coverage(report / "check_timing_init.rpt", fanout, proof), "unverified debug clock/blackbox gap")
        coverage = "PENDING_TOOL_DEBUG_MATERIALIZATION"
    cdc = critical_coverage(report / f"cdc_{point}.rpt", Path(os.environ["HAP_SYNTH_REPORT_DIR"]) / "cdc_post_synth.rpt")
    io = reset_io_coverage(report / f"check_timing_{point}.rpt")
    if point == "init":
        structure = {"qualified": False, "status": "DEFERRED_TO_OPT", "issues": []}
    elif point == "opt":
        structure = reset_structure(report / f"reset_graph_{point}.tsv")
        (report / f"reset_structure_{point}.json").write_text(json.dumps(structure, indent=2) + "\n")
    else:
        previous_report = Path(os.environ["HAP_PLACE_REPORT_DIR"]) if point == "route" else report
        structure = json.loads((previous_report / "reset_structure_opt.json").read_text())
    # INIT gathers evidence; OPT is the mandatory structural gate before place.
    require(point == "init" or structure["qualified"], "known reset CDC/IO structural conditions not established: " + str(structure.get("issues")))
    (report / f"admission_{point}.txt").write_text(f"clock_coverage {coverage}\ndiagnostic_eligible 1\n")
    (report / f"integrity_{point}.json").write_text(json.dumps({
        "observed_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": point,
        "synthesis": lineage, "resources": utilization_metrics(report / f"utilization_{point}.rpt"),
        "constraints": file_id(report / f"constraints_{point}.json"), "cdc_classification": cdc,
        "reset_io_classification": io, "reset_structure": structure}, indent=2) + "\n")


def artifact_id(path: Path) -> dict:
    path = path.resolve(strict=True)
    require(path.is_file(), f"missing artifact {path}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_identity(identity: dict) -> None:
    require(artifact_id(Path(identity["path"])) == identity, f"evidence identity changed: {identity['path']}")


def manifest_records(path: Path) -> dict[Path, str]:
    records = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, "malformed archived stage manifest")
        digest, name = match.groups()
        source = Path(name)
        require(source.is_absolute() and source not in records, "duplicate/relative stage input")
        records[source] = digest
    require(bool(records), "empty stage input manifest")
    return records


def validate_stage_archive(report: Path, stage_identity: dict, archive_identity: dict) -> dict:
    verify_identity(stage_identity)
    verify_identity(archive_identity)
    archive = input_manifest(Path(archive_identity["path"]))
    require(all(p.parent == report / "stage_sources" for p in archive), "stage archive outside immutable source snapshot")
    original = manifest_records(Path(stage_identity["path"]))
    for source, digest in original.items():
        archived = report / "stage_sources" / source.name
        if archived in archive:
            require(archive[archived] == digest, "archived execution code differs from old stage manifest")
        else:
            require(source.is_file() and sha256(source) == digest, f"design/probe input changed: {source}")
    return original


def prior_hooks(project: Path) -> None:
    owner = json.loads((project / "m002_physical_hook_owner.json").read_text())
    require(owner["project"] == str(project), "foreign implementation hook owner")
    report = Path(owner["report"])
    require(report.is_relative_to(ROOT / "vivado/reports"), "foreign implementation hook report")
    command = json.loads((report / "command.json").read_text())
    require(command["stage"] == "place" and command["synthesis"]["project"] == str(project), "foreign prior hook command")
    records = validate_stage_archive(report, owner["stage_inputs"], owner["archive"])
    required = {Path(__file__).parent / "m002_impl_threads.tcl", *Path(__file__).parent.glob("m002_diagnostic_*_post.tcl")}
    require(required <= set(records), "prior hook provenance missing expected scripts")


def parent_recovered_place(path: Path, project: Path, lineage: dict) -> dict:
    value=json.loads(path.read_text());report=path.parent
    require(value.get('schema')==SCHEMA and value.get('stage')=='place' and value.get('execution_mode')=='checkpoint_restored_commands', 'wrong recovered parent mode/schema')
    require(value.get('execution_state')=='completed' and value.get('diagnostic_eligible') is True and value.get('physical_signoff') is False and
            value.get('project')==str(project) and value.get('synthesis')==lineage,'recovered parent is not a completed qualified diagnostic')
    launcher=key_values(report/'launcher_status.txt')
    require(launcher.get('exit_code')=='0' and launcher.get('native_exit_code')=='0' and launcher.get('stage')=='place' and launcher.get('project')==str(project) and launcher.get('reports')==str(report),'recovered parent launcher failed')
    status=json.loads((Path(value['managed_attempt'])/'status.json').read_text())
    require(status['stage']=='place' and status['project']==str(project) and status['report']==str(report) and status['exit_code']==0 and
            status['native_exit_code']==0 and not status['stop_reason'] and not status['owned_survivors'],'recovered parent supervisor failed/survivors')
    for key in ('checkpoint','stage_inputs','archived_stage_sources','native_checkpoint_manifest','implementation_settings','constraints','recovery_parent','actual_xdc_reads'):
        verify_identity(value[key])
    validate_stage_archive(report,value['stage_inputs'],value['archived_stage_sources'])
    require(Path(value['checkpoint']['path'])==report/'physopt.dcp' and
            set(input_manifest(Path(value['native_checkpoint_manifest']['path'])))=={report/'physopt.dcp'},'recovered parent is not its actual physopt DCP')
    require(not value['native_parent_receipts'],'recovered parent must not fabricate project-run receipts')
    for point,command in (('opt','opt_design'),('place','place_design'),('physopt','phys_opt_design')):
        identity=value['command_receipts'][point];verify_identity(identity)
        receipt=key_values(Path(identity['path']))
        require(receipt.get('native_tcl_code')=='0' and receipt.get('command')==command and receipt.get('phase')==point,'recovered parent native phase failed')
    constraints=json.loads(Path(value['constraints']['path']).read_text())
    require(constraints['mode']=='embedded_checkpoint_inherited' and all(Path(n).is_file() and sha256(Path(n))==h for n,h in constraints['hashes'].items()),'recovered parent effective constraints changed')
    return value


def parent_place(path: Path, project: Path, lineage: dict) -> dict:
    value = json.loads(path.read_text())
    if value.get("execution_mode") == "checkpoint_restored_commands":
        return parent_recovered_place(path, project, lineage)
    require(value.get("schema") == SCHEMA and value.get("stage") == "place", "wrong parent diagnostic schema/stage")
    require(value.get("execution_state") == "completed" and value.get("diagnostic_eligible") is True,
            "parent placement is not a completed diagnostic candidate")
    require(value.get("project") == str(project) and value.get("physical_signoff") is False,
            "parent placement project/signoff identity mismatch")
    require(value["synthesis"] == lineage, "parent placement synthesis identity changed")
    report = path.parent
    launcher = key_values(report / "launcher_status.txt")
    require(launcher == {"stage": "place", "exit_code": "0", "native_exit_code": "0", "project": str(project), "reports": str(report)},
            "parent launcher did not actually succeed for this project/report")
    attempt = Path(value["managed_attempt"])
    status = json.loads((attempt / "status.json").read_text())
    require(status["stage"] == "place" and status["project"] == str(project) and status["report"] == str(report) and
            status["exit_code"] == 0 and status["native_exit_code"] == 0 and not status["stop_reason"] and
            not status["owned_survivors"], "parent supervisor did not actually finish successfully")
    command = json.loads((report / "command.json").read_text())
    require(command["managed_attempt"] == str(attempt) and command["synthesis"] == lineage and command["stage"] == "place",
            "parent command/managed identity mismatch")
    for key in ("checkpoint", "stage_inputs", "archived_stage_sources", "native_checkpoint_manifest", "implementation_settings", "constraints"):
        verify_identity(value[key])
    validate_stage_archive(report, value["stage_inputs"], value["archived_stage_sources"])
    native = input_manifest(Path(value["native_checkpoint_manifest"]["path"]))
    expected = project / "scalellm_vcu118_f05.runs/impl_1/scalellm_vcu118_f05_bd_wrapper_physopt.dcp"
    require(set(native) == {expected}, "parent native checkpoint is not this project's actual physopt")
    run = expected.parent
    receipts = value["native_parent_receipts"]
    require(set(receipts) == {".phys_opt_design.end.rst", ".vivado.end.rst"}, "missing native completion receipts")
    for name, identity in receipts.items():
        verify_identity(identity)
        require(sha256(run / name) == identity["sha256"], f"parent native completion receipt changed: {name}")
    require(not (run / ".phys_opt_design.error.rst").exists() and not (run / ".vivado.error.rst").exists(),
            "parent native implementation has an error receipt")
    old_constraints = json.loads(Path(value["constraints"]["path"]).read_text())
    require(all(Path(n).is_file() and sha256(Path(n)) == h for n, h in old_constraints["hashes"].items()), "parent effective XDC changed")
    return value


def route_counts(path: Path) -> dict:
    text = path.read_text()
    result = {}
    patterns = {"routable": r"# of routable nets", "fully_routed": r"# of fully routed nets",
                "unrouted": r"# of unrouted nets", "partially_routed": r"# of partially routed nets",
                "routing_errors": r"# of nets with routing errors"}
    for key, label in patterns.items():
        match = re.search(label + r"\s*[:|]?\s*([0-9,]+)", text, re.I)
        require(match is not None, f"missing actual route count: {key}")
        result[key] = int(match.group(1).replace(",", ""))
    require(result["routable"] > 0 and result["fully_routed"] <= result["routable"], "invalid/empty route statistics")
    result["complete"] = result["fully_routed"] == result["routable"] and all(
        result[k] == 0 for k in ("unrouted", "partially_routed", "routing_errors"))
    return result


def loaded_constraints(log: Path, output: Path, inherited: dict | None = None) -> dict:
    records = []
    for number, line in enumerate(log.read_text(errors="replace").splitlines(), 1):
        match = re.search(r"^Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?", line)
        if match:
            source = Path(match.group(1))
            require(source.is_file(), f"actual loaded constraint disappeared: {source}")
            records.append({"line": number, "path": str(source), "scope": match.group(2),
                            "sha256": sha256(source), "bytes": source.stat().st_size})
    require(bool(records) or inherited is not None, "no actual implementation XDC reads recorded")
    if inherited:
        if "recovery" in inherited:
            verify_identity(inherited["recovery"])
            original=json.loads(Path(inherited["recovery"]["path"]).read_text())
            require(original['phase']=='project_init_after_link_before_opt' and original['actual_reads'], 'missing inherited project-init constraints')
            verify_identity(original['checkpoint'])
            inherited={"mode":"embedded_checkpoint_inherited","recovery_parent":inherited['recovery'],"original_actual_reads":original['actual_reads']}
        else:
            verify_identity(inherited["evidence"])
            parent = json.loads(Path(inherited["evidence"]["path"]).read_text())
            verify_identity(parent["constraints"])
            verify_identity(parent["actual_xdc_reads"])
            inherited = {"mode": "checkpoint_inherited", "parent_checkpoint": inherited["checkpoint"],
                         "parent_constraints": parent["constraints"], "parent_actual_reads": parent["actual_xdc_reads"]}
    output.write_text(json.dumps({"source_log": str(log), "records": records, "inherited": inherited}, indent=2) + "\n")
    return file_id(output)


def finalize(stage: str, project: Path, report: Path, lineage: dict, parent: dict | None) -> dict:
    import os
    restored = os.environ.get("HAP_EXECUTION_MODE") == "checkpoint_restored_commands"
    point = "physopt" if stage == "place" else "route"
    result = key_values(report / f"{point}_result.txt")
    require(result.get("completed") == "1" and result.get("diagnostic_eligible") == "1",
            "physical hook did not complete/admit this diagnostic candidate")
    metrics = timing_metrics(report / f"timing_{point}.rpt")
    counts = check_timing_counts(report / f"check_timing_{point}.rpt")
    require(placement_coverage(counts, int(result["blackboxes"])), "physical coverage incomplete")
    checkpoint = file_id(report / f"{point}.dcp")
    required = [f"timing_{point}.rpt", f"check_timing_{point}.rpt", f"clocks_{point}.rpt",
                f"clock_interaction_{point}.rpt", f"cdc_{point}.rpt", f"drc_{point}.rpt",
                f"exceptions_{point}.rpt", f"pulse_width_{point}.rpt", f"bus_skew_{point}.rpt",
                f"utilization_{point}.rpt", f"paths_setup_{point}.rpt", f"paths_hold_{point}.rpt"]
    if stage == "route":
        required.append("route_status_route.rpt")
    evidence = {
        "schema": SCHEMA, "mode": "diagnostic", "stage": stage,
        "execution_mode": "checkpoint_restored_commands" if restored else "project_runs",
        "recovery_parent": file_id(report / "recovery_parent.json") if restored and stage == "place" else None,
        "command_receipts": {p:file_id(report/f"{p}_command_result.txt") for p in
            (("opt","place","physopt") if stage == "place" else ("route",))} if restored else {},
        "execution_state": "completed", "diagnostic_eligible": True,
        "timing_verdict": "FAIL" if timing_verdict(metrics) == "FAIL" else "NOT_EVALUABLE",
        "timing_summary_verdict": timing_verdict(metrics), "bus_skew_review": "OPEN", "physical_signoff": False,
        "managed_attempt": __import__("os").environ["HAP_CURRENT_ATTEMPT_DIR"],
        "project": str(project), "part": "xcvu9p-flga2104-2L-e", "tool_version": "2025.2",
        "synthesis": lineage, "stage_inputs": file_id(report / "stage_inputs.sha256"),
        "archived_stage_sources": file_id(report / "archived_sources.sha256"),
        "implementation_settings": file_id(report / "implementation_settings.txt"),
        "implementation_settings_scope": "candidate_project_settings" if restored else "effective_project_run_settings",
        "checkpoint": checkpoint, "metrics_ns": metrics, "clock_coverage": counts,
        "native_checkpoint_manifest": file_id(report / "implementation_checkpoint.sha256"),
        "constraints": file_id(report / f"constraints_{point}.json"),
        "native_parent_receipts": {} if restored else {name: artifact_id(report / "native_run_receipts" / name) for name in
            ((".phys_opt_design.end.rst", ".vivado.end.rst") if stage == "place" else (".route_design.end.rst", ".vivado.end.rst"))},
        "route": route_counts(report / "route_status_route.rpt") if stage == "route" else None,
        "drc_disposition": "no error/critical blocker; ordinary warnings retained",
        "cdc_review_status": "OPEN: reset CDC and CE-controlled memory classifications retained",
        "reports": {name: file_id(report / name) for name in required},
        "actual_xdc_reads": loaded_constraints(report / "implementation_run.log", report / "actual_xdc_reads.json",
            {"recovery":file_id(report / "recovery_parent.json")} if restored and stage == "place" else parent),
        "parent": parent,
    }
    (report / "diagnostic_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


if __name__ == "__main__":
    import sys
    require(len(sys.argv) == 4, "expected ACTION PHASE REPORT")
    if sys.argv[1] == "hook-batch":
        hook_batch(sys.argv[2], Path(sys.argv[3]).resolve())
    elif sys.argv[1] == "constraints":
        constraint_chain(sys.argv[2], Path(sys.argv[3]).resolve())
    elif sys.argv[1] == "prior-hooks":
        prior_hooks(Path(sys.argv[3]).resolve())
    elif sys.argv[1] == "claim-hooks":
        import os
        project = Path(os.environ["HAP_PROJECT_DIR"])
        report = Path(sys.argv[3]).resolve()
        (project / "m002_physical_hook_owner.json").write_text(json.dumps({
            "project": str(project), "report": str(report),
            "stage_inputs": file_id(report / "stage_inputs.sha256"),
            "archive": file_id(report / "archived_sources.sha256")}, indent=2) + "\n")
    else:
        raise ValueError("unknown action")
