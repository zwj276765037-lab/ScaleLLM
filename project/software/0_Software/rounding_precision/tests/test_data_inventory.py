import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiment"))
from data_inventory import bounded_listing, build_inventory, npz_headers, sha256_file


def npy_header(dtype, shape):
    header = repr({"descr": dtype, "fortran_order": False, "shape": shape}).encode() + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header


class DataInventoryTests(unittest.TestCase):
    def test_header_only_inventory_never_needs_array_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trace.npz"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("groups.npy", npy_header("<f4", (32768, 32)))
                archive.writestr("labels.npy", npy_header("<U16", (32768,)))
            headers = npz_headers(path)
            self.assertEqual(headers[0]["shape"], [32768, 32])
            self.assertEqual(headers[1]["dtype"], "<U16")

    def test_malicious_or_oversized_header_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "trace.npz"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("groups.npy", b"\x93NUMPY\x02\x00" + struct.pack("<I", 1000000))
            with self.assertRaisesRegex(ValueError, "bound"):
                npz_headers(path)

    def test_listing_and_hash_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for index in range(4):
                (base / str(index)).write_bytes(b"large")
            listing = bounded_listing(base, max_files=2)
            self.assertEqual(len(listing["entries"]), 2)
            self.assertTrue(listing["truncated"])
            self.assertIsNone(sha256_file(base / "0", max_bytes=1))

    def test_float_archive_not_qualified_by_manifest_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / "legacy/0_Software/FPtoQ/results/llama3.1-8b-instruct"
            trace.mkdir(parents=True)
            (trace / "activation_groups.json").write_text(json.dumps({"total_groups": 32768}))
            with zipfile.ZipFile(trace / "activation_groups.npz", "w") as archive:
                archive.writestr("groups.npy", npy_header("<f4", (32768, 32)))
                archive.writestr("labels.npy", npy_header("<U16", (32768,)))
            result = build_inventory(root / "project", root / "legacy")
            self.assertTrue(result["replay_qualification"]["float_activation_archive_available"])
            self.assertFalse(result["replay_qualification"]["existing_same_code_linear_replay"])


if __name__ == "__main__":
    unittest.main()
