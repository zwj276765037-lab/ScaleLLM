#!/usr/bin/env python3
"""Bounded read-only RTL identity, mux-scale arithmetic, and route sample extraction.

This is source-level arithmetic, never a synthesis or timing result.  Only the
explicit files below and the already-existing E003 route log are read.
"""
from pathlib import Path
import hashlib
import json
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent
RTL = ROOT / "project/hardware/rtl/attention"
NAMES = [
    "hap_tensor24_buffers.sv", "hap_tensor24_cohort16_buffers.sv",
    "hap_attention_cohort16_local_stores.sv",
    "hap_attention_compute_cohort16_top.sv",
    "hap_projection_core16x16_w8_reuse.sv", "hap_attention_frontend_8row.sv",
    "hap_a8w8_array_16x16_s42_col3.sv", "hap_a8w8_col_shard_center12_s42.sv",
    "hap_a8w8_col_shard_s42.sv", "hap_a8w8_group32_lane_s42.sv",
    "hap_linear_tile_accum_dual_s42.sv", "hap_attention_board_cohort16_core.sv",
    "hap_kv12_quantizer4.sv", "hap_hadamard32_norm_stream.sv",
    "hap_rope_pair_s24.sv", "hap_a8w8_col_shard_left2_s42.sv",
    "hap_a8w8_col_shard_right2_s42.sv",
]
MANIFEST = ROOT / "project/hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/inputs.sha256"
BUILD = ROOT / "project/hardware/vivado/reports/m002_E003_R003_AT001_full_route/effective_build_identity.txt"
LOG = ROOT / "project/hardware/vivado/reports/m002_E003_R003_AT001_full_route/vivado.log"
PHYSOPT_EVIDENCE = ROOT / "project/hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt/diagnostic_evidence.json"

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def mux2_equiv(width, alternatives):
    return width * (alternatives - 1)

def identities():
    expected = {}
    for line in MANIFEST.read_text().splitlines():
        sha, path = line.split(None, 1)
        expected[path.strip()] = sha
    build_text = BUILD.read_text()
    rows = []
    for name in NAMES:
        path = RTL / name
        actual = digest(path)
        source_lines = path.read_text().splitlines()
        assert str(path) in expected, name
        assert actual == expected[str(path)], f"Source drift: {name}"
        assert str(path) + ":SystemVerilog:1:1" in build_text, name
        rows.append({"path": str(path.relative_to(ROOT)), "sha256": actual,
                     "fresh_synth_manifest_match": True,
                     "route_effective_build_active": True,
                     "source_lines": len(source_lines)})
    return rows

def samples():
    lines = LOG.read_text().splitlines()
    pattern = re.compile(r"^(\d+)\. \((\d+),(\d+),(\d+)\) (\S+) Hist: (\d+) Tile Name: (\S+) Node: (\S+) Overlapping Nets: (\d+)")
    starts = [(i, pattern.match(line)) for i, line in enumerate(lines)
              if pattern.match(line)]
    assert len(starts) == 10
    rows = []
    for k, (i, match) in enumerate(starts):
        stop = starts[k+1][0] if k+1 < len(starts) else next(
            j for j in range(i+1, len(lines)) if "Verification failed" in lines[j])
        net_start = next(j for j in range(i+1, stop) if lines[j] == "Nets:")
        nets = [{"log_line": j+1, "name": lines[j]} for j in range(net_start+1, stop)
                if lines[j].startswith("scalellm_")]
        assert len(nets) == 3
        assert all("/u_attention/" in x["name"] for x in nets)
        rows.append({"sample": int(match[1]), "log_line": i+1,
                     "tile": match[7], "node": match[8], "nets": nets})
    return rows

def arithmetic():
    # Generic binary-tree mux equivalents are a reproducible scale metric,
    # not LUT count. Static decoder gates / physical fanout are not estimated.
    values = {
        "input_image_bits_two_waves": 2*3072*256,
        "input_image_KiB_two_waves": 2*3072*256//8//1024,
        "input_activation_payload_register_bits_two_waves": 2*6144,
        "input_BRAM_pipeline_payload_bits_two_waves": 2*2*256,
        "candidate_input_protected_decoder_LUT6_instances_per_wave": 24,
        "candidate_input_protected_decoder_LUT6_instances_two_waves": 2*24,
        "candidate_context_protected_decoder_LUT5_instances": 16*4,
        "candidate_protected_decoder_boundary_instances_full_design": 2*24+16*4,
        "input_wave_select_mux2_equiv": mux2_equiv(6144, 2),
        "input_context_select_mux2_equiv": mux2_equiv(6144, 2),
        "frontend_snapshot_payload_bits": 6144,
        "frontend_snapshot_row_read_mux2_equiv": mux2_equiv(768, 8),
        "context_image_bits": 4*4096*96,
        "context_image_KiB": 4*4096*96//8//1024,
        "context_payload_register_bits": 384+384+6144,
        "context_write_address_bits": 12,
        "context_read_slot_bits": 4,
        "output_image_bits_two_waves": 2*3072*256,
        "output_payload_register_bits_two_waves": 2*(8*(256+128+128+256)+256),
        "output_serializer_mux2_equiv_two_waves": 2*mux2_equiv(256, 24),
        "output_wave_response_mux2_equiv": mux2_equiv(256, 2),
        "postprocess_payload_bits": 16*2*768,
        "postprocess_single_bank_candidate_payload_reduction_bits": 16*768,
        "postprocess_all_row_pair_read_mux2_equiv": 16*mux2_equiv(48,16),
        "postprocess_row_select_mux2_equiv": mux2_equiv(48,16),
        "postprocess_quant_four_row_group_mux2_equiv": mux2_equiv(4*768,4),
        "projection_weight_fifo_payload_bits": 2*(7+16*32*8+16*16),
        "projection_weight_fifo_head_mux2_equiv": mux2_equiv(7+16*32*8+16*16,2),
        "projection_group_stage_payload_bits": 1+7+8*24+8*4*32*8+8*4*8+16*32*8+16*16,
        "projection_group_activation_bits": 8*4*32*8,
        "projection_group_unique_activation_bits": 8*32*8,
        "projection_group_duplicated_activation_bits": 8*3*32*8,
        "projection_group_duplicated_zero_point_bits": 8*3*8,
        "projection_shard_activation_stage_bits": 6*8*32*8,
        "projection_shard_all_payload_stage_bits": 6*8*32*8+8*16*8+6*8*(8+6)+16*32*8+16*(8+6),
        "projection_active_lanes": 8*16,
        "projection_lane_FIFO_distributed_memory_bits": 8*16*16*42,
        "projection_lane_high_act_wgt_payload_bits": 8*16*(128+128),
        "projection_lane_product_declared_bits": 8*16*16*16,
        "projection_lane_sum2_declared_bits": 8*16*8*17,
        "projection_dual_accumulator_state_bits": 2*8*16*42,
        "projection_dual_accumulator_output_bits": 2*8*16*24,
        "projection_array_active_output_bits": 8*16*24,
        "projection_array_declared_output_bits": 16*16*24,
        "projection_array_constant_zero_output_bits": 8*16*24,
    }
    # These finite integer checks verify addressing/packing arithmetic only.
    input_covered = [b for slot in range(24) for b in range(slot*256,(slot+1)*256)]
    context_covered = [b for slot in range(16)
                       for b in range((slot>>1)*768+(slot&1)*384,
                                      (slot>>1)*768+(slot&1)*384+384)]
    context_addresses = {((wave<<11)|((slot>>1)<<8)|(group<<1)|(slot&1))
                         for wave in range(2) for slot in range(16) for group in range(128)}
    assert input_covered == list(range(6144))
    assert context_covered == list(range(6144))
    assert context_addresses == set(range(4096))
    return values

manifest_binding = json.loads(PHYSOPT_EVIDENCE.read_text())["synthesis"]["manifest"]
assert manifest_binding["path"] == str(MANIFEST)
assert manifest_binding["sha256"] == digest(MANIFEST)
assert manifest_binding["bytes"] == MANIFEST.stat().st_size
auxiliary_paths = [
    ROOT / "project/hardware/tb/hap_attention_cohort16_local_stores_tb.sv",
    ROOT / "project/hardware/source/design.md",
    ROOT / "project/hardware/source/m002_dedicated_ddr.md",
]
result = {
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "source-declared payload bits and generic mux2-equivalent arithmetic; no EDA",
    "candidate_decoder_count_scope": "Explicit local decoder boundary instances only; shared write qualification logic and removed/original decoder mapping are excluded. Whole-design net LUT delta is unknown until synthesis.",
    "synthesis_manifest": {"path": str(MANIFEST.relative_to(ROOT)), "sha256": digest(MANIFEST)},
    "successful_physopt_manifest_binding": manifest_binding,
    "route_build": {"path": str(BUILD.relative_to(ROOT)), "sha256": digest(BUILD)},
    "route_log": {"path": str(LOG.relative_to(ROOT)), "sha256": digest(LOG)},
    "sources": identities(), "arithmetic": arithmetic(), "route_samples": samples(),
    "auxiliary_read_identities": [{"path": str(p.relative_to(ROOT)), "sha256": digest(p)} for p in auxiliary_paths],
    "checks": {"all_target_source_hashes_match": True,
               "successful_physopt_binds_synthesis_manifest": True,
               "input_24_slots_cover_6144_bits_once": True,
               "context_16_slots_cover_6144_bits_once": True,
               "context_read_addresses_cover_4096_words_once": True},
}
(OUT / "rtl_evidence.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({"source_files": len(result["sources"]), "route_nodes": len(result["route_samples"]),
                  "checks": result["checks"], "arithmetic": result["arithmetic"]}, indent=2))
