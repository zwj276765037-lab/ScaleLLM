#!/usr/bin/env python3
"""Record a qualified synth-only debug placeholder without changing failed runs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from select_candidate import count_recovery_primitives, parse_recovery_hierarchy, row, number

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"dsp_raw_only": 192, "dsp_all": 384}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def properties(path):
    rows = path.read_text(errors="replace").splitlines()
    if not rows or rows[0] != "property\tvalue":
        raise ValueError("Missing dbg_hub property table")
    return dict(line.split("\t", 1) for line in rows[1:] if "\t" in line)


def accept(name):
    work = ROOT / "runs" / name
    original = work / "synth"
    probe = work / "synth_qualified"
    original_result = json.loads((original / "result.json").read_text())
    probe_path = probe / "result.json"
    probe_result = json.loads(probe_path.read_text())
    if (original_result["returncode"] != 1 or original_result["stop_reason"] is not None or
            original_result["changed_inputs"] or original_result["native_pass_marker"] or
            probe_result["returncode"] != 0 or probe_result["stop_reason"] is not None or
            not probe_result["native_pass_marker"] or
            probe_result["original_synth_result_sha256"] != sha(original / "result.json") or
            probe_result["source_checkpoint_sha256"] != sha(original / "reports/synthesized.dcp")):
        raise ValueError("Original failure and fresh checkpoint probe identities do not match")
    if sha(probe / "stage_inputs.json") != probe_result["stage_inputs_sha256"]:
        raise ValueError("Checkpoint probe input identity changed")
    probe_log = probe / "vivado.log"
    console_log = probe / "console.log"
    if (probe_result.get("vivado_log_sha256") != sha(probe_log) or
            probe_result.get("console_sha256") != sha(console_log)):
        raise ValueError("Checkpoint probe logs changed")
    diagnostics = probe_log.read_text(errors="replace").splitlines()
    errors = Counter(line for line in diagnostics if line.startswith("ERROR:"))
    expected_errors = Counter({
        "ERROR: [Vivado 12-4444] Invalid property name REF_NAME. Use the 'list_property' command to find properties supported by the debug_core object": 3,
        "ERROR: [Vivado 12-4444] Invalid property name IPDEF. Use the 'list_property' command to find properties supported by the debug_core object": 3})
    warnings = [line for line in diagnostics if line.startswith("WARNING:")]
    if (errors != expected_errors or len(warnings) != 13 or
            any(line.startswith("FATAL:") for line in diagnostics) or
            any(not (line.startswith("WARNING: [Vivado 12-8382]") or
                     line.startswith("WARNING: [Common 17-69]")) for line in warnings)):
        raise ValueError("Checkpoint probe has unclassified Vivado diagnostics")
    for relative, digest in probe_result["reports"].items():
        if sha(probe / relative) != digest:
            raise ValueError("Checkpoint probe report changed: " + relative)
    bb = (probe / "reports/blackboxes.tsv").read_text().splitlines()
    if bb != ["name\tref_name", "dbg_hub\tdbg_hub_CV"]:
        raise ValueError("Fresh checkpoint has a blackbox other than the exact debug placeholder")
    cores = (probe / "reports/debug_cores.tsv").read_text().splitlines()
    if not cores or cores[0] != "name\tref_name\tipdef" or not any(
            line.split("\t", 1)[0] == "dbg_hub" for line in cores[1:]):
        raise ValueError("Vivado did not identify dbg_hub as a debug core")
    props = properties(probe / "reports/dbg_hub_properties.tsv")
    if (props.get("NAME") != "dbg_hub" or props.get("REF_NAME") != "dbg_hub_CV" or
            props.get("IS_BLACKBOX", "").lower() not in ("1", "true") or
            props.get("IS_PRIMITIVE", "").lower() not in ("0", "false") or
            any("dbg_hub,labtools_xsdbm_v3_00_a," not in props.get(key, "") or
                "component_name=dbg_hub_CV" not in props.get(key, "")
                for key in ("CORE_GENERATION_INFO", "DEBUG_CORE_INFO"))):
        raise ValueError("Current debug placeholder cell properties differ")

    source_reports = original / "reports"
    mapping_path = source_reports / "recovery_mapping.tsv"
    inventory_path = source_reports / "dsp_inventory.tsv"
    mapping = mapping_path.read_text(errors="replace")
    inventory = inventory_path.read_text(errors="replace")
    counts, inventory_total, legacy_total = count_recovery_primitives(mapping, inventory)
    leaves = parse_recovery_hierarchy((source_reports / "utilization_hierarchical.rpt").read_text(errors="replace"))
    whole_board_dsp = number(row((source_reports / "utilization.rpt").read_text(errors="replace"), "DSPs")[0])
    if (len(counts) != 96 or any(value != EXPECTED[name] // 96 for value in counts.values()) or
            len(leaves) != 96 or any(leaf["dsp"] != EXPECTED[name] // 96 for leaf in leaves) or
            inventory_total != whole_board_dsp or sum(counts.values()) != EXPECTED[name] or legacy_total != 0):
        raise ValueError("Recovery DSP counts are inconsistent with the original native reports")
    old_rows = [line.split("\t") for line in mapping.splitlines()[1:] if line.strip()]
    corrected = work / "synth_acceptance_recovery_mapping.tsv"
    if corrected.exists():
        raise FileExistsError("Preserved corrected mapping already exists: " + str(corrected))
    with corrected.open("w") as stream:
        stream.write("name\tref_name\torig_ref_name\tdsp_descendants\n")
        for fields in old_rows:
            stream.write("\t".join(fields[:3] + [str(counts[fields[0]])]) + "\n")

    acceptance = dict(schema="scalellm_dsp_synth_acceptance_v1", candidate=name, status="PASS",
        classification="OPEN_DEBUG_PLACEHOLDER", placeholder=dict(name="dbg_hub", ref_name="dbg_hub_CV",
        is_blackbox=True, is_primitive=False, vivado_debug_core=True),
        original_synth_status="FAIL_RETAINED", original_synth_result=str(original / "result.json"),
        original_synth_result_sha256=sha(original / "result.json"),
        original_stage_inputs_sha256=original_result["stage_inputs_sha256"],
        checkpoint=str(source_reports / "synthesized.dcp"), checkpoint_sha256=sha(source_reports / "synthesized.dcp"),
        fresh_probe_result=str(probe_path), fresh_probe_result_sha256=sha(probe_path),
        fresh_probe_vivado_log_sha256=sha(probe_log),
        probe_diagnostics=dict(caught_optional_debug_core_property_errors=dict(errors),
                               exploratory_cell_property_warnings=len(warnings),
                               interpretation="Optional debug_core REF_NAME/IPDEF queries were caught; required cell identity and get_debug_cores queries succeeded"),
        fresh_blackboxes_sha256=sha(probe / "reports/blackboxes.tsv"),
        fresh_debug_cores_sha256=sha(probe / "reports/debug_cores.tsv"),
        fresh_dbg_hub_properties_sha256=sha(probe / "reports/dbg_hub_properties.tsv"),
        recovery_leaf_count=96, recovery_dsp_count=EXPECTED[name], whole_board_dsp_count=inventory_total,
        original_mapping_export_dsp=legacy_total, corrected_mapping=str(corrected),
        corrected_mapping_sha256=sha(corrected), physical_blackbox_requirement="ZERO_AFTER_OPT_AND_LATER",
        acceptance_script_sha256=sha(Path(__file__)))
    target = work / "synth_acceptance.json"
    if target.exists():
        raise FileExistsError("Preserved synthesis acceptance already exists: " + str(target))
    target.write_text(json.dumps(acceptance, indent=2) + "\n")
    print(json.dumps(acceptance, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", choices=tuple(EXPECTED))
    accept(parser.parse_args().candidate)
