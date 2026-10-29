"""Release integrity checks with small synthetic artifacts, no board required."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('release_tool', Path(__file__).resolve().parents[1] / 'tools/package_release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        payload = b'synthetic test bitstream'
        self.digest = hashlib.sha256(payload).hexdigest()
        for name, data in {
            'bitstream/' + release.BIT_NAME: payload,
            'README.md': b'test release\n',
            'deploy/vendor/example.py': b'VALUE = 1\n',
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        dependency = self.root / 'deploy/vendor/example.py'
        for name, data in {
            'deploy/vendor_manifest.json': {'files': {'deploy/vendor/example.py': {'bytes': dependency.stat().st_size, 'sha256': release.sha256(dependency)}}},
            'deploy/final/hardware_source_manifest.json': {'files': {}, 'portable_build_files': {}},
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        self.config = {'files': sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob('*') if p.is_file())}
        for name, value in [('BIT_SHA256', self.digest), ('BIT_SIZE', len(payload))]:
            patcher = patch.object(release, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        release.seal(self.root, self.config)

    def change_manifest(self, callback):
        path = self.root / release.MANIFEST
        manifest = json.loads(path.read_text())
        callback(manifest)
        path.write_text(json.dumps(manifest))

    def test_intact_package(self):
        self.assertEqual(release.verify(self.root)['status'], 'PASS')

    def test_content_tampering(self):
        (self.root / 'README.md').write_text('corrupt data\n')
        with self.assertRaisesRegex(ValueError, 'verification failed'):
            release.verify(self.root)

    def test_extra_file(self):
        (self.root / 'unlisted.key').write_text('do not distribute')
        with self.assertRaisesRegex(ValueError, 'Unlisted files'):
            release.verify(self.root)

    def test_traversal_and_windows_paths(self):
        for path in ('../outside.bit', 'C:/outside.bit', 'a\\b', '/etc/passwd', 'a//b'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'Unsafe release path'):
                release.safe_relative(path)

    def test_bit_identity_independent_of_manifest(self):
        name = 'bitstream/' + release.BIT_NAME
        bit = self.root / name
        bit.write_bytes(b'x' * bit.stat().st_size)
        def change(manifest):
            next(e for e in manifest['files'] if e['path'] == name)['sha256'] = release.sha256(bit)
        self.change_manifest(change)
        with self.assertRaisesRegex(ValueError, 'board-tested identity'):
            release.verify(self.root)

    def test_external_symlink(self):
        path = self.root / 'README.md'
        path.unlink()
        path.symlink_to(self.root.parent / 'outside.md')
        with self.assertRaisesRegex(ValueError, 'Unsafe installed file'):
            release.verify(self.root)

    def test_omitted_source_dependency(self):
        self.config['files'].remove('deploy/vendor/example.py')
        with self.assertRaisesRegex(ValueError, 'dependency omitted'):
            release.selected_files(self.config, self.root)

    def test_changed_dependency_even_with_release_hash(self):
        name = 'deploy/vendor/example.py'
        path = self.root / name
        path.write_text('VALUE = 2\n')
        def change(manifest):
            next(e for e in manifest['files'] if e['path'] == name)['sha256'] = release.sha256(path)
        self.change_manifest(change)
        with self.assertRaisesRegex(ValueError, 'Frozen dependency mismatch'):
            release.verify(self.root)

    def test_build_preserves_integrity(self):
        output = self.root / 'dist' / release.PROJECT
        first = release.build(self.root, output)
        self.assertEqual(release.verify(output)['status'], 'PASS')
        self.assertTrue(Path(first['archive']).is_file())
        with self.assertRaisesRegex(ValueError, 'new directory'):
            release.build(self.root, output)

    def test_local_artifacts_not_traversed(self):
        p = self.root / 'models/private.safetensors'
        p.parent.mkdir()
        p.write_bytes(b'not released')
        (self.root / '.git').write_text('gitdir: local worktree')
        self.assertEqual(release.verify(self.root)['status'], 'PASS')


if __name__ == '__main__':
    unittest.main()
