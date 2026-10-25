"""Public generic mode has no baseline dependency or premature numerical PASS."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'deploy'))
import scalellm
scalellm.vendor_check();scalellm.bootstrap()
import device_health
from optimized import run
from optimized.backends import ResidentAttention,global_guard
from optimized.verification import DeferredCatalog
from evidence import Evidence
from test_optimized_protocol import FakeSession,Artifacts


class DeferredTests(unittest.TestCase):
    def test_default_public_plan_without_any_baseline(self):
        output=io.StringIO()
        with mock.patch.object(sys,'argv',['scalellm.py','resident','--dry-run']),contextlib.redirect_stdout(output):scalellm.main()
        plan=json.loads(output.getvalue());self.assertEqual(plan['validation_mode'],'deferred');self.assertIsNone(plan['baseline_root']);self.assertIsNone(plan['baseline_index'])
        self.assertFalse(plan['device_opened']);self.assertEqual(plan['numerical_verdict_after_execution'],'NUMERICAL_VERIFICATION_PENDING')
        with mock.patch('optimized.run.GoldCatalog',side_effect=AssertionError('baseline must not be touched')):
            catalog=run.catalog_for('deferred',ROOT/'nonexistent',None,None,None)
        self.assertIsInstance(catalog,DeferredCatalog)
        with self.assertRaises(ValueError):run.catalog_for('audited_baseline','unused',None,None,None)

    def test_config_prompts_and_generation_count_are_actual_arguments(self):
        assets=object()
        with mock.patch('optimized.run.actual_requests',return_value=('tokenizer','requests')) as actual:
            self.assertEqual(run.requests_for_config(assets,{'prompts':['Good','Day'],'max_new_tokens':1}),('tokenizer','requests'))
        actual.assert_called_once_with(assets,('Good','Day'),1)
        with self.assertRaises(ValueError):run.requests_for_config(assets,{'prompts':['Good','Day'],'max_new_tokens':3})

    def test_deferred_adapter_still_fullcopies_identity_checks_then_clears(self):
        with tempfile.TemporaryDirectory() as folder:
            s=FakeSession();catalog=DeferredCatalog();e=Evidence(Path(folder)/'run')
            a=ResidentAttention(s,Artifacts(),type('Store',(),{'require':lambda self:None})(),e,catalog,lambda:None)
            payload=bytes([7])*196608;a.start(0,0,0,payload,3,4,'a');s.complete_attention(command=3,request=4);output,record=a.collect()
            self.assertTrue(record['copied'] and record['sticky_cleared']);self.assertEqual(record['comparison'],'NUMERICAL_VERIFICATION_PENDING')
            self.assertIsNone(record['expected_output_sha256']);self.assertEqual(len(output),196608);self.assertEqual(len(catalog.used),1)
            self.assertEqual(s.writes[-1],(8,2));self.assertEqual((e.root/'a/input_s24.bin').read_bytes(),payload)
        with tempfile.TemporaryDirectory() as folder:
            s=FakeSession();a=ResidentAttention(s,Artifacts(),type('Store',(),{'require':lambda self:None})(),Evidence(Path(folder)/'run'),DeferredCatalog(),lambda:None)
            a.start(0,0,0,bytes(196608),3,4,'a');s.complete_attention(command=99,request=4)
            with self.assertRaises(RuntimeError):a.collect()
            self.assertNotIn((8,2),s.writes);self.assertIsNotNone(a.pending)

    def test_retained_error_only_current_while_completion_valid(self):
        s=FakeSession();s.r[0x350]=0x2200;s.r[0x10c]=0x3b;s.r[0xc]=0
        global_guard(s)
        abi={0:0x48384103,4:0x20000,0x100:0x48384605,0x104:0x70000,0x300:0x4d4c0002,0x304:0x1d,0x308:1,0x2b8:0x4d303032}
        s.r.update(abi);device_health.csr_snapshots(s)
        s.r[0x324]=10
        with self.assertRaises(RuntimeError):global_guard(s)
        with self.assertRaises(RuntimeError):device_health.csr_snapshots(s)
        s.r[0x324]=8;s.r[0x178]=8
        with self.assertRaises(RuntimeError):global_guard(s)


if __name__=='__main__':unittest.main()
