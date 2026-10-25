"""Portable deployment checks; no FPGA, driver loading or Vivado invocation."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
DEPLOY=ROOT/'deploy'
sys.path.insert(0,str(DEPLOY))
import scalellm
import device_health
import build_hardware
import export_model


class DeploymentTests(unittest.TestCase):
    def test_vendor_and_config(self):
        self.assertEqual(scalellm.vendor_check(),133)
        c=scalellm.config(DEPLOY/'config.example.json')
        self.assertEqual(Path(c['bitstream']).parent,ROOT/'bitstream')
        self.assertEqual(c['prompts'],['Hi','Hello'])
        with tempfile.TemporaryDirectory(prefix='deployment config ') as folder:
            path=Path(folder)/'config.json';bad=json.loads((DEPLOY/'config.example.json').read_text());bad['max_new_tokens']=3;path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):scalellm.config(path)

    def test_identity_before_import(self):
        with mock.patch.object(scalellm,'vendor_check',side_effect=ValueError('bad source')),mock.patch.object(scalellm,'bootstrap') as boot:
            with self.assertRaisesRegex(ValueError,'bad source'):scalellm.cpu_check({})
            boot.assert_not_called()

    def test_initial_idle_then_final_shared(self):
        class Fake:
            def __init__(self):self.owner=0x20;self.paired=0x20
            def read32(self,a):return {0:0x48384103,4:0x20000,0x100:0x48384605,0x104:0x70000,0x300:0x4d4c0002,0x304:0x1d,0x308:1,0x2b8:0x4d303032,0x324:8,0x10c:self.owner,0x260:self.paired}.get(a,0)
        s=Fake();device_health.csr_snapshots(s);s.owner=0x7b;s.paired=0x23;device_health.csr_snapshots(s)
        s.owner=s.paired=0x20
        with self.assertRaises(RuntimeError):device_health.csr_snapshots(s)
        s=Fake();s.paired=0x23
        with self.assertRaises(RuntimeError):device_health.csr_snapshots(s)
        s=Fake();s.read32=lambda a:{0:0x48384103,4:0x20000,0xc:0x20,0x324:8,0x10c:0x20,0x260:0x20}.get(a,0)
        with self.assertRaises(RuntimeError):device_health.csr_snapshots(s)

    def test_bounded_bf16_host_asset_stream(self):
        import numpy as np
        original=export_model.load()
        with tempfile.TemporaryDirectory(prefix='host asset stream ') as folder:
            root=Path(folder);path=root/'source.safetensors'
            bits=np.array([0x0000,0x3f80,0xbf80,0x4000,0x3e80,0xc100,0x3fc0,0x0080,0x3f00,0xbf00,0x4040,0x4080,0x3e00,0xbe00,0x4100],dtype='<u2').reshape(5,3)
            header=json.dumps({'weight':{'dtype':'BF16','shape':[5,3],'data_offsets':[0,bits.nbytes]}}).encode();path.write_bytes(struct.pack('<Q',len(header))+header+bits.tobytes())
            reader=original.SafeTensorNumpy(path);calls=[]
            class Checkpoint:
                def float32(self,name,rows):calls.append((rows.start,rows.stop));return reader.float32(name,rows=rows)
            output=root/'out.f32';export_model.stream_fp32_matrix(Checkpoint(),'weight',output,5,3,2)
            self.assertEqual(calls,[(0,2),(2,4),(4,5)])
            np.testing.assert_array_equal(np.fromfile(output,dtype='<u4').reshape(5,3),bits.astype('<u4')<<16)
            with self.assertRaises(FileExistsError):export_model.stream_fp32_matrix(Checkpoint(),'weight',output,5,3,2)

    def test_new_hardware_tree_in_space_path(self):
        with tempfile.TemporaryDirectory(prefix='new GU build ') as folder:
            root=Path(folder);board=root/'board files';board.mkdir()
            for name in ('board.xml','part0_pins.xml','preset.xml'):(board/name).write_text('<test-only/>')
            vivado=root/'Vivado not executed';vivado.touch();work=root/'build workspace'
            result=build_hardware.prepare(work,vivado,board)
            self.assertFalse(result['rtl_changes']);self.assertFalse(result['bit_identical_rebuild_claimed'])
            self.assertEqual(len(result['adapted_files']),2)
            self.assertTrue((work/'project/hardware/vivado/manifests/mlp_gu_only/input_manifest.json').is_file())
            with self.assertRaises(FileExistsError):build_hardware.prepare(work,vivado,board)

    def test_move_release_without_original_paths(self):
        with tempfile.TemporaryDirectory(prefix='moved ScaleLLM project ') as folder:
            moved=Path(folder)/'portable release with spaces';shutil.copytree(DEPLOY,moved/'deploy',ignore=shutil.ignore_patterns('__pycache__'))
            for command in ('dry-run','preflight'):
                r=subprocess.run([sys.executable,str(moved/'deploy/scalellm.py'),command],cwd=folder,capture_output=True,text=True,timeout=60)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr);result=json.loads(r.stdout)
                self.assertFalse(result['device_opened']);self.assertEqual(result['vendor_files_verified'],133)
                if command=='dry-run':self.assertTrue(result['resolved_config']['artifacts'].startswith(str(moved)))

    def test_patch_parser_and_unknown_base_fail_closed(self):
        path=DEPLOY/'driver/prepare_source.py';spec=importlib.util.spec_from_file_location('prepare_driver',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'x').write_text('one\ntwo\n')
            module.apply_unified(root,'--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n one\n-two\n+three\n')
            self.assertEqual((root/'x').read_text(),'one\nthree\n')
            self.assertEqual(module.inspect(root)['verdict'],'SOURCE_REVIEW_REQUIRED')


if __name__=='__main__':unittest.main()
