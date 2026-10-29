"""CPU-only public CLI import check from a real repository path containing spaces."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class PublicCliTests(unittest.TestCase):
    def test_real_cli_dry_run_with_spaces(self):
        release = Path(__file__).resolve().parents[2]
        manifest = json.loads((release/'deploy/vendor_manifest.json').read_text())
        with tempfile.TemporaryDirectory(prefix='ScaleLLM power CLI with spaces ') as temporary:
            root = Path(temporary)
            for relative in [*manifest['files'], 'deploy/vendor_manifest.json']:
                target = root/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(release/relative, target)
            result = subprocess.run([
                sys.executable, str(root/'deploy/scalellm.py'),
                '--config', str(root/'deploy/config.example.json'), 'dry-run'],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = json.loads(result.stdout)
            self.assertEqual(plan['verdict'], 'PLAN_VALID')
            self.assertFalse(plan['device_opened'])
            self.assertEqual(plan['request_count'], 16)
            self.assertEqual(plan['source_files_verified'], len(manifest['files']))


if __name__ == '__main__':
    unittest.main()
