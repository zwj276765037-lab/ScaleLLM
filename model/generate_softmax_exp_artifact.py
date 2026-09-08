#!/usr/bin/env python3
"""Generate and exhaustively audit the FixBit v2 Softmax exp ROM."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from fixbit_v2 import (
    FORMAT_ID,
    build_softmax_exp_lut_u17,
    softmax_exp_delta_q14_u17,
    self_test,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "softmax_exp_u17"


def main() -> None:
    self_test()
    lut = build_softmax_exp_lut_u17()
    if lut[0] != 65536 or any(a < b for a, b in zip(lut, lut[1:])):
        raise AssertionError("Softmax exp LUT endpoint/monotonicity failure")
    rom_text = "".join(f"{value:05x}\n" for value in lut)
    rom_sha256 = hashlib.sha256(rom_text.encode("ascii")).hexdigest()

    maximum_absolute_error = 0.0
    maximum_relative_error = 0.0
    previous = 65537
    monotonic = True
    maximum_integer_error_lsb = 0
    for magnitude_q14 in range((16 << 14) + 1):
        approximation = softmax_exp_delta_q14_u17(-magnitude_q14, lut)
        exact_real = math.exp(-magnitude_q14 / float(1 << 14))
        exact_q16 = int(math.floor(exact_real * 65536.0 + 0.5))
        maximum_integer_error_lsb = max(
            maximum_integer_error_lsb, abs(approximation - exact_q16))
        approximation_real = approximation / 65536.0
        absolute_error = abs(approximation_real - exact_real)
        relative_error = absolute_error / exact_real
        maximum_absolute_error = max(maximum_absolute_error, absolute_error)
        maximum_relative_error = max(maximum_relative_error, relative_error)
        monotonic = monotonic and approximation <= previous
        previous = approximation

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "exp_lut_u17.mem").write_text(rom_text, encoding="ascii")
    expected_text = "".join(
        f"{softmax_exp_delta_q14_u17(-magnitude, lut):05x}\n"
        for magnitude in range((16 << 14) + 1)
    )
    (OUT_DIR / "expected_u17.mem").write_text(
        expected_text, encoding="ascii")
    manifest = {
        "schema": "hap_fixbit_v2_softmax_exp_u17_artifact_v1",
        "format_id": f"0x{FORMAT_ID:08x}",
        "input_format": "S19 Q5.14 delta clipped to [-16,0]",
        "output_format": "U17 U1.16",
        "address_rule": "index=(-delta_q14)>>10; fraction=(-delta_q14)&1023",
        "node_spacing": "1/16",
        "node_count": 257,
        "interpolation": "round(((lut[index]-lut[index+1])*fraction)/1024)",
        "rom_sha256": rom_sha256,
        "maximum_absolute_error": maximum_absolute_error,
        "maximum_relative_error": maximum_relative_error,
        "maximum_integer_error_lsb": maximum_integer_error_lsb,
        "monotonic_exhaustive": monotonic,
        "exp_zero_exact": lut[0] == 65536,
        "exhaustive_input_count": (16 << 14) + 1,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SOFTMAX_EXP_ARTIFACT_JSON:", json.dumps(manifest, sort_keys=True))
    if not monotonic or lut[0] != 65536:
        raise SystemExit("FAIL: Softmax exp artifact audit failed")
    print("PASS: Softmax exp artifact generated and exhaustively audited.")


if __name__ == "__main__":
    main()
