"""Check release integrity and path containment without touching real artifacts."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("release_tool", Path(__file__).resolve().parents[1] / "tools/package_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.payload = b"synthetic test bitstream"
        self.digest = hashlib.sha256(self.payload).hexdigest()
        bit = self.root / "bitstream" / release.BIT_NAME
        bit.parent.mkdir()
        bit.write_bytes(self.payload)
        (self.root / "README.md").write_text("test release\n")
        self.entries = []
        for p in [bit, self.root / "README.md"]:
            self.entries.append({"path": p.relative_to(self.root).as_posix(),
                                 "bytes": p.stat().st_size, "sha256": release.sha256(p)})
        self.write_manifest()
        self.sha_patch = patch.object(release, "BIT_SHA256", self.digest)
        self.size_patch = patch.object(release, "BIT_SIZE", len(self.payload))
        self.sha_patch.start()
        self.size_patch.start()

    def tearDown(self):
        self.sha_patch.stop()
        self.size_patch.stop()
        self.tmp.cleanup()

    def write_manifest(self):
        (self.root / "RELEASE_MANIFEST.json").write_text(json.dumps({
            "project": "ScaleLLM_VCU118_GU_only", "files": self.entries}))

    def test_intact_package(self):
        self.assertEqual(release.verify(self.root)["status"], "PASS")

    def test_content_tampering(self):
        (self.root / "README.md").write_text("corrupt data\n")
        with self.assertRaisesRegex(ValueError, "verification failed"):
            release.verify(self.root)

    def test_injected_extra_file(self):
        (self.root / "unlisted.key").write_text("do not distribute")
        with self.assertRaisesRegex(ValueError, "Unlisted files"):
            release.verify(self.root)

    def test_traversal_in_manifest(self):
        self.entries[0]["path"] = "../outside.bit"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Unsafe release path"):
            release.verify(self.root)

    def test_bit_identity_cannot_be_changed_by_manifest(self):
        bit = self.root / "bitstream" / release.BIT_NAME
        bit.write_bytes(b"x" * len(self.payload))
        self.entries[0]["sha256"] = release.sha256(bit)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "board-tested identity"):
            release.verify(self.root)

    def test_external_symlink_is_rejected(self):
        path = self.root / "README.md"
        path.unlink()
        path.symlink_to(self.root.parent / "outside.md")
        with self.assertRaisesRegex(ValueError, "Unsafe installed file"):
            release.verify(self.root)

    def test_selector_requires_all_frozen_deployment_inputs(self):
        dependency = self.root / "deploy/vendor/example.sv"
        dependency.parent.mkdir(parents=True)
        dependency.write_text("module example; endmodule\n")
        manifest = self.root / "deploy/vendor_manifest.json"
        manifest.write_text(json.dumps({"files": {"vendor/example.sv": {
            "bytes": dependency.stat().st_size, "sha256": release.sha256(dependency)}}}))
        bit_name = "bitstream/" + release.BIT_NAME
        config = {"files": [{"source": bit_name}, {"source": "deploy/vendor_manifest.json"}]}
        with patch.object(release, "ROOT", self.root), patch.object(release, "BIT_SOURCE", bit_name):
            with self.assertRaisesRegex(ValueError, "dependency omitted"):
                release.selected_files(config)
            config["files"].append({"source": "deploy/vendor/example.sv"})
            self.assertIn("deploy/vendor/example.sv", release.selected_files(config))


if __name__ == "__main__":
    unittest.main()
