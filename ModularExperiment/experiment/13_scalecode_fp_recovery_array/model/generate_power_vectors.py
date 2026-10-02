#!/usr/bin/env python3
"""Generate trace-range-calibrated input activity for M13 power runs."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

import numpy as np

from generate_vectors import fp16_bits, fp16_ftz, fp32_bits, pack, write_word


HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "data_power"
LANES = 96
VECTORS = 4096
SEED = 0x13A8C0DE


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = [
        "dot0_s17x96.mem", "dot1_s17x96.mem",
        "activation_meta_sc_u1344.mem", "weight0_meta_sc_u1344.mem",
        "weight1_meta_sc_u1344.mem",
        "activation_scale_fp16x96.mem", "weight0_scale_fp16x96.mem",
        "weight1_scale_fp16x96.mem",
        "activation_scale_fp32x96.mem", "weight0_scale_fp32x96.mem",
        "weight1_scale_fp32x96.mem",
    ]
    handles = {name: (OUT / name).open("w", encoding="ascii") for name in names}
    rng = random.Random(SEED)
    shift_min = 127
    shift_max = 0
    dot_min = 0
    dot_max = 0

    try:
        for cycle in range(VECTORS):
            dots0: list[int] = []
            dots1: list[int] = []
            acodes: list[int] = []
            ashifts: list[int] = []
            w0codes: list[int] = []
            w0shifts: list[int] = []
            w1codes: list[int] = []
            w1shifts: list[int] = []
            a16bits: list[int] = []
            w016bits: list[int] = []
            w116bits: list[int] = []
            a32bits: list[int] = []
            w032bits: list[int] = []
            w132bits: list[int] = []

            for lane in range(LANES):
                # M09 real Gate/Up trace correlations were [-7384, 6959].
                # Use a symmetric nearby envelope and avoid an artificially
                # idle all-zero workload.
                dot0 = rng.randrange(-8000, 8001)
                dot1 = rng.randrange(-8000, 8001)
                if dot0 == 0:
                    dot0 = 1 if lane & 1 else -1
                if dot1 == 0:
                    dot1 = -1 if lane & 1 else 1
                acode = rng.randrange(96, 256)
                w0code = rng.randrange(96, 256)
                w1code = rng.randrange(96, 256)
                ashift = rng.randrange(13, 19)
                legal_weights = [shift for shift in range(13, 21)
                                 if 26 <= ashift + shift <= 37]
                w0shift = rng.choice(legal_weights)
                w1shift = rng.choice(legal_weights)
                shift_min = min(shift_min, ashift+w0shift, ashift+w1shift)
                shift_max = max(shift_max, ashift+w0shift, ashift+w1shift)
                dot_min = min(dot_min, dot0, dot1)
                dot_max = max(dot_max, dot0, dot1)

                ascale = acode / float(1 << ashift)
                w0scale = w0code / float(1 << w0shift)
                w1scale = w1code / float(1 << w1shift)
                dots0.append(dot0)
                dots1.append(dot1)
                acodes.append(acode)
                ashifts.append(ashift)
                w0codes.append(w0code)
                w0shifts.append(w0shift)
                w1codes.append(w1code)
                w1shifts.append(w1shift)
                a16bits.append(fp16_bits(fp16_ftz(ascale)))
                w016bits.append(fp16_bits(fp16_ftz(w0scale)))
                w116bits.append(fp16_bits(fp16_ftz(w1scale)))
                a32bits.append(fp32_bits(np.float32(ascale)))
                w032bits.append(fp32_bits(np.float32(w0scale)))
                w132bits.append(fp32_bits(np.float32(w1scale)))

            write_word(handles["dot0_s17x96.mem"], pack(dots0, 17), LANES*17)
            write_word(handles["dot1_s17x96.mem"], pack(dots1, 17), LANES*17)
            write_word(handles["activation_meta_sc_u1344.mem"],
                       pack(acodes, 8) | (pack(ashifts, 6) << (LANES*8)),
                       LANES*14)
            write_word(handles["weight0_meta_sc_u1344.mem"],
                       pack(w0codes, 8) | (pack(w0shifts, 6) << (LANES*8)),
                       LANES*14)
            write_word(handles["weight1_meta_sc_u1344.mem"],
                       pack(w1codes, 8) | (pack(w1shifts, 6) << (LANES*8)),
                       LANES*14)
            for stem, bits16, bits32 in [
                ("activation_scale", a16bits, a32bits),
                ("weight0_scale", w016bits, w032bits),
                ("weight1_scale", w116bits, w132bits),
            ]:
                write_word(handles[f"{stem}_fp16x96.mem"],
                           pack(bits16, 16), LANES*16)
                write_word(handles[f"{stem}_fp32x96.mem"],
                           pack(bits32, 32), LANES*32)
    finally:
        for handle in handles.values():
            handle.close()

    hashes = {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest()
              for name in names}
    manifest = {
        "schema_version": 1,
        "seed": SEED,
        "vectors": VECTORS,
        "lanes": LANES,
        "replay_cycles": 65536,
        "replay_count": 16,
        "accepted_contributions": 65536 * LANES * 2,
        "dot_range": [dot_min, dot_max],
        "total_shift_range": [shift_min, shift_max],
        "range_anchor": "M09 real Gate/Up trace correlation/shift envelope",
        "sha256": hashes,
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("M13_POWER_VECTOR_GENERATION_PASS "
          f"vectors={VECTORS} replay_cycles=65536 lanes={LANES} "
          f"dot=[{dot_min},{dot_max}] shift=[{shift_min},{shift_max}]")


if __name__ == "__main__":
    main()
