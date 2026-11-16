"""Frozen integration identity and offline pilot cadence regression."""
import ctypes
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
POWER=ROOT/'resource_optimization/deployment/power'
sys.path.insert(0,str(POWER))
import pilot


class PortablePowerAnalysisTests(unittest.TestCase):
    def test_frozen_decoding_and_integration_files_are_unchanged(self):
        for name in ('kv128_sevenrail_analyze.py','kv128_sevenrail_windows.py'):
            self.assertEqual((POWER/name).read_bytes(),
                (ROOT/'resource_optimization/power_retest/source/analysis_frozen'/name).read_bytes())

    def test_offline_pilot_reuses_raw_words_and_raw_sweep_start_cadence(self):
        folder=ROOT/'outputs/resource_optimization_power/pilot_001'
        if not (folder/'telemetry.jsonl').is_file():
            self.skipTest('Historical raw download is required for this optional data regression')
        metadata=json.loads((folder/'telemetry.json').read_text(encoding='utf-8-sig'))
        receipt=dict(schema='scalellm_portable_power_launcher_v1',action='pilot',state='COMPLETE',
                     sampler_exit_code=0,lease_released=True,survivors=[],bit_sha256=pilot.BIT_SHA,
                     sampler_script_sha256='fixture',powertool_manifest_sha256='fixture',
                     **{key:metadata[key] for key in ('run_id','boot_utc','qpc_frequency')})
        with tempfile.TemporaryDirectory(prefix='offline power pilot ') as temporary:
            path=Path(temporary)/'receipt.json';path.write_text(json.dumps(receipt))
            with mock.patch.object(ctypes,'WinDLL',create=True,side_effect=AssertionError('device access')):
                result=pilot.freeze_pilot(folder/'telemetry.json',folder/'telemetry.jsonl',path)
            self.assertEqual(result['sweep_period_ms']['p95'],118.3493)
            self.assertEqual(result['target_period_ms'],150)
            self.assertEqual(result['gap_threshold_ms'],450)
            receipt['sampler_exit_code']=1;path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(RuntimeError,'launcher/native exit'):
                pilot.freeze_pilot(folder/'telemetry.json',folder/'telemetry.jsonl',path)

    def test_new_runtime_has_no_frozen_legacy_script_hash_bypass(self):
        script=(POWER/'run_power.ps1').read_text()
        self.assertIn("'source_manifest.json'",script)
        self.assertIn("$source.files.PSObject.Properties",script)
        self.assertIn('Portable source identity differs',script)
        self.assertIn('SAMPLER_OPERATION_HEARTBEAT_TIMEOUT',script)
        self.assertIn('[IO.Path]::GetPathRoot($script:OutputDir)',script)
        self.assertNotIn('Get-PSDrive D',script)
        self.assertIn('fixed_wall_time_termination=$false',script)
        self.assertIn("'-MaxSeconds',$(if($Action -eq 'pilot'){[string]$PilotSeconds}else{'0'})",script)


if __name__=='__main__':
    unittest.main()
