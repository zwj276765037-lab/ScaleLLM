"""Actual receipt/ownership/identity recovery rules, using CPU fixtures only."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_m002_physical_diagnostic as base
from test_m002_physical_diagnostic import m, put, manifest
import m002_execution_profile as policy
import m002_synthesis_recovery as recovery


class Recovery(unittest.TestCase):
    def setUp(self):
        f=base.Lineage('test_complete');f.setUp();self.addCleanup(f.doCleanups)
        self.fixture=f;self.project=f.project;self.report=f.report;self.attempt=f.attempt
        self.auth={'profile':policy.OPTIMIZED_PROFILE,'contract':{'sha256':'fixture-contract'}}
        self.auth_patch=patch.object(policy,'authorization',return_value=self.auth)
        self.auth_patch.start();self.addCleanup(self.auth_patch.stop)
        self.proc_patch=patch.object(recovery.guard,'process_table',return_value={})
        self.proc_patch.start();self.addCleanup(self.proc_patch.stop)
        (self.attempt/'status.json').unlink()
        policy.save(self.attempt/'execution_authorization.json',self.auth)
        command=dict(stage='synth',execution_profile=policy.OPTIMIZED_PROFILE,
            project=str(self.project),report=str(self.report),started_utc='2026-10-16T00:00:00+00:00',
            authorization=policy.identity(self.attempt/'execution_authorization.json'))
        policy.save(self.attempt/'command.json',command)
        policy.save(self.attempt/'started.json',dict(**command,supervisor_pid=900001,leader_pid=900002))
        last=dict(utc='2026-10-16T00:05:00+00:00',processes={'900002':{'start_ticks':123}})
        put(self.attempt/'resources.jsonl',json.dumps(last)+'\n')
        self.handover=self.attempt/'supervision_handover_fixture';self.handover.mkdir()
        guard=put(f.root/'fixture_guard.py','read-only guard fixture')
        adoption=dict(started_utc='2026-10-16T00:10:00+00:00',adoption_supervisor_pid=900003,
            original_supervisor_pid=900001,original_leader_pid=900002,original_leader_start_ticks=123,
            original_last_resource_utc=last['utc'],original_started_sha256=m.sha256(self.attempt/'started.json'),
            resource_supervision_gap=True,gap_end_utc='2026-10-16T00:10:00+00:00',
            native_process_restarted=False,original_records_modified=False,
            attempt=str(self.attempt),report=str(self.report),guard_sha256=m.sha256(guard),
            cpu_affinity=list(range(8)),nice=5,rss_limit_bytes=192*recovery.guard.GIB,
            mem_available_floor_bytes=48*recovery.guard.GIB,mem_low_grace_seconds=30,
            disk_free_floor_bytes=30*recovery.guard.GIB,timeout_seconds=None,no_output_timeout_seconds=None)
        policy.save(self.handover/'started.json',adoption)
        wrapper=f'stage=synth\nexit_code=0\nnative_exit_code=0\nproject={self.project}\nreports={self.report}\n'
        put(self.report/'launcher_status.txt',wrapper)
        policy.save(self.handover/'status.json',dict(**adoption,ended_utc='2026-10-16T00:15:00+00:00',
            stop_reason=None,native_exit_code=None,native_exit_not_waitable_after_orphaning=True,
            final_owned_processes={},controller_launcher_status=wrapper))
        put(self.handover/'resources.jsonl',json.dumps(dict(utc='2026-10-16T00:15:00+00:00',processes={},live_pids=[]))+'\n')
        policy.save(self.handover/'guard_process_identity.json',dict(pid=900003,proc_identity={'pgrp':900003},cmdline=['python3',str(guard)]))
        records={name:m.file_id(self.attempt/name) for name in ['started.json','command.json','resources.jsonl']}
        policy.save(self.handover/'original_evidence_snapshot.json',dict(original_terminal_status_exists=False,
            original_immutable_records=records,original_last_resource_sample=last))
        for i in range(3):put(f.root/f'src/new{i}',f'optimized input{i}')
        manifest(self.report/'inputs.sha256',sorted((f.root/'src').iterdir()))
        put(self.report/'fresh_synth_complete.txt',f'project {self.project} inputs_sha256 {m.sha256(self.report/"inputs.sha256")} identity_sha256 {m.sha256(self.report/"build_identity.txt")}\n')
        put(self.report/'vivado.log',f'E005_OPTIMIZED_STRUCTURE_COMPLETED synth 48/16/16 boundary CE graphs\nCOMPLETED: synth reports at {self.report}\nExiting Vivado\n')
        put(self.report/'optimized_structure_synth_result.txt','phase=synth\nissues=\nboundary_contract=48input_16gate_16down\n')
        for name in ['optimized_boundaries_synth.tsv','optimized_control_sources_synth.tsv']:put(self.report/name)

    def record(self):
        return recovery.record_recovery(self.project,self.report,self.attempt,self.handover)

    def mutate_json(self,path,**changes):
        value=json.loads(path.read_text());value.update(changes);policy.save(path,value)

    def anchor(self):
        names=(set(m.SYNTH_ANCHORS)-{'status.json'})|{recovery.RECEIPT}
        anchors={name:m.sha256((self.report if name in {'inputs.sha256','build_identity.txt','fresh_synth_complete.txt'} else self.attempt)/name) for name in names}
        policy.save(self.attempt/'frozen_synthesis_anchor.json',dict(project=str(self.project),report=str(self.report),
            execution_authorization=self.auth,source_rows=342,anchors=anchors))

    def test_native_success_has_independent_receipt_and_unknown_wait(self):
        value=self.record();self.anchor();lineage=self.fixture.check()
        self.assertFalse((self.attempt/'status.json').exists())
        self.assertEqual(value['checkpoint_paths'],45)
        self.assertIsNone(value['original_supervisor_exit_code'])
        self.assertIsNone(value['original_leader_wait_exit_code'])
        self.assertFalse(lineage['supervision']['supervision_continuous'])
        self.assertNotIn('managed_status',lineage)
        self.assertEqual(lineage['source_rows'],342)

    def test_missing_wrapper_rejected(self):
        (self.report/'launcher_status.txt').unlink()
        with self.assertRaises(FileNotFoundError):self.record()

    def test_native_nonzero_rejected(self):
        p=self.report/'launcher_status.txt';p.write_text(p.read_text().replace('native_exit_code=0','native_exit_code=1'))
        with self.assertRaisesRegex(ValueError,'native/wrapper'):self.record()

    def test_wrapper_post_failure_rejected(self):
        p=self.report/'launcher_status.txt';p.write_text(p.read_text().replace('exit_code=0\n','exit_code=1\n',1))
        with self.assertRaisesRegex(ValueError,'native/wrapper'):self.record()

    def test_resource_stop_rejected(self):
        self.mutate_json(self.handover/'status.json',stop_reason='task_tree_rss_above_192GiB')
        with self.assertRaisesRegex(ValueError,'handover stopped'):self.record()

    def test_final_owned_process_rejected(self):
        self.mutate_json(self.handover/'status.json',final_owned_processes={'900002':{'start_ticks':123}})
        with self.assertRaisesRegex(ValueError,'handover stopped'):self.record()

    def test_live_original_identity_rejected(self):
        with patch.object(recovery.guard,'process_table',return_value={900002:{'start_ticks':123}}):
            with self.assertRaisesRegex(ValueError,'still present'):self.record()

    def test_source_change_rejected(self):
        put(self.fixture.root/'src/4','modified source')
        with self.assertRaisesRegex(ValueError,'changed input'):self.record()

    def test_closure_tamper_rejected(self):
        self.record();self.mutate_json(self.attempt/recovery.RECEIPT,original_supervisor_exit_code=0)
        with self.assertRaisesRegex(ValueError,'closure changed'):recovery.validate_recovery(self.project,self.report,self.attempt)

    def test_binding_tamper_rejected(self):
        self.record();p=next((self.project/'scalellm_vcu118_f05.runs').glob('*/*.dcp'));p.write_text('changed checkpoint')
        with self.assertRaisesRegex(ValueError,'changed input'):recovery.validate_recovery(self.project,self.report,self.attempt)

    def test_original_status_cannot_be_replaced_or_shadowed(self):
        put(self.attempt/'status.json','{}')
        with self.assertRaisesRegex(ValueError,'cannot replace'):self.record()

    def test_missing_marker_and_failed_structure_rejected(self):
        put(self.report/'fresh_synth_complete.txt','wrong marker')
        with self.assertRaisesRegex(ValueError,'completion binding'):self.record()
        put(self.report/'optimized_structure_synth_result.txt','phase=synth\nissues=wrong\nboundary_contract=48input_16gate_16down\n')
        with self.assertRaisesRegex(ValueError,'structure did not pass'):self.record()

    def test_original_resource_snapshot_tamper_rejected(self):
        p=self.attempt/'resources.jsonl';p.write_text(p.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'identity changed'):self.record()


if __name__=='__main__':unittest.main()
