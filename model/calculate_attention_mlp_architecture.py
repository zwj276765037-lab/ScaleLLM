#!/usr/bin/env python3
"""Emit the frozen V5 first-signoff capacity/cycle model as JSON evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mlp_fixed import architecture_summary, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=Path("data/attention_mlp_architecture.json"))
    args = parser.parse_args()
    summary = architecture_summary()
    write_json(args.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
