#!/usr/bin/env python3
"""Remove XSim top-parameter text that Vivado read_saif cannot parse."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


INSTANCE_RE = re.compile(r"^(\s*)\(INSTANCE\s+(.+?)\s*$")


def decode_identifier(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_saif", type=Path)
    parser.add_argument("normalized_saif", type=Path)
    parser.add_argument("top_name")
    parser.add_argument("strip_path_file", type=Path)
    args = parser.parse_args()

    lines = args.raw_saif.read_text(encoding="utf-8").splitlines(keepends=True)
    instance_chain: list[str] = []
    first_instance = True
    in_ancestry = True
    output: list[str] = []

    for line in lines:
        match = INSTANCE_RE.match(line.rstrip("\n"))
        if in_ancestry and match:
            indent, identifier = match.groups()
            if first_instance:
                identifier = args.top_name
                newline = "\n" if line.endswith("\n") else ""
                line = f"{indent}(INSTANCE  {identifier}{newline}"
                first_instance = False
            instance_chain.append(decode_identifier(identifier))
        elif in_ancestry and re.match(r"^\s*\(NET(?:\s|$)", line):
            in_ancestry = False
        output.append(line)

    if first_instance or not instance_chain:
        raise SystemExit("no INSTANCE hierarchy found in XSim SAIF")
    args.normalized_saif.write_text("".join(output), encoding="utf-8")
    args.strip_path_file.write_text("/".join(instance_chain) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
