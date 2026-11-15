#!/usr/bin/env python3
"""Apply the recorded post-physopt board selection rule to native reports."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("dsp_raw_only", "dsp_all")
EXPECTED_DSP = {"dsp_raw_only": 192, "dsp_all": 384}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row(report, name):
    # Vivado marks provisional rows such as "CLB LUTs*" with a footnote.
    pattern = re.compile(r"^\|\s*" + re.escape(name) + r"\*?\s*\|(.+)$", re.M)
    matches = pattern.findall(report)
    if not matches:
        raise ValueError("Missing utilization row: " + name)
    fields = [x.strip() for x in matches[0].split("|")]
    return fields


def number(field):
    return float(field.replace(",", "").replace("<", ""))


def parse_timing(report):
    lines = report.splitlines()
    for i, line in enumerate(lines):
        if "WNS(ns)" in line and "WHS(ns)" in line and "WPWS(ns)" in line:
            for following in lines[i + 1:i + 8]:
                fields = following.split()
                if len(fields) == 12:
                    try:
                        values = [float(x) for x in fields]
                    except ValueError:
                        continue
                    return dict(wns=values[0], tns=values[1], setup_fail=int(values[2]),
                                whs=values[4], ths=values[5], hold_fail=int(values[6]),
                                wpws=values[8], tpws=values[9], pulse_fail=int(values[10]))
    raise ValueError("Cannot parse twelve-field global timing summary")


def parse_slr(report, top):
    keys = {"CLB": "clb", "CLB LUTs": "lut", "DSPs": "dsp"}
    slr = {str(i): {} for i in range(3)}
    for label, key in keys.items():
        fields = row(report, label)
        if len(fields) < 6:
            raise ValueError("Incomplete SLR row: " + label)
        available = top[key]["available"] / 3
        if int(available) != available:
            raise ValueError("Unexpected unequal SLR capacity for " + label)
        for i in range(3):
            used, pct = int(number(fields[i])), number(fields[i + 3])
            if abs(pct - 100 * used / available) > 0.03:
                raise ValueError("SLR utilization/capacity mismatch: " + label)
            slr[str(i)][key] = dict(used=used, available=int(available), percent=pct)
    return slr


def parse_top(report):
    keys = {"CLB LUTs": "lut", "CLB Registers": "registers", "Register as Flip Flop": "ff",
            "CLB": "clb", "Block RAM Tile": "bram36_equivalent", "URAM": "uram", "DSPs": "dsp"}
    out = {}
    for label, key in keys.items():
        fields = row(report, label)
        if len(fields) < 5:
            raise ValueError("Incomplete utilization row: " + label)
        out[key] = dict(used=number(fields[0]), available=number(fields[3]), percent=number(fields[4]))
    return out


def parse_recovery_hierarchy(report):
    leaves = []
    for line in report.splitlines():
        if "|" not in line:
            continue
        fields = [x.strip() for x in line.split("|")]
        if len(fields) >= 12 and fields[1] == "u_recover" and "hap_a8w4_scalecode_recover2_lut" in fields[2]:
            leaves.append(dict(module=fields[2], lut=int(fields[3]), ff=int(fields[7]), dsp=int(fields[11])))
    return leaves


def count_recovery_primitives(mapping_report, inventory_report):
    mapping_rows = [line.split("\t") for line in mapping_report.splitlines()[1:] if line.strip()]
    if len(mapping_rows) != 96 or any(len(fields) != 4 or not fields[3].isdigit() for fields in mapping_rows):
        raise ValueError("Recovery mapping export has missing or malformed rows")
    names = [fields[0] for fields in mapping_rows]
    if len(set(names)) != 96:
        raise ValueError("Recovery mapping export has duplicate leaf paths")
    inventory_rows = [line.split("\t") for line in inventory_report.splitlines()[1:] if line.strip()]
    if any(len(fields) != 5 or fields[1] != "DSP48E2" for fields in inventory_rows):
        raise ValueError("DSP primitive inventory has malformed rows")
    counts = {name: 0 for name in names}
    for fields in inventory_rows:
        primitive = fields[0]
        for name in names:
            # Literal prefix matching is required: generate names contain [0], [1], etc.
            if primitive.startswith(name + "/"):
                counts[name] += 1
                break
    return counts, len(inventory_rows), sum(int(fields[3]) for fields in mapping_rows)


def synth_acceptance(work):
    receipt = work / "synth/result.json"
    if not receipt.is_file():
        return False, "missing synthesis result"
    native = json.loads(receipt.read_text())
    if native.get("returncode") == 0 and native.get("stop_reason") is None and native.get("native_pass_marker"):
        return True, "native synthesis gate passed"
    path = work / "synth_acceptance.json"
    if not path.is_file():
        return False, "failed native synthesis has no qualified follow-up receipt"
    qualified = json.loads(path.read_text())
    probe = work / "synth_qualified/result.json"
    dcp = work / "synth/reports/synthesized.dcp"
    mapping = work / "synth_acceptance_recovery_mapping.tsv"
    if any(not file.is_file() for file in (probe, dcp, mapping)):
        return False, "qualified synthesis evidence is incomplete"
    if (native.get("returncode") != 1 or native.get("stop_reason") is not None or native.get("changed_inputs") or
            qualified.get("status") != "PASS" or qualified.get("candidate") != work.name or
            qualified.get("classification") != "OPEN_DEBUG_PLACEHOLDER" or
            qualified.get("physical_blackbox_requirement") != "ZERO_AFTER_OPT_AND_LATER" or
            qualified.get("original_synth_result_sha256") != sha(receipt) or
            qualified.get("fresh_probe_result_sha256") != sha(probe) or
            qualified.get("checkpoint_sha256") != sha(dcp) or
            qualified.get("corrected_mapping_sha256") != sha(mapping)):
        return False, "qualified synthesis identity differs"
    return True, "synthesis DCP qualified with exact debug placeholder"


def read_candidate(name, root=ROOT):
    work = root / "runs" / name
    place = work / "place"
    synth = work / "synth"
    reasons = []
    synth_ok, synth_status = synth_acceptance(work)
    if not synth_ok:
        reasons.append(synth_status)
    place_result_path = place / "result.json"
    if not place_result_path.is_file():
        reasons.append("missing " + str(place_result_path))
    else:
        place_result = json.loads(place_result_path.read_text())
        if place_result.get("returncode") != 0 or place_result.get("stop_reason") is not None or not place_result.get("native_pass_marker"):
            reasons.append("native stage failed: " + str(place_result_path))
    paths = {"utilization": place / "reports/utilization.rpt",
             "slr": place / "reports/utilization_slr.rpt",
             "timing": place / "reports/timing_summary.rpt",
             "hierarchy": place / "reports/utilization_hierarchical.rpt",
             "blackboxes": place / "reports/blackboxes.txt",
             "dsp_inventory": place / "reports/dsp_inventory.tsv",
             "recovery_mapping": place / "reports/recovery_mapping.tsv",
             "post_opt_blackboxes": place / "reports/blackboxes_post_opt.tsv",
             "post_opt_checkpoint": place / "reports/opt_design.dcp"}
    if reasons:
        return dict(candidate=name, feasible=False, reasons=reasons)
    for key, path in paths.items():
        if not path.is_file():
            reasons.append("missing report: " + key)
    if reasons:
        return dict(candidate=name, feasible=False, reasons=reasons)
    try:
        top = parse_top(paths["utilization"].read_text(errors="replace"))
        slr = parse_slr(paths["slr"].read_text(errors="replace"), top)
        timing = parse_timing(paths["timing"].read_text(errors="replace"))
        leaves = parse_recovery_hierarchy(paths["hierarchy"].read_text(errors="replace"))
        primitive_counts, inventory_total, legacy_mapping_dsp = count_recovery_primitives(
            paths["recovery_mapping"].read_text(errors="replace"),
            paths["dsp_inventory"].read_text(errors="replace"))
    except (ValueError, IndexError) as exc:
        return dict(candidate=name, feasible=False, reasons=[str(exc)], reports={k: str(v) for k,v in paths.items()})
    if paths["blackboxes"].read_text().strip():
        reasons.append("unresolved blackbox")
    if paths["post_opt_blackboxes"].read_text().splitlines() != ["name\tref_name"]:
        reasons.append("post-opt design contains blackboxes or lacks zero-blackbox evidence")
    if not paths["post_opt_checkpoint"].stat().st_size:
        reasons.append("empty post-opt checkpoint")
    for key in ("post_opt_blackboxes", "post_opt_checkpoint"):
        relative = "reports/" + paths[key].name
        if place_result.get("reports", {}).get(relative) != sha(paths[key]):
            reasons.append("post-opt evidence hash differs from native place receipt: " + key)
    if len(leaves) != 96:
        reasons.append("recovery hierarchy count is %d, expected 96" % len(leaves))
    mapped_dsp = sum(x["dsp"] for x in leaves)
    if mapped_dsp != EXPECTED_DSP[name]:
        reasons.append("recovery hierarchy DSP count is %d, expected %d" % (mapped_dsp, EXPECTED_DSP[name]))
    mapping_dsp = sum(primitive_counts.values())
    if len(primitive_counts) != 96 or any(count != EXPECTED_DSP[name] // 96 for count in primitive_counts.values()):
        reasons.append("recovery primitive inventory is not evenly mapped across all 96 leaves")
    if mapping_dsp != mapped_dsp:
        reasons.append("recovery primitive inventory disagrees with hierarchical utilization")
    if inventory_total != top["dsp"]["used"]:
        reasons.append("whole-board DSP inventory disagrees with utilization")
    if legacy_mapping_dsp not in (0, mapping_dsp):
        reasons.append("recovery mapping export disagrees with primitive inventory")
    for key in ("clb", "dsp"):
        if top[key]["used"] > top[key]["available"]:
            reasons.append("whole-board " + key + " exceeds capacity")
        for index, value in slr.items():
            if value[key]["used"] > value[key]["available"]:
                reasons.append("SLR" + index + " " + key + " exceeds capacity")
    setup = timing["wns"] >= 0 and timing["tns"] == 0 and timing["setup_fail"] == 0
    hold = timing["whs"] >= 0 and timing["ths"] == 0 and timing["hold_fail"] == 0
    return dict(candidate=name, feasible=not reasons, reasons=reasons, synth_status=synth_status,
                top=top, slr=slr, timing=timing,
                setup_pass=setup, hold_pass=hold, recovery_leaf_count=len(leaves),
                recovery_dsp=mapped_dsp, recovery_query_count=len(primitive_counts), recovery_primitive_dsp=mapping_dsp,
                recovery_legacy_export_dsp=legacy_mapping_dsp,
                maximum_slr_clb_percent=max(x["clb"]["percent"] for x in slr.values()),
                maximum_slr_dsp_percent=max(x["dsp"]["percent"] for x in slr.values()),
                reports={k: {"path":str(v),"sha256":sha(v)} for k,v in paths.items()})


def choose(raw, all_dsp):
    viable = [x for x in (raw, all_dsp) if x["feasible"]]
    if not viable:
        raise ValueError("Neither candidate has a valid physical placement")
    if len(viable) == 1:
        return viable[0]["candidate"], "only feasible candidate"
    if raw["setup_pass"] != all_dsp["setup_pass"]:
        return (raw if raw["setup_pass"] else all_dsp)["candidate"], "setup closure priority"
    if raw["hold_pass"] != all_dsp["hold_pass"]:
        return (raw if raw["hold_pass"] else all_dsp)["candidate"], "hold closure priority"
    if raw["setup_pass"] and raw["hold_pass"]:
        return "dsp_raw_only", "both closed at place; preserve DSP margin"
    def rank(x):
        t = x["timing"]
        return (-t["wns"], t["setup_fail"], abs(t["tns"]), -t["whs"], t["hold_fail"],
                x["maximum_slr_clb_percent"], x["maximum_slr_dsp_percent"], x["top"]["lut"]["used"],
                0 if x["candidate"] == "dsp_raw_only" else 1)
    winner = min(viable, key=rank)
    return winner["candidate"], "unclosed-placement lexicographic priority"


def select(root=ROOT):
    raw, all_dsp = (read_candidate(n, root) for n in NAMES)
    winner, reason = choose(raw, all_dsp)
    record = dict(schema="scalellm_dsp_board_selection_v1", candidate=winner, reason=reason,
                  selector_sha256=sha(Path(__file__)),
                  candidates={raw["candidate"]:raw, all_dsp["candidate"]:all_dsp})
    path = root / "runs/selection.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    print(json.dumps(select(), indent=2))
