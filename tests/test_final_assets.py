"""Final runtime CPU/mock regression; no FPGA or licensed model files."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "project/hardware"))

import unittest

from host.scalellm_decode16 import DecodeRow
from host.scalellm_final_assets import build_row_rope
from model.export_scalellm_llama31_artifacts import build_rope


CONFIG = {"rope_theta": 500000.0, "rope_scaling": {
    "rope_type": "llama3", "factor": 8.0, "low_freq_factor": 1.0,
    "high_freq_factor": 4.0, "original_max_position_embeddings": 8192}}


class FinalRopeTests(unittest.TestCase):
    def test_matches_existing_contiguous_generator(self):
        for start in (0, 16, 112):
            rows = tuple(DecodeRow(True, i + 1, start + i) for i in range(16))
            self.assertEqual(build_row_rope(CONFIG, rows), build_rope(CONFIG, start))

    def test_independent_positions_127_and_inactive_zero(self):
        positions = (127, 0, 63, 1, 126, 4, 17, 92, 8, 77, 23, 44, 31, 65, 100, 12)
        rows = tuple(DecodeRow(True, 10 + i, position) if i % 3 else DecodeRow()
                     for i, position in enumerate(positions))
        payload = build_row_rope(CONFIG, rows)
        for slot, row in enumerate(rows):
            expected = build_rope(CONFIG, row.position)[:512] if row.active else bytes(512)
            self.assertEqual(payload[slot * 512:(slot + 1) * 512], expected)
        # Active maximum position independently checks the encoded 36-bit words.
        rows = tuple(DecodeRow(True, i + 1, 127) for i in range(16))
        payload = build_row_rope(CONFIG, rows)
        for offset in range(0, 8192, 8):
            self.assertEqual(int.from_bytes(payload[offset:offset + 8], "little") >> 36, 0)


if __name__ == "__main__": unittest.main()
