#!/usr/bin/env python3
"""Create two independently hashed Decode16 DSP recovery board workspaces."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
BASE_BUILDER = REPO / "deploy/final/build_hardware.py"
BASE_MANIFEST = REPO / "deploy/final/hardware_source_manifest.json"
LEAF_REL = "project/hardware/rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv"
LEAF_SHA = "18a2bad1a3b7df345abfaf3428a8a5bec245d9580dc3b336e6153736a23a9f6a"
VIVADO = Path("/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado")
BOARD = Path("/home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0")
ATTRS = {
    "dsp_raw_only": ("no", "no", "yes", "yes"),
    "dsp_all": ("yes", "yes", "yes", "yes"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_leaf(name):
    base = REPO / LEAF_REL
    if sha(base) != LEAF_SHA:
        raise ValueError("Frozen recovery leaf identity changed")
    text = base.read_text()
    old = '(* use_dsp = "no" *)'
    if text.count(old) != 4:
        raise ValueError("Expected exactly four frozen use_dsp attributes")
    desired = ATTRS[name]
    found = re.findall(r'\(\* use_dsp = "(no|yes)" \*\)', text)
    if found != ["no"] * 4:
        raise ValueError("Frozen leaf attributes do not match expected order")
    values = iter(desired)
    text = re.sub(r'\(\* use_dsp = "no" \*\)',
                  lambda _: '(* use_dsp = "' + next(values) + '" *)', text)
    actual = re.findall(r'\(\* use_dsp = "(no|yes)" \*\)', text)
    if actual != list(desired):
        raise ValueError("Candidate DSP attributes have wrong order")
    # The only byte differences from the frozen leaf must be attribute values.
    frozen = base.read_text()
    normalized = text.replace('(* use_dsp = "yes" *)', old)
    if normalized != frozen:
        raise ValueError("Candidate differs beyond use_dsp values")
    target = ROOT / "rtl" / (name + ".sv")
    if target.exists() and target.read_text() != text:
        raise ValueError("Candidate leaf already exists with different content: " + str(target))
    target.write_text(text)
    return target


def prepare(name):
    work = ROOT / "runs" / name
    leaf = make_leaf(name)
    if work.exists():
        raise FileExistsError(work)
    if not VIVADO.is_file() or any(not (BOARD / n).is_file() for n in ("board.xml", "part0_pins.xml", "preset.xml")):
        raise FileNotFoundError("Vivado binary or official board files missing")
    prod = json.loads(BASE_MANIFEST.read_text())
    if prod["files"][LEAF_REL] != LEAF_SHA:
        raise ValueError("Production manifest leaf identity changed")
    subprocess.run([sys.executable, str(BASE_BUILDER), "prepare", "--work", str(work),
                    "--vivado", str(VIVADO), "--board-files", str(BOARD)], check=True)
    target = work / "source" / LEAF_REL
    target.write_bytes(leaf.read_bytes())
    cfg_path = work / "build.json"
    cfg = json.loads(cfg_path.read_text())
    if cfg["source_inputs"][LEAF_REL] != LEAF_SHA:
        raise ValueError("Prepared production input identity changed")
    cfg["source_inputs"][LEAF_REL] = sha(target)
    cfg["schema"] = "scalellm_dsp_recovery_candidate_build_v1"
    cfg["base_manifest_sha256"] = sha(BASE_MANIFEST)
    cfg["candidate"] = name
    cfg["candidate_leaf"] = {"relative_path": LEAF_REL, "base_sha256": LEAF_SHA,
                             "sha256": sha(target), "attribute_values": ATTRS[name]}
    cfg["candidate_driver_sha256"] = sha(ROOT / "scripts" / "run_board.py")
    cfg["candidate_tcl_sha256"] = sha(ROOT / "scripts" / "build_board.tcl")
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
    candidate_manifest = {
        "schema": "scalellm_dsp_recovery_candidate_manifest_v1",
        "candidate": name,
        "parent_release_manifest": str(BASE_MANIFEST),
        "parent_release_manifest_sha256": cfg["base_manifest_sha256"],
        "allowed_overlay": cfg["candidate_leaf"],
        "source_inputs": cfg["source_inputs"],
        "board_inputs": cfg["board_inputs"],
        "driver_sha256": cfg["candidate_driver_sha256"],
        "tcl_sha256": cfg["candidate_tcl_sha256"],
    }
    (work / "candidate_manifest.json").write_text(json.dumps(candidate_manifest, indent=2) + "\n")
    print(json.dumps({"candidate": name, "workspace": str(work), "leaf_sha256": sha(target)}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("candidate", choices=ATTRS)
    args = p.parse_args()
    prepare(args.candidate)


if __name__ == "__main__":
    main()
