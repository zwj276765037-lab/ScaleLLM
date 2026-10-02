#!/usr/bin/env python3
"""Verify the immutable M12 vector set before every long simulation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import generate_vectors


DATA = Path(__file__).resolve().parent.parent / "data"
MANIFEST = DATA / "manifest.json"


def main() -> None:
    semantic_cases = generate_vectors.verify_fp16_mul_ip_boundary()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema") != "scalellm_m12_down_a8w4_full_v1":
        raise SystemExit("unexpected M12 vector schema")
    if (manifest.get("groups"), manifest.get("tiles"),
            manifest.get("transactions")) != (448, 342, 153216):
        raise SystemExit("unexpected M12 workload shape")
    generator = Path(manifest["generator"]).resolve(strict=True)
    expected_generator = Path(generate_vectors.__file__).resolve()
    if generator != expected_generator:
        raise SystemExit("M12 synthetic generator path changed")
    if hashlib.sha256(generator.read_bytes()).hexdigest() != manifest[
            "generator_sha256"]:
        raise SystemExit("M12 synthetic generator hash changed")
    for name, expected in manifest["sha256"].items():
        actual = hashlib.sha256((DATA / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(
                f"M12 vector hash mismatch for {name}: {actual} != {expected}")
    print(
        f"M12_VECTOR_VERIFY_PASS files={len(manifest['sha256'])} "
        f"fp16_boundary_cases={semantic_cases}")


if __name__ == "__main__":
    main()
