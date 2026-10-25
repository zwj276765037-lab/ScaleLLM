#!/usr/bin/env python3
"""Independent Python-integer lane vectors; no RTL or oracle imports."""
import hashlib
import json
from pathlib import Path


def main():
    out = Path(__file__).resolve().parents[1]/'data/mlp_gu_lane'
    out.mkdir(exist_ok=True)
    stimuli, gold = [], []
    shift_cases = [20, 23, 24, 44, 19, 45, 126, 21]
    codes = [1, 127, 128, 255, 0, 3, 17, 254]
    shift_errors = 0
    for index in range(512):
        activation = [((index*31+k*47+11) % 511)-255 for k in range(32)]
        weights = [[((index*7+k*3+c*11) % 16)-8 for k in range(32)] for c in range(2)]
        acode = codes[index % 8]
        wcodes = [codes[(index//8+c*3) % 8] for c in range(2)]
        total = shift_cases[(index//16) % 8]
        ashift = total//2
        wshifts = [total-ashift, min(63, total-ashift+(index % 3)-1)]
        # Include valid and deliberately malformed zero-code metadata.
        if acode == 0 and index % 2 == 0:
            ashift = 0
        for col in range(2):
            if wcodes[col] == 0 and index % 4 == 0:
                wshifts[col] = 0
        packed = sum((value & 511) << (9*k) for k, value in enumerate(activation))
        for col in range(2):
            packed |= sum((value & 15) << (288+128*col+4*k)
                          for k, value in enumerate(weights[col]))
        packed |= acode << 544 | ashift << 552 | wcodes[0] << 558
        packed |= wshifts[0] << 566 | wcodes[1] << 572 | wshifts[1] << 580
        guards = []
        for col in range(2):
            dot = sum(a*w for a, w in zip(activation, weights[col]))
            assert -(1 << 16) <= dot < (1 << 16)
            raw = dot*acode*wcodes[col]
            assert -(1 << 32) <= raw < (1 << 32)
            shift = ashift+wshifts[col]
            shift_errors += int(acode != 0 and wcodes[col] != 0 and not 20 <= shift <= 44)
            aligned = 0 if raw == 0 or not 20 <= shift <= 44 else (
                raw << (24-shift) if shift < 24 else raw >> (shift-24))
            assert -(1 << 36) <= aligned < (1 << 36)
            guards.append(aligned)
        stimuli.append(f'{packed:0147x}')
        gold.append(f'{((guards[1] & ((1<<37)-1)) << 37) | (guards[0] & ((1<<37)-1)):019x}')
    (out/'stimulus.mem').write_text('\n'.join(stimuli)+'\n')
    (out/'gold.mem').write_text('\n'.join(gold)+'\n')
    manifest = dict(vectors=512, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    scalar='Python arbitrary-precision sum32 and signed shifts',
                    expected_shift_format_count=shift_errors,
                    stimulus_sha256=hashlib.sha256((out/'stimulus.mem').read_bytes()).hexdigest(),
                    gold_sha256=hashlib.sha256((out/'gold.mem').read_bytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
