#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compatibility entry for the current final Decode16 hardware builder."""
import runpy
from pathlib import Path

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent/'final/build_hardware.py'), run_name='__main__')
