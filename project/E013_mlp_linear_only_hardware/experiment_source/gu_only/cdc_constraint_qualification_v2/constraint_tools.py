#!/usr/bin/env python3
"""CPU helpers for the same-routed-design constraint qualification.

These helpers do not run EDA or change the original routed checkpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import posixpath
import re
import zipfile
from pathlib import Path

FIELDS = ("wns_ns", "tns_ns", "setup_failing_endpoints", "setup_total_endpoints",
          "whs_ns", "ths_ns", "hold_failing_endpoints", "hold_total_endpoints",
          "wpws_ns", "tpws_ns", "pulse_failing_endpoints", "pulse_total_endpoints")
USER_GROUP = ("set_clock_groups -asynchronous "
              "-group [get_clocks -include_generated_clocks -of_objects [get_ports pcie_refclk_p]] "
              "-group [get_clocks -include_generated_clocks -of_objects [get_ports default_250mhz_clk1_clk_p]] "
              "-group [get_clocks -include_generated_clocks -of_objects [get_ports default_250mhz_clk2_clk_p]]")
PHYSICAL_SUFFIXES = (".edf", ".nnlns", ".devns", ".rdb", ".pdb", ".shape")
CAPTURE_PREDICATE = '((DIRECTION == IN && (IS_CLOCK == 0 || REF_PIN_NAME =~ CE*)) || DIRECTION == INOUT)'


def full_capture_predicate(extras: list[str]) -> str:
    if not extras:
        return CAPTURE_PREDICATE
    terms = " || ".join('NAME == "' + pin + '"' for pin in extras)
    return '(' + CAPTURE_PREDICATE + ' || (IS_CLOCK == 1 && (' + terms + ')))'


def exclusion_predicate(pins: list[str]) -> str:
    exact = " && ".join('NAME != "' + pin + '"' for pin in pins)
    common = posixpath.commonpath(pins)
    # Most of the millions of primitive pins lie outside these two small
    # frontend scopes. This guard preserves the exact NAME exclusions while
    # avoiding every long-name comparison on every unrelated primitive pin.
    if common and not any(c in common for c in '[]\\*?"'):
        if not all(pin.startswith(common + "/") for pin in pins):
            raise ValueError("invalid common scope optimization")
        return '(NAME !~ "' + common + '/*" || (' + exact + '))'
    return '(' + exact + ')'


def tcl_list(values: list[str]) -> str:
    """Quote known native object names without evaluating Tcl metacharacters."""
    if not values or any(not value or any(c in value for c in "{}\\\n\r") for value in values):
        raise ValueError("empty or unsupported native object name")
    return "{" + " ".join("{" + value + "}" for value in values) + "}"


def replacement(identity: dict) -> str:
    """Build only the user clock isolation replacement, never vendor exceptions.

    Clock direction remains part of every exception, including for multi-clock
    RAM/DSP cells. The through superset includes every nonclock primitive input,
    so capture CE/reset/gating inputs cannot be omitted by a register taxonomy.
    The native qualification separately proves that every exposed target is a
    direct launch-FF Q to capture-FF D connection.
    """
    clocks = identity["clock_groups"]
    if set(clocks) != {"pcie", "ddr0", "ddr1"}:
        raise ValueError("expected the original three domain sets")
    clock_sets = [set(clocks[key]) for key in ("pcie", "ddr0", "ddr1")]
    if any(not values for values in clock_sets) or any(clock_sets[i] & clock_sets[j] for i in range(3) for j in range(i)):
        raise ValueError("clock sets must be nonempty and disjoint")
    targets = identity["target_D"]
    if set(targets) != {"ddr0", "ddr1"} or len(targets["ddr0"]) != 68 or len(targets["ddr1"]) != 70:
        raise ValueError("expected 68 Attention and 70 GU dynamic D endpoints")
    all_targets = targets["ddr0"] + targets["ddr1"]
    if len(set(all_targets)) != 138 or any(not pin.endswith("/D") for pin in all_targets):
        raise ValueError("target set is not exactly 138 distinct D pins")
    for pin in all_targets:
        tcl_list([pin])
        if '"' in pin:
            raise ValueError("unsupported quote in pin name")
    native = {}
    for key in clocks:
        tcl_list(clocks[key])
        if any('"' in name for name in clocks[key]):
            raise ValueError("unsupported quote in native clock name")
        condition = " || ".join('NAME == "' + name + '"' for name in clocks[key])
        native[key] = "[get_clocks -quiet -filter {" + condition + "}]"
    output_drivers = ("[get_pins -quiet -leaf -of_objects [get_nets -quiet -segments -of_objects "
                      "[get_ports -quiet -filter {DIRECTION == OUT || DIRECTION == INOUT}]] "
                      "-filter {DIRECTION == OUT || DIRECTION == INOUT}]")
    lines = ["# Section 12: replace only the original user three-domain isolation.",
             "set_clock_groups -asynchronous -group " + native["ddr0"] + " -group " + native["ddr1"]]
    for domain in ("ddr0", "ddr1"):
        excluded = exclusion_predicate(targets[domain])
        extras = identity.get('extra_capture_pins', {}).get(domain, [])
        for name in extras:
            tcl_list([name])
            if '"' in name:
                raise ValueError('unsupported quote in extra capture name')
        capture = ("[get_pins -quiet -of_objects [get_cells -quiet -hierarchical "
                   "-filter {IS_PRIMITIVE == 1}] -filter "
                   "{" + full_capture_predicate(extras) + " && " + excluded + "}]")
        lines += ["set_false_path -from " + native[domain] + " -to " + native["pcie"],
                  "set_false_path -from " + native["pcie"] + " -to " + native[domain] + " -through " + capture,
                  "set_false_path -from " + native["pcie"] + " -to " + native[domain] + " -through " + output_drivers]
    return "\n".join(lines) + "\n"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def metrics(path: Path) -> dict:
    lines = path.read_text().splitlines()
    for index, line in enumerate(lines):
        if "WNS(ns)" not in line or "TNS Failing Endpoints" not in line:
            continue
        for row in lines[index + 1:index + 5]:
            words = row.split()
            if len(words) != 12:
                continue
            try:
                values = [float(value) for value in words]
            except ValueError:
                continue
            result = dict(zip(FIELDS, values))
            for key in result:
                if "endpoints" in key:
                    result[key] = int(result[key])
            return result
    raise ValueError("complete native timing table not found")


def assert_timing(path: Path) -> dict:
    result = metrics(path)
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError("native aggregate timing metrics must be finite")
    for key in ("wns_ns", "whs_ns", "wpws_ns"):
        if result[key] < 0:
            raise ValueError({"negative_native_slack": key, "value": result[key]})
    for key in ("tns_ns", "ths_ns", "tpws_ns", "setup_failing_endpoints", "hold_failing_endpoints", "pulse_failing_endpoints"):
        if result[key] != 0:
            raise ValueError({"native_timing_failures": key, "value": result[key]})
    return {"scope": "ACTIVE_NATIVE_CONSTRAINTS_EXTERNAL_RESET_SIGNOFF_OPEN", "status": "PASS", "metrics": result}


def patch(original: Path, replacement: Path, candidate: Path) -> dict:
    text = original.read_text()
    matches = list(re.finditer(r"^set_clock_groups[^\n]*$", text, re.MULTILINE))
    exact = [match for match in matches
             if " ".join(match.group().split()) == USER_GROUP]
    if len(exact) != 1:
        raise ValueError(f"expected exactly one exact user three-domain group, got {len(exact)}")
    selected = exact[0]
    body = replacement.read_text()
    if not body.endswith("\n"):
        body += "\n"
    candidate.write_text(text[:selected.start()] + body.rstrip("\n") + text[selected.end():])
    return {"original_sha256": digest(original), "replacement_sha256": digest(replacement),
            "candidate_sha256": digest(candidate), "removed_exact_user_group": selected.group(),
            "original_line": text[:selected.start()].count("\n") + 1,
            "other_original_bytes_preserved": True}


def checkpoint_members(path: Path) -> dict:
    result = {}
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if not entry.filename.endswith(PHYSICAL_SUFFIXES):
                continue
            with archive.open(entry) as stream:
                value = hashlib.file_digest(stream, "sha256").hexdigest()
            result[entry.filename] = {"bytes": entry.file_size, "sha256": value}
    if {Path(name).suffix for name in result} != set(PHYSICAL_SUFFIXES):
        raise ValueError("expected EDIF/net-name/device/route/place/shape members absent")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("metrics");p.add_argument("report", type=Path)
    p = sub.add_parser("assert-timing");p.add_argument("report", type=Path)
    p = sub.add_parser("patch");p.add_argument("original", type=Path);p.add_argument("replacement", type=Path);p.add_argument("candidate", type=Path)
    p = sub.add_parser("physical");p.add_argument("checkpoint", type=Path)
    p = sub.add_parser("replacement");p.add_argument("identity", type=Path);p.add_argument("output", type=Path)
    p = sub.add_parser("augment-roles");p.add_argument("identity", type=Path);p.add_argument("classification", type=Path);p.add_argument("output", type=Path)
    p = sub.add_parser("compare-timing");p.add_argument("reference", type=Path);p.add_argument("replay", type=Path)
    p = sub.add_parser("compare-physical");p.add_argument("original", type=Path);p.add_argument("qualified", type=Path)
    args = parser.parse_args()
    if args.command == "metrics":
        result = metrics(args.report)
    elif args.command == "assert-timing":
        result = assert_timing(args.report)
    elif args.command == "patch":
        result = patch(args.original, args.replacement, args.candidate)
    elif args.command == "physical":
        result = checkpoint_members(args.checkpoint)
    elif args.command == "replacement":
        args.output.write_text(replacement(json.loads(args.identity.read_text())))
        result = {"replacement_sha256": digest(args.output), "dynamic_D_endpoints": 138}
    elif args.command == "augment-roles":
        identity = json.loads(args.identity.read_text())
        classified = json.loads(args.classification.read_text())
        if classified['status'] != 'ALL_DISCOVERED_ROLES_PROVEN' or classified['unknown_count']:
            raise ValueError('unproven capture role')
        identity['extra_capture_pins'] = classified['extra_capture_pins']
        identity['capture_role_classification_sha256'] = digest(args.classification)
        args.output.write_text(json.dumps(identity, indent=2)+'\n')
        result = {'augmented_identity_sha256': digest(args.output)}
    elif args.command == "compare-timing":
        before, after = metrics(args.reference), metrics(args.replay)
        if before != after:
            raise ValueError({"zero_replay_timing_changed": {key: [before[key], after[key]] for key in before if before[key] != after[key]}})
        result = {"status": "IDENTICAL_NATIVE_AGGREGATE_TABLE", "reference": before, "replay": after}
    else:
        before, after = checkpoint_members(args.original), checkpoint_members(args.qualified)
        if before != after:
            raise ValueError({"physical_or_netlist_member_changes": [key for key in before.keys() | after.keys() if before.get(key) != after.get(key)]})
        result = {"status": "IDENTICAL_NETLIST_AND_PHYSICAL_DATABASE_MEMBERS", "members": before}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
