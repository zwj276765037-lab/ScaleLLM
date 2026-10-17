"""Bounded pre-place restart: qualified historical state and fresh live guard stay separate."""
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import unittest
from unittest.mock import patch
from test_m002_physical_diagnostic import Temp, put, manifest, timing, m, SCRIPTS


class CompletedPrePlaceParent(Temp):
    def setUp(self):
        super().setUp();self.addCleanup(patch.stopall);patch.object(m,'ROOT',self.root).start()
        self.project=self.root/'vivado/project/fresh';self.project.mkdir(parents=True)
        self.source=self.root/'vivado/reports/completed';self.report=self.root/'vivado/reports/next';self.report.mkdir(parents=True)
        self.attempt=self.root/'attempt';self.lineage={'project':str(self.project)}
        old_source=self.root/'vivado/reports/old_opt'
        self.old={'phase':'post_opt_pre_debug','synthesis':self.lineage,'source_metadata':{},'actual_reads':[{'actual':'old INIT'}],
                  'generated_phy':{},'generated_debug':{}}
        for key in ('checkpoint','status','child_log','command','stage_inputs','archive','source_registry','opt_command','upstream_recovery','parent_constraints','completed_report_integrity'):
            self.old[key]=m.file_id(put(old_source/('command.json' if key=='command' else key),key))
        self.command={'stage':'place','execution_mode':'checkpoint_restored_commands','synthesis':self.lineage,
                      'managed_attempt':str(self.attempt),'environment':{'HAP_OPT_REPORT_DIR':str(old_source)}}
        put(self.source/'command.json',json.dumps(self.command))
        self.status={'stage':'place','project':str(self.project),'report':str(self.source),'exit_code':124,
                     'native_exit_code':-15,'stop_reason':'stage_wall_timeout','owned_survivors':[]}
        put(self.attempt/'status.json',json.dumps(self.status))
        put(self.source/'recovery_parent.json',json.dumps(self.old))
        put(self.source/'stage_inputs.sha256');put(self.source/'archived_sources.sha256');put(self.source/'implementation_settings.txt')
        for name in m.PRE_PLACE_POST_REQUIRED:put(self.source/name)
        self.dcp=put(self.source/'debug_materialized.dcp','closed pre-place checkpoint fixture');self.saved=m.file_id(self.dcp)
        self.qualified={'checkpoint':self.saved}
        put(self.source/'pre_place_evidence.json','qualified original pre-place fixture')
        structure={'qualified':True,'source':m.file_id(self.source/'reset_graph_debug_materialized.tsv'),
                   'explicit_primitive_exports':[{'netlist':m.file_id(put(self.source/f'export_debug_materialized_{i}.v'))} for i in range(14)]}
        fanout={'qualified':True,'bram_port_clock_endpoints':688,
                'source':m.file_id(self.source/'cdc_changed_reset_debug_materialized.tsv'),
                'bram_port_clock_source':m.file_id(self.source/'bram_port_clocks_debug_materialized.tsv')}
        self.integrity={'gate_issues':[],'reset_structure':structure,'reset_fanout_observation':fanout,
                        'cdc_classification':{'classified_opt_reset':8}}
        put(self.source/'integrity_debug_materialized.json',json.dumps(self.integrity))
        put(self.source/'constraints_debug_materialized.json',json.dumps({'mode':'embedded_checkpoint_inherited','candidate_metadata':{},'hashes':{}}))
        opt='phase=opt\ncommand=opt_design\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n'
        put(old_source/'opt_command',opt);self.old['opt_command']=m.file_id(old_source/'opt_command')
        put(self.source/'recovery_parent.json',json.dumps(self.old));put(self.source/'opt_command_result.txt',opt)
        put(self.source/'debug_materialization_condition.txt','debug_core_count=3\ncondition=actual_get_debug_cores_nonempty\n')
        put(self.source/'debug_materialization_command_result.txt','phase=debug_materialization\ncommand=implement_debug_core\nnative_tcl_code=0\nstarted_epoch=2\nended_epoch=3\n')
        put(self.source/'restored_runtime_settings.txt','ip_cache_after=disable\n')
        put(self.source/'vivado.log',f"Command: open_checkpoint {self.old['checkpoint']['path']}\nThe checkpoint '{self.dcp}' has been generated\nM002_DIAGNOSTIC_STEP_COMPLETED debug_materialized\nCommand: place_design\n")
        put(self.attempt/'terminal_facts.json',json.dumps({'original_status':m.file_id(self.attempt/'status.json'),
            'available_debug_checkpoint':self.saved,'owned_survivors':[],'placed_checkpoint_exists':False}))
        files=[p for p in self.source.iterdir() if p.is_file() and 'debug_materialized' in p.name]
        files += [self.source/n for n in ('pre_place_evidence.json','debug_materialization_condition.txt','debug_materialization_command_result.txt','opt_command_result.txt','restored_runtime_settings.txt')]
        manifest(self.attempt/'completed_pre_place_post.sha256',files)
        put(self.attempt/'completed_pre_place_post_completion.json',json.dumps({
            'original_status':m.file_id(self.attempt/'status.json'),'terminal_facts':m.file_id(self.attempt/'terminal_facts.json'),
            'checkpoint':self.saved,'pre_place':m.file_id(self.source/'pre_place_evidence.json'),
            'manifest':m.file_id(self.attempt/'completed_pre_place_post.sha256'),'processes_gone':True}))
        # These fixtures start from a separately qualified upstream. Real complete
        # archive/graph/DCP qualification is replayed on the frozen AT008 evidence.
        patch.object(m,'validate_stage_archive',return_value={}).start()
        patch.object(m,'recovery_opt_parent',side_effect=lambda *a,**kw:self.old).start()
        patch.object(m,'pre_place_evidence',side_effect=lambda *a,**kw:self.qualified).start()
        patch.object(m,'checkpoint_package',return_value={'fixture':'closed package'}).start()

    def check(self):return m.recovery_pre_place_parent(self.source,self.project,self.lineage,self.report)

    def test_timeout_restarts_saved_pre_place_and_keeps_history_at_original_paths(self):
        value=self.check();self.assertEqual(value['phase'],'post_debug_pre_place');self.assertTrue(value['single_bounded_restart'])
        self.assertEqual(value['checkpoint'],self.saved);self.assertEqual(set(value['historical_command_receipts']),{'opt','debug_materialization'})
        self.assertTrue(all(Path(v['path']).parent==self.source for v in value['historical_command_receipts'].values()))
        self.assertFalse((self.report/'opt_command_result.txt').exists());self.assertFalse((self.report/'debug_materialization_command_result.txt').exists())

    def test_wrong_terminal_or_survivor_never_authorizes_restart(self):
        for changed in ({'exit_code':0},{'native_exit_code':0},{'stop_reason':'resource_limit'},{'owned_survivors':[123]}):
            put(self.attempt/'status.json',json.dumps({**self.status,**changed}))
            with self.assertRaisesRegex(ValueError,'genuine bounded timeout'):self.check()

    def test_second_same_restart_or_new_physical_artifact_is_rejected(self):
        put(self.source/'command.json',json.dumps({**self.command,'environment':{**self.command['environment'],'HAP_PRE_PLACE_REPORT_DIR':'earlier'}}))
        with self.assertRaisesRegex(ValueError,'cannot be repeated'):self.check()
        put(self.source/'command.json',json.dumps(self.command))
        for name in ('place.dcp','physopt.dcp','place_command_result.txt','physopt_command_result.txt'):
            path=put(self.source/name)
            with self.assertRaisesRegex(ValueError,'recover its missing stage'):self.check()
            path.unlink()

    def test_changed_checkpoint_missing_report_and_tampered_complete_report_block(self):
        put(self.dcp,'changed checkpoint')
        with self.assertRaisesRegex(ValueError,'DCP identity changed'):self.check()
        put(self.dcp,'closed pre-place checkpoint fixture');p=self.source/'clocks_debug_materialized.rpt';p.unlink()
        with self.assertRaisesRegex(ValueError,'POST source missing'):self.check()
        put(p,'changed actual clocks report')
        with self.assertRaisesRegex(ValueError,'changed input'):self.check()

    def test_false_original_fanout_qualification_blocks(self):
        self.integrity['reset_fanout_observation']['qualified']=False
        put(self.source/'integrity_debug_materialized.json',json.dumps(self.integrity))
        with self.assertRaisesRegex(ValueError,'qualification incomplete'):self.check()


class RestoredPrePlaceLiveGuard(Temp):
    def setUp(self):
        super().setUp();self.addCleanup(patch.stopall)
        self.source=self.root/'history';self.report=self.root/'next';self.report.mkdir()
        actual=SCRIPTS.parent/'reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt'
        shutil.copy2(actual/'debug_debug_materialized.tsv',self.report/'debug_restore.tsv')
        self.scope=put(self.source/'debug_hub_effective_debug_materialized.xdc',(actual/'debug_hub_effective_debug_materialized.xdc').read_text())
        debug=m.debug_clock_facts(self.report/'debug_restore.tsv',effective_path=self.scope)
        structure={'async_reset_chains':[{'root':f'async{i}'} for i in range(7)],'aux_chains':[{'root':f'aux{i}'} for i in range(4)]}
        self.original=put(self.source/'integrity.json',json.dumps({'debug_clock_observation':debug,'reset_structure':structure}))
        checkpoint=put(self.source/'debug.dcp','closed fixture checkpoint')
        self.parent={'phase':'post_debug_pre_place','source_report':str(self.source),'synthesis':{'project':str(self.root/'project')},
                     'checkpoint':m.file_id(checkpoint),'inherited_pre_place':m.file_id(put(self.source/'pre_place.json')),
                     'inherited_integrity':m.file_id(self.original),'historical_command_receipts':{
                         'opt':m.file_id(put(self.source/'opt_receipt')),'debug_materialization':m.file_id(put(self.source/'debug_receipt'))},
                     'hashes':{},'source_metadata':{}}
        put(self.report/'recovery_parent.json',json.dumps(self.parent))
        put(self.report/'command.json',json.dumps({'execution_mode':'checkpoint_restored_commands','stage':'place','synthesis':self.parent['synthesis'],
            'environment':{'HAP_PRE_PLACE_REPORT_DIR':str(self.source),'HAP_RECOVERY_CHECKPOINT':str(checkpoint)}}))
        put(self.report/'restored_checkpoint_mode.txt',f'checkpoint={checkpoint}\nexecution_mode=checkpoint_restored_commands\n')
        self.preflight='BLACKBOX_COUNT\t0\t\n'+''.join(f'{label}\t{prefix}{i}\t4\n' for label,prefix,n in
            [('ASYNC_SEQUENTIAL_COUNT','async',7),('AUX_SEQUENTIAL_COUNT','aux',4)] for i in range(n))+'PREFLIGHT_ISSUES\t\n'
        put(self.report/'restored_preflight.tsv',self.preflight)
        timing(self.report/'check_timing_pre_place_restore.rpt')
        put(self.report/'pre_place_restore_command_result.txt','phase=pre_place_restore\ncommand=m002_live_pre_place_restore\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n')
        self.guard='completed=1\nblackboxes=0\ndrc_blockers=0\nclock_groups_verified=1\n'
        put(self.report/'pre_place_restore_guard.txt',self.guard);put(self.report/'drc_pre_place_restore.rpt','actual native DRC fixture')
        put(self.report/'constraints_pre_place_restore.json',json.dumps({'mode':'embedded_checkpoint_inherited','hashes':{},'candidate_metadata':{}}))
        put(self.report/'restored_runtime_settings.txt','ip_cache_after=disable\n')
        put(self.report/'vivado.log',f'Command: open_checkpoint {checkpoint}\n')
        manifest(self.report/'stage_inputs.sha256',[self.report/'recovery_parent.json',checkpoint,self.scope,self.original])
        patch.object(m,'recovery_pre_place_parent',side_effect=lambda *a,**kw:self.parent).start()

    def check(self,create=True):return m.restored_pre_place_evidence(self.report,create=create)

    def test_inherited_measurements_and_fresh_live_guard_are_distinct_and_reverifiable(self):
        value=self.check();self.assertEqual(value['phase'],'restored_completed_pre_place')
        self.assertEqual(value['inherited_pre_place'],self.parent['inherited_pre_place']);self.assertTrue(value['diagnostic_eligible'])
        put(self.report/'vivado.log',(self.report/'vivado.log').read_text()+'Command: place_design\n')
        self.assertEqual(value,self.check(create=False))
        with self.assertRaisesRegex(ValueError,'after actual place'):self.check()

    def test_missing_live_sanity_wrong_reset_count_or_native_DRC_blocks(self):
        put(self.report/'restored_preflight.tsv',self.preflight.replace('async0\t4','async0\t3'))
        with self.assertRaisesRegex(ValueError,'reset sanity differs'):self.check()
        put(self.report/'restored_preflight.tsv',self.preflight.replace('PREFLIGHT_ISSUES\t','PREFLIGHT_ISSUES\twrong clock'))
        with self.assertRaisesRegex(ValueError,'live sanity incomplete'):self.check()
        put(self.report/'restored_preflight.tsv',self.preflight)
        put(self.report/'pre_place_restore_guard.txt',self.guard.replace('drc_blockers=0','drc_blockers=1'))
        with self.assertRaisesRegex(ValueError,'native DRC/clock guard'):self.check()

    def test_changed_actual_clock_or_restore_command_checkpoint_blocks(self):
        p=self.report/'debug_restore.tsv';put(p,p.read_text().replace('\tPERIOD\t20.000','\tPERIOD\t3.333'))
        with self.assertRaisesRegex(ValueError,'hub clock relation differs'):self.check()
        shutil.copy2(SCRIPTS.parent/'reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt/debug_debug_materialized.tsv',p)
        p=self.report/'restored_checkpoint_mode.txt';put(p,p.read_text().replace('debug.dcp','foreign.dcp'))
        with self.assertRaisesRegex(ValueError,'checkpoint mismatch'):self.check()

    def test_environment_phase_alone_cannot_authorize_place(self):
        p=self.report/'command.json';v=json.loads(p.read_text());v['environment']['HAP_PRE_PLACE_REPORT_DIR']='foreign';put(p,json.dumps(v))
        with self.assertRaisesRegex(ValueError,'command identity mismatch'):self.check()

    def final_fixture(self):
        self.check()
        for name in ('implementation_settings.txt','restored_runtime_settings.txt','integrity_physopt.json','constraints_physopt.json',
                     'timing_physopt.rpt','check_timing_physopt.rpt','clocks_physopt.rpt','clock_interaction_physopt.rpt','cdc_physopt.rpt',
                     'drc_physopt.rpt','exceptions_physopt.rpt','pulse_width_physopt.rpt','bus_skew_physopt.rpt','utilization_physopt.rpt',
                     'paths_setup_physopt.rpt','paths_hold_physopt.rpt'):put(self.report/name)
        put(self.report/'restored_runtime_settings.txt','ip_cache_after=disable\n')
        put(self.report/'physopt_result.txt','completed=1\ndiagnostic_eligible=1\nblackboxes=0\n')
        put(self.report/'timing_physopt.rpt','WNS(ns) TNS Failing Endpoints\n0 0 0 10 0 0 0 10 0 0 0 10\n')
        timing(self.report/'check_timing_physopt.rpt')
        for phase,command in (('place','place_design'),('physopt','phys_opt_design')):
            put(self.report/f'{phase}_command_result.txt',f'phase={phase}\ncommand={command}\nnative_tcl_code=0\nstarted_epoch=3\nended_epoch=4\n')
        cp=put(self.report/'physopt.dcp','closed physopt fixture')
        manifest(self.report/'implementation_checkpoint.sha256',[cp])
        manifest(self.report/'archived_sources.sha256',[put(self.report/'stage_sources/script.py')])
        graph=put(self.report/'reset_graph_physopt.tsv')
        put(self.report/'integrity_physopt.json',json.dumps({'phase':'physopt','reset_structure':{'qualified':True,'source':m.file_id(graph)},'cdc_classification':{}}))
        put(self.report/'constraints_physopt.json',json.dumps({'mode':'embedded_checkpoint_inherited','hashes':{}}))
        reads=put(self.report/'actual_xdc_reads.json','{}')
        attempt=self.root/'new_attempt';project=Path(self.parent['synthesis']['project'])
        put(attempt/'status.json',json.dumps({'stage':'place','project':str(project),'report':str(self.report),
            'exit_code':0,'native_exit_code':0,'stop_reason':None,'owned_survivors':[]}))
        put(self.report/'launcher_status.txt',f'exit_code=0\nnative_exit_code=0\nstage=place\nproject={project}\nreports={self.report}\n')
        with patch.dict(os.environ,HAP_EXECUTION_MODE='checkpoint_restored_commands',HAP_CURRENT_ATTEMPT_DIR=str(attempt)), \
             patch.object(m,'loaded_constraints',return_value=m.file_id(reads)):
            value=m.finalize('place',project,self.report,self.parent['synthesis'],None)
        return value,project

    def test_final_and_route_parent_keep_only_new_physical_commands_in_current_scope(self):
        value,project=self.final_fixture()
        self.assertEqual(set(value['command_receipts']),{'place','physopt'})
        self.assertEqual(value['historical_command_receipts'],self.parent['historical_command_receipts'])
        self.assertFalse((self.report/'opt_command_result.txt').exists())
        accepted=m.parent_recovered_place(self.report/'diagnostic_evidence.json',project,self.parent['synthesis'])
        self.assertEqual(accepted['checkpoint']['path'],str(self.report/'physopt.dcp'))

    def test_route_parent_rejects_history_presented_as_new_command(self):
        value,project=self.final_fixture();value['command_receipts']['opt']=self.parent['historical_command_receipts']['opt']
        put(self.report/'diagnostic_evidence.json',json.dumps(value))
        with self.assertRaisesRegex(ValueError,'historical/new command scopes mismatch'):
            m.parent_recovered_place(self.report/'diagnostic_evidence.json',project,self.parent['synthesis'])

    def test_controller_runs_new_guard_then_place_and_no_opt_debug(self):
        text=(SCRIPTS/'m002_resume_physical.tcl').read_text();flow=text[text.index('if {$stage eq "place"} {'):text.index('m002_put [file join $report_dir implementation_checkpoint.sha256]')]
        for deny in (0,1):
            prefix=f'''set stage place
set ::env(HAP_RECOVERY_PHASE) post_debug_pre_place
set report_dir {{{self.root}}}
set script_dir /fixture
set sequence {{}}
set deny {deny}
proc m002_put {{args}} {{}}
proc m002_command {{point args}} {{lappend ::sequence $point}}
proc m002_post {{point}} {{lappend ::sequence post_$point}}
proc exec {{args}} {{lappend ::sequence live_admission;if {{$::deny}} {{error "live guard rejected"}}}}
'''
            result=subprocess.run(['tclsh'],input=prefix+'set rc [catch {\n'+flow+'\n} issue]\nputs $rc\nputs $sequence\n',text=True,capture_output=True)
            rows=result.stdout.splitlines();self.assertEqual(rows[0],str(deny),result.stdout+result.stderr)
            expected='pre_place_restore live_admission'+('' if deny else ' place post_place physopt post_physopt')
            self.assertEqual(rows[1],expected)


class RecoveryCliScope(Temp):
    def test_recovery_choices_are_exclusive_and_place_only(self):
        common=[sys.executable,str(SCRIPTS/'run_managed_eda.py')]
        paths=['--attempt',str(self.root/'attempt'),'--project',str(self.root/'project'),'--report',str(self.root/'report')]
        for stage,extra,expected in [('place',['--init-report',str(self.root/'init'),'--pre-place-report',str(self.root/'pre')],'Choose one exact recovery checkpoint phase'),
                                     ('route',['--pre-place-report',str(self.root/'pre')],'place-stage input')]:
            result=subprocess.run(common+[stage]+paths+extra,text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertIn(expected,result.stderr)
            self.assertFalse((self.root/'attempt').exists())


if __name__=='__main__':unittest.main()
