import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from prepare_public_source import prepare, verify_sources
from prepare_source import apply_unified, apply_unified_texts


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PublicSourcePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        original = b"\xef\xbb\xbf/* Fixture license */\r\nint policy = 0;"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("fixture/core.c", original)
        self.archive = self.root / "source.zip"
        self.archive.write_bytes(buffer.getvalue())
        baseline = b"/* Fixture license */\nint policy = 1;\n"
        final = b"/* Fixture license */\nint policy = 2;\n"
        bridge = b"--- a/core.c\n+++ b/core.c\n@@ -1,2 +1,2 @@\n /* Fixture license */\n-int policy = 0;\n+int policy = 1;\n"
        policy = bridge.replace(b"policy = 0", b"policy = 1").replace(b"+int policy = 1", b"+int policy = 2")
        (self.root / "bridge.patch").write_bytes(bridge)
        (self.root / "policy.patch").write_bytes(policy)
        observed = json.dumps({"files": {"core.c": {"lf_sha256": sha(baseline)}}}).encode()
        (self.root / "observed.json").write_bytes(observed)
        self.manifest = self.root / "manifest.json"
        self.data = {
            "schema": "scalellm_xdma_public_source_v1",
            "source_kind": "THIRD_PARTY_PUBLIC_MIRROR",
            "repository": "fixture", "commit": "fixed",
            "official_amd_archive_identity": "UNVERIFIED",
            "archive": {"bytes": len(buffer.getvalue()), "sha256": sha(buffer.getvalue()), "prefix": "fixture/"},
            "observed_base_manifest": {"file": "observed.json", "sha256": sha(observed)},
            "patches": [{"file": "bridge.patch", "sha256": sha(bridge)},
                        {"file": "policy.patch", "sha256": sha(policy)}],
            "normalization": {"remove_utf8_bom_for": ["core.c"], "ensure_final_lf_for": ["core.c"]},
            "input_files": {"core.c": {"bytes": len(original), "sha256": sha(original)}},
            "final_files": {"core.c": {"bytes": len(final), "sha256": sha(final)}},
        }
        self.save_manifest()
        self.expected = final

    def save_manifest(self):
        self.manifest.write_text(json.dumps(self.data))

    def test_inspect_and_prepare_preserve_license_and_exact_bytes(self):
        source_before = self.archive.read_bytes()
        files, receipt = verify_sources(self.archive, self.manifest)
        self.assertEqual(files, {"core.c": self.expected})
        self.assertEqual(receipt["official_amd_archive_identity"], "UNVERIFIED")
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),
                         ["bridge.patch", "manifest.json", "observed.json", "policy.patch", "source.zip"])
        destination = self.root / "prepared"
        result = prepare(self.archive, destination, self.manifest)
        self.assertEqual((destination / "core.c").read_bytes(), self.expected)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(self.archive.read_bytes(), source_before)

    def test_modified_or_extra_archive_bytes_are_rejected_before_output(self):
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("fixture/unreviewed.c", b"extra source")
        destination = self.root / "prepared"
        with self.assertRaisesRegex(ValueError, "Archive size/SHA256"):
            prepare(self.archive, destination, self.manifest)
        self.assertFalse(destination.exists())

    def test_unexpected_source_content_is_rejected(self):
        self.data["input_files"]["core.c"]["sha256"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Public source bytes"):
            verify_sources(self.archive, self.manifest)

    def test_changed_patch_is_rejected_before_output(self):
        (self.root / "policy.patch").write_bytes(b"unknown changes")
        with self.assertRaisesRegex(ValueError, "Project patch identity"):
            prepare(self.archive, self.root / "prepared", self.manifest)
        self.assertFalse((self.root / "prepared").exists())

    def test_final_identity_mismatch_is_rejected(self):
        self.data["final_files"]["core.c"]["sha256"] = "0" * 64
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Final source differs"):
            prepare(self.archive, self.root / "prepared", self.manifest)
        self.assertFalse((self.root / "prepared").exists())

    def test_existing_output_is_preserved(self):
        destination = self.root / "prepared"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_text("existing")
        with self.assertRaises(FileExistsError):
            prepare(self.archive, destination, self.manifest)
        self.assertEqual(sentinel.read_text(), "existing")

    def test_failed_final_rename_cleans_staging(self):
        destination = self.root / "prepared"
        with mock.patch("prepare_public_source.os.rename", side_effect=OSError("simulated failure")):
            with self.assertRaisesRegex(OSError, "simulated failure"):
                prepare(self.archive, destination, self.manifest)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.root.glob(".prepared-*")), [])

    def test_legacy_patch_entry_retains_exact_context_behavior(self):
        original = {"core.c": "a\nb\n"}
        patch = "--- a/core.c\n+++ b/core.c\n@@ -1,2 +1,2 @@\n a\n-b\n+c\n"
        self.assertEqual(apply_unified_texts(original, patch), {"core.c": "a\nc\n"})
        self.assertEqual(original["core.c"], "a\nb\n")
        (self.root / "core.c").write_text(original["core.c"])
        apply_unified(self.root, patch)
        self.assertEqual((self.root / "core.c").read_text(), "a\nc\n")
        with self.assertRaisesRegex(ValueError, "Patch context mismatch"):
            apply_unified_texts({"core.c": "a\nx\n"}, patch)


if __name__ == "__main__":
    unittest.main()
