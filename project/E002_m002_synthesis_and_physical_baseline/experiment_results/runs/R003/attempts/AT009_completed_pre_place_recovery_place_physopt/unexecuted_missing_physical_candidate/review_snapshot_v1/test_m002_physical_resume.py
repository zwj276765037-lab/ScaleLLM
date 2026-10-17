"""Closed physical outputs can advance only missing POST/physopt, never place."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from test_m002_physical_diagnostic import Temp, put, manifest, m, SCRIPTS
from test_m002_pre_place_recovery import RestoredPrePlaceLiveGuard


class ClosedPhysicalParent(Temp):
    def setUp(self):
        super().setUp();self.addCleanup(patch.stopall)
        patch.object(m,'ROOT',self.root).start()
        self.source=self.root/'vivado/reports/closed';self.source.mkdir(parents=True)
        self.report=self.root/'vivado/reports/new';self.report.mkdir()
        self.project=self.root/'vivado/project/project';self.project.mkdir(parents=True)
        self.attempt=self.root/'attempt';self.lineage={'project':str(self.project)}
        self.old={'phase':'post_debug_pre_place','synthesis':self.lineage,'hashes':{},'source_metadata':{},
            'source_archives':{},'tool_debug_metadata':{},'generated_source_candidates':{},'actual_reads':[{'original':'read'}],
            'source_registry':m.file_id(put(self.root/'history/registry')),
            'inherited_integrity':m.file_id(put(self.root/'history/integrity')),
            'historical_command_receipts':{}}
        for phase,command in (('opt','opt_design'),('debug_materialization','implement_debug_core')):
            self.old['historical_command_receipts'][phase]=m.file_id(put(self.root/'history'/phase,
                f'phase={phase}\ncommand={command}\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n'))
        put(self.source/'recovery_parent.json',json.dumps(self.old))
        put(self.source/'pre_place_evidence.json','qualified historical pre-place admission')
        put(self.source/'command.json',json.dumps({'stage':'place','execution_mode':'checkpoint_restored_commands',
            'synthesis':self.lineage,'managed_attempt':str(self.attempt)}))
        self.status={'stage':'place','project':str(self.project),'report':str(self.source),
            'exit_code':124,'native_exit_code':-15,'stop_reason':'stage_wall_timeout','owned_survivors':[],
            'ended_utc':'2026-10-15T11:41:08+00:00'}
        put(self.attempt/'status.json',json.dumps(self.status))
        for name in ('implementation_settings.txt','stage_inputs.sha256','archived_sources.sha256'):put(self.source/name)
        put(self.source/'constraints_pre_place_restore.json',json.dumps({'mode':'embedded_checkpoint_inherited',
            'hashes':{},'candidate_metadata':{}}))
        self.cp=put(self.source/'place.dcp','closed placed fixture bytes')
        self.receipt=put(self.source/'place_command_result.txt',
            'phase=place\ncommand=place_design\nnative_tcl_code=0\nstarted_epoch=100\nended_epoch=101\n')
        put(self.source/'vivado.log',f"Command: place_design\nThe checkpoint '{self.cp}' has been generated\n")
        guard=put(self.source/'pre_place_restore_command_result.txt','ended_epoch=10\n')
        patch.object(m,'restored_pre_place_evidence',return_value={'live_guard_command':m.file_id(guard)}).start()
        patch.object(m,'validate_stage_archive',return_value={}).start()
        self.package={'part':'qualified fixture part'}
        patch.object(m,'checkpoint_package',return_value=self.package).start()
        self.close()

    def close(self):
        manifest(self.attempt/'closed_physical_source.sha256',[p for p in self.source.iterdir() if p.is_file()])
        self.completion={'original_status':m.file_id(self.attempt/'status.json'),'processes_gone':True,
            'observed_utc':'2026-10-15T11:42:00+00:00','manifest':m.file_id(self.attempt/'closed_physical_source.sha256'),
            'checkpoints':{'place':m.file_id(self.cp)},'checkpoint_packages':{'place':self.package},
            'native_command_receipts':{'place':m.file_id(self.receipt)},'complete_posts':{}}
        put(self.attempt/'closed_physical_source_completion.json',json.dumps(self.completion))

    def check(self):return m.recovery_physical_parent(self.source,self.project,self.lineage,self.report)

    def test_closed_place_resumes_only_missing_POST_and_physopt_with_original_receipts(self):
        value=self.check();self.assertEqual(value['phase'],'post_place_pre_physopt')
        self.assertFalse(value['physical_post_complete']);self.assertEqual(value['checkpoint'],m.file_id(self.cp))
        self.assertEqual(set(value['historical_command_receipts']),{'opt','debug_materialization','place'})
        self.assertEqual(value['historical_command_receipts']['place']['path'],str(self.receipt))
        self.assertFalse((self.report/'place_command_result.txt').exists())

    def test_active_wrong_terminal_or_survivor_blocks(self):
        for key,value in (('exit_code',0),('native_exit_code',0),('stop_reason',None),('owned_survivors',[123])):
            changed={**self.status,key:value};put(self.attempt/'status.json',json.dumps(changed))
            with self.assertRaisesRegex(ValueError,'ended bounded timeout'):self.check()
        put(self.attempt/'status.json',json.dumps(self.status))

    def test_missing_native_success_or_unclosed_DCP_cannot_advance(self):
        original=self.receipt.read_text();put(self.receipt,original.replace('native_tcl_code=0','native_tcl_code=1'));self.close()
        with self.assertRaisesRegex(ValueError,'no new closed'):self.check()
        put(self.receipt,original);put(self.source/'vivado.log','Command: place_design\n');self.close()
        with self.assertRaisesRegex(ValueError,'no new closed'):self.check()

    def test_copied_historical_receipt_before_live_restore_is_rejected(self):
        put(self.receipt,self.receipt.read_text().replace('started_epoch=100','started_epoch=3').replace('ended_epoch=101','ended_epoch=4'))
        self.close()
        with self.assertRaisesRegex(ValueError,'restore chronology'):self.check()

    def test_checkpoint_tamper_or_missing_terminal_closure_blocks(self):
        put(self.cp,'changed bytes')
        with self.assertRaisesRegex(ValueError,'changed input'):self.check()
        self.close();self.completion['processes_gone']=False
        put(self.attempt/'closed_physical_source_completion.json',json.dumps(self.completion))
        with self.assertRaisesRegex(ValueError,'post-termination closure'):self.check()

    def test_partial_POST_cannot_be_promoted_to_completed_inheritance(self):
        self.completion['complete_posts']={'place':{'result':{},'integrity':{}}}
        put(self.attempt/'closed_physical_source_completion.json',json.dumps(self.completion))
        with self.assertRaises((ValueError,FileNotFoundError)):self.check()

    def test_more_advanced_closed_physopt_is_selected_only_with_qualified_place_predecessor(self):
        put(self.source/'place_result.txt','completed=1\ndiagnostic_eligible=1\nphase=place\nblackboxes=0\nclock_coverage=COMPLETE_INTERNAL\n')
        put(self.source/'integrity_place.json',json.dumps({'phase':'place','gate_issues':[],
            'reset_structure':{'qualified':True},'cdc_classification':{}}))
        put(self.source/'constraints_place.json',json.dumps({'mode':'embedded_checkpoint_inherited','hashes':{},'candidate_metadata':{}}))
        cp=put(self.source/'physopt.dcp','closed physopt fixture')
        receipt=put(self.source/'physopt_command_result.txt','phase=physopt\ncommand=phys_opt_design\nnative_tcl_code=0\nstarted_epoch=200\nended_epoch=201\n')
        p=self.source/'vivado.log';put(p,p.read_text()+f"M002_DIAGNOSTIC_STEP_COMPLETED place\nCommand: phys_opt_design\nThe checkpoint '{cp}' has been generated\n")
        self.close();self.completion['checkpoints']['physopt']=m.file_id(cp)
        self.completion['checkpoint_packages']['physopt']=self.package
        self.completion['native_command_receipts']['physopt']=m.file_id(receipt)
        self.completion['complete_posts']['place']={k:m.file_id(self.source/n) for k,n in
            (('result','place_result.txt'),('integrity','integrity_place.json'))}
        put(self.attempt/'closed_physical_source_completion.json',json.dumps(self.completion))
        with patch.object(m,'verify_reset_proof'),patch.object(m,'verify_cdc_proof'):
            value=self.check()
            self.assertEqual(value['phase'],'post_physopt_pre_finalize')
            self.assertEqual(value['checkpoint'],m.file_id(cp));self.assertEqual(len(value['historical_command_receipts']),4)
            self.completion['complete_posts'].pop('place')
            put(self.attempt/'closed_physical_source_completion.json',json.dumps(self.completion))
            with self.assertRaisesRegex(ValueError,'qualified predecessor'):self.check()


class PhysicalResumeFlow(Temp):
    def test_controller_never_repeats_place_and_only_runs_missing_successor(self):
        text=(SCRIPTS/'m002_resume_physical.tcl').read_text()
        flow=text[text.index('if {$stage eq "place"} {'):text.index('m002_put [file join $report_dir implementation_checkpoint.sha256]')]
        for phase,expected in (('post_place_pre_physopt','pre_place_restore live_admission post_place physopt post_physopt'),
                               ('post_physopt_pre_finalize','pre_place_restore live_admission post_physopt')):
            for deny in (0,1):
                prefix=f'''set stage place
set ::env(HAP_RECOVERY_PHASE) {phase}
set report_dir {{{self.root}}}
set script_dir /fixture
set sequence {{}}
set deny {deny}
proc m002_put {{args}} {{}}
proc m002_command {{point args}} {{lappend ::sequence $point}}
proc m002_post {{point}} {{lappend ::sequence post_$point}}
proc exec {{args}} {{lappend ::sequence live_admission;if {{$::deny}} {{error "guard rejected"}}}}
'''
                result=subprocess.run(['tclsh'],input=prefix+'set rc [catch {\n'+flow+'\n} issue]\nputs $rc\nputs $sequence\n',text=True,capture_output=True)
                rows=result.stdout.splitlines();self.assertEqual(rows[0],str(deny),result.stdout+result.stderr)
                self.assertEqual(rows[1],'pre_place_restore live_admission' if deny else expected)

    def test_physical_recovery_CLI_is_exclusive_and_place_stage_only(self):
        common=[sys.executable,str(SCRIPTS/'run_managed_eda.py')]
        paths=['--attempt',str(self.root/'attempt'),'--project',str(self.root/'project'),'--report',str(self.root/'report')]
        for stage,extra,expected in (('route',['--physical-report',str(self.root/'physical')],'place-stage input'),
                ('place',['--physical-report',str(self.root/'physical'),'--pre-place-report',str(self.root/'pre')],'Choose one exact')):
            result=subprocess.run(common+[stage]+paths+extra,text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertIn(expected,result.stderr)
            self.assertFalse((self.root/'attempt').exists())


class PhysicalResumeLiveAndFinal(unittest.TestCase):
    def fixture(self,point='place',final=False):
        f=RestoredPrePlaceLiveGuard('test_environment_phase_alone_cannot_authorize_place');f.setUp();self.addCleanup(f.doCleanups)
        if final:f.final_fixture()
        parent={**f.parent,'phase':'post_place_pre_physopt' if point=='place' else 'post_physopt_pre_finalize',
            'physical_point':point,'inherited_pre_place':m.file_id(put(f.source/'original_pre_place.json','original qualified admission'))}
        for phase,native in (('opt','opt_design'),('debug_materialization','implement_debug_core'),('place','place_design'),('physopt','phys_opt_design')):
            if phase=='physopt' and point=='place':continue
            parent['historical_command_receipts'][phase]=m.file_id(put(f.source/f'history_{phase}.txt',
                f'phase={phase}\ncommand={native}\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n'))
        put(f.report/'recovery_parent.json',json.dumps(parent))
        command=json.loads((f.report/'command.json').read_text());command['environment']['HAP_PHYSICAL_REPORT_DIR']=str(f.source)
        command['environment'].pop('HAP_PRE_PLACE_REPORT_DIR',None);put(f.report/'command.json',json.dumps(command))
        manifest(f.report/'stage_inputs.sha256',[f.report/'recovery_parent.json',Path(parent['checkpoint']['path']),f.scope,f.original])
        patch.object(m,'recovery_physical_parent',return_value=parent).start()
        f.parent=parent
        return f,parent

    def test_fresh_physical_guard_is_distinct_from_inherited_pre_place(self):
        f,parent=self.fixture();value=m.physical_resume_evidence(f.report,create=True)
        self.assertEqual(value['phase'],'restored_physical_checkpoint_live_admission')
        self.assertEqual(value['inherited_pre_place'],parent['inherited_pre_place'])
        put(f.report/'vivado.log',(f.report/'vivado.log').read_text()+'Command: phys_opt_design\n')
        self.assertEqual(value,m.physical_resume_evidence(f.report))

    def test_frozen_parent_uses_its_archive_while_changed_design_input_still_blocks(self):
        f,parent=self.fixture();live=put(f.root/'live_scripts/tool.py','original stage code')
        archived=put(f.report/'stage_sources/tool.py','original stage code')
        manifest(f.report/'archived_sources.sha256',[archived])
        design=put(f.root/'design_input','fixed design identity')
        manifest(f.report/'stage_inputs.sha256',[f.report/'recovery_parent.json',Path(parent['checkpoint']['path']),
            f.scope,f.original,live,design])
        put(live,'later installed stage code')
        with self.assertRaisesRegex(ValueError,'changed input'):m.physical_resume_evidence(f.report,create=True)
        m.physical_resume_evidence(f.report,create=True,frozen_source=True)
        put(design,'changed design')
        with self.assertRaisesRegex(ValueError,'design/probe input changed'):
            m.physical_resume_evidence(f.report,frozen_source=True)

    def test_missing_live_guard_wrong_count_or_environment_alone_blocks(self):
        f,parent=self.fixture();put(f.report/'pre_place_restore_guard.txt',f.guard.replace('drc_blockers=0','drc_blockers=1'))
        with self.assertRaisesRegex(ValueError,'fresh native DRC'):m.physical_resume_evidence(f.report,create=True)
        put(f.report/'pre_place_restore_guard.txt',f.guard);put(f.report/'restored_preflight.tsv',f.preflight.replace('async0\t4','async0\t3'))
        with self.assertRaisesRegex(ValueError,'live reset count'):m.physical_resume_evidence(f.report,create=True)
        put(f.report/'restored_preflight.tsv',f.preflight);p=f.report/'command.json';d=json.loads(p.read_text())
        d['environment']['HAP_RECOVERY_CHECKPOINT']='foreign';put(p,json.dumps(d))
        with self.assertRaisesRegex(ValueError,'actual command/checkpoint'):m.physical_resume_evidence(f.report,create=True)

    def test_completed_POST_copy_preserves_original_origin_without_new_command_receipt(self):
        f,parent=self.fixture();parent['physical_post_complete']=True
        parent['source_completion']=m.file_id(put(f.source/'completion.json','original closure'))
        parent['inherited_reports']={n:m.file_id(put(f.source/n,'original completed report')) for n in
            ('timing_place.rpt','place_result.txt')}
        put(f.report/'recovery_parent.json',json.dumps(parent))
        manifest(f.report/'stage_inputs.sha256',[f.report/'recovery_parent.json',Path(parent['checkpoint']['path']),f.scope,f.original])
        m.physical_resume_evidence(f.report,create=True);m.inherit_physical_post(f.report)
        self.assertEqual((f.report/'timing_place.rpt').read_text(),'original completed report')
        self.assertFalse((f.report/'place_command_result.txt').exists())
        value=json.loads((f.report/'inherited_physical_post.json').read_text())
        self.assertEqual(value['reports'],parent['inherited_reports'])

    def test_finalize_and_route_parent_separate_current_and_historical_commands(self):
        for point in ('place','physopt'):
            with self.subTest(point=point):
                f,parent=self.fixture(point,final=True)
                (f.report/'place_command_result.txt').unlink()
                if point=='physopt':(f.report/'physopt_command_result.txt').unlink()
                m.physical_resume_evidence(f.report,create=True)
                reads=f.report/'actual_xdc_reads.json';attempt=f.root/'new_attempt';project=Path(parent['synthesis']['project'])
                with patch.dict(os.environ,HAP_EXECUTION_MODE='checkpoint_restored_commands',HAP_CURRENT_ATTEMPT_DIR=str(attempt)), \
                     patch.object(m,'loaded_constraints',return_value=m.file_id(reads)):
                    value=m.finalize('place',project,f.report,parent['synthesis'],None)
                self.assertEqual(set(value['command_receipts']),{'physopt'} if point=='place' else set())
                self.assertEqual(value['historical_command_receipts'],parent['historical_command_receipts'])
                self.assertEqual(value['pre_place'],parent['inherited_pre_place'])
                m.parent_recovered_place(f.report/'diagnostic_evidence.json',project,parent['synthesis'])
                value['command_receipts']['place']=parent['historical_command_receipts']['place']
                put(f.report/'diagnostic_evidence.json',json.dumps(value))
                with self.assertRaisesRegex(ValueError,'inherited/current command'):m.parent_recovered_place(f.report/'diagnostic_evidence.json',project,parent['synthesis'])
                f.doCleanups()


if __name__=='__main__':unittest.main()
