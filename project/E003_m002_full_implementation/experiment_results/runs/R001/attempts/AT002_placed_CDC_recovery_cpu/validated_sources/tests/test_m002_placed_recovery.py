"""Exact dual-input CDC representatives and closed-place continuation; no EDA."""
import ast
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from test_m002_physical_diagnostic import m, put, manifest, SCRIPTS
import test_m002_pre_place_recovery as prior_tests

REAL=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware')
SOURCE=REAL/'vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt'
ORIGINAL=REAL/'vivado/reports/m002_E002_R001_AT002_fresh_synth/cdc_post_synth.rpt'

class AuxRepresentatives(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.structure=m.reset_structure(SOURCE/'reset_graph_place.tsv')
        cls.fanout=m.reset_fanout(SOURCE/'cdc_changed_reset_place.tsv',SOURCE/'bram_port_clocks_place.tsv')
        cls.actual=m.cdc_critical_records(SOURCE/'cdc_place.rpt')
        cls.original=m.cdc_critical_records(ORIGINAL)
    def check(self,rows=None,structure=None,fanout=None):
        actual=self.actual if rows is None else rows
        original_reader=m.cdc_critical_records
        with patch.object(m,'ROOT',REAL),patch.object(m,'cdc_critical_records',side_effect=lambda p: actual if p==SOURCE/'cdc_place.rpt' else original_reader(p)):
            return m.critical_coverage(SOURCE/'cdc_place.rpt',ORIGINAL,self.structure if structure is None else structure,self.fanout if fanout is None else fanout)
    def test_actual_two_ddr1_representatives_and_canonical_both_admitted(self):
        v=self.check();self.assertEqual(len(v['actual_aux_representative_sources']),2);self.assertEqual(v['formal_reset_cdc_safety'],'OPEN')
        self.assertNotIn('actual_aux_representative_sources',self.check(m.opt_reset_cdc_rows()))
    def test_any_proven_aux_cone_may_report_either_actual_dual_source(self):
        rows=set()
        for row in m.opt_reset_cdc_rows():
            rows.add((*row[:3],row[3].replace('u_ready_cdc','u_base_reset_cdc'),row[4]) if '/syncstages_ff_reg[0]/D' in row[4] else row)
        self.assertEqual(len(self.check(rows)['actual_aux_representative_sources']),4)
    def test_additional_duplicate_cone_representative_and_ninth_row_rejected(self):
        extra=next(row for row in m.opt_reset_cdc_rows() if '/d1_smc/' in row[4])
        with self.assertRaisesRegex(ValueError,'duplicate AUX representatives'):self.check(self.actual|{extra})
    def test_unknown_source_clock_type_target_and_stage_rejected(self):
        row=next(row for row in self.actual if '/d1_smc/' in row[4])
        for index,value in [(0,'CDC-11'),(1,'wrong_UI'),(2,'other_dest'),(3,row[3].replace('[3]','[2]')),(3,row[3].replace('d1_gate','d0_gate')),(4,row[4].replace('[0]','[1]'))]:
            changed=list(row);changed[index]=value
            with self.subTest(index=index,value=value),self.assertRaisesRegex(ValueError,'new/unclassified'):self.check((self.actual-{row})|{tuple(changed)})
    def test_missing_row_and_changed_non_aux_rejected(self):
        row=next(row for row in self.actual if row[0]=='CDC-11')
        with self.assertRaisesRegex(ValueError,'new/unclassified'):self.check(self.actual-{row})
        changed=(*row[:3],row[3]+'wrong',row[4])
        with self.assertRaisesRegex(ValueError,'new/unclassified'):self.check((self.actual-{row})|{changed})
    def test_actual_dual_source_four_stage_chain_and_qualification_required(self):
        for kind in ('term','stage','chain','qualified','exports'):
            structure=copy.deepcopy(self.structure)
            if kind=='term':structure['aux_chains'][0]['source_synchronized_terms'].pop()
            if kind=='stage':structure['aux_chains'][0]['stages'].pop()
            if kind=='chain':structure['aux_chains'].pop()
            if kind=='qualified':structure['qualified']=False
            if kind=='exports':structure['explicit_primitive_exports'].pop()
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.check(structure=structure)
        with self.assertRaises(ValueError):self.check(fanout={'qualified':False})
    def test_missing_or_foreign_actual_graph_rejected(self):
        for change in ({'path':str(SOURCE/'reset_graph_physopt.tsv')},{'sha256':'0'*64}):
            structure=copy.deepcopy(self.structure);structure['source'].update(change)
            with self.assertRaises((ValueError,FileNotFoundError)):self.check(structure=structure)
    def test_classification_serialization_stable_across_hash_seeds(self):
        code="""import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import m002_physical_evidence as m
m.ROOT=Path(sys.argv[2]);p=Path(sys.argv[3]);g=json.loads((p/'reset_structure_place.json').read_text());f=json.loads((p/'integrity_place.json').read_text())['reset_fanout_observation']
print(json.dumps(m.critical_coverage(p/'cdc_place.rpt',m.ROOT/'vivado/reports/m002_E002_R001_AT002_fresh_synth/cdc_post_synth.rpt',g,f),sort_keys=True))
"""
        outputs=[subprocess.check_output([sys.executable,'-c',code,str(SCRIPTS),str(REAL),str(SOURCE)],env={**os.environ,'PYTHONHASHSEED':seed},text=True) for seed in ('1','2','3')]
        self.assertEqual(len(set(outputs)),1)
    def test_report_parser_rejects_duplicate_actual_row(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'cdc_place.rpt';text=(SOURCE/'cdc_place.rpt').read_text();line=next(x for x in text.splitlines() if 'Critical' in x and '/C' in x)
            p.write_text(text+'\n'+line+'\n')
            with self.assertRaisesRegex(ValueError,'duplicate'):m.cdc_critical_records(p)

class PlacedSourceAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.command=json.loads((SOURCE/'command.json').read_text());cls.attempt=Path(cls.command['managed_attempt'])
        cls.bound=m.input_manifest(cls.attempt/'closed_placed_source.sha256')
    def check(self,changed=None):
        native_read=Path.read_text;changed=changed or {}
        def read(path,*a,**kw):return changed[path] if path in changed else native_read(path,*a,**kw)
        with tempfile.TemporaryDirectory() as d,patch.object(m,'ROOT',REAL),patch.object(Path,'read_text',read),patch.object(m,'validate_stage_archive',return_value={}),patch.object(m,'restored_pre_place_evidence',return_value={'live_guard_command':m.file_id(SOURCE/'pre_place_restore_command_result.txt')}),patch.object(m,'input_manifest',return_value=self.bound):
            return m.recovery_placed_parent(SOURCE,Path(self.command['synthesis']['project']),self.command['synthesis'],Path(d))
    def test_natural_post_failure_retains_original_place_and_failed_post(self):
        v=self.check();self.assertEqual(v['phase'],'post_place_pre_physopt');self.assertFalse(v['physical_post_complete'])
        self.assertEqual(set(v['historical_command_receipts']),{'opt','debug_materialization','place'})
        self.assertEqual(v['source_original_POST_failure'],m.file_id(SOURCE/'integrity_place.json'))
    def test_abnormal_status_survivor_or_wall_stop_rejected(self):
        p=self.attempt/'status.json';status=json.loads(p.read_text())
        for changed in ({'exit_code':0},{'native_exit_code':-15},{'stop_reason':'resource_stop'},{'owned_survivors':[123]},{'wall_clock_stop_disabled':False}):
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'ended natural POST'):self.check({p:json.dumps({**status,**changed})})
    def test_native_place_nonzero_and_other_post_failure_rejected(self):
        p=SOURCE/'place_command_result.txt'
        with self.assertRaisesRegex(ValueError,'closed native place'):self.check({p:p.read_text().replace('native_tcl_code=0','native_tcl_code=1')})
        p=SOURCE/'integrity_place.json';v=json.loads(p.read_text());v['gate_issues']=['unrelated actual failure']
        with self.assertRaisesRegex(ValueError,'failure scope'):self.check({p:json.dumps(v)})
    def test_changed_dcp_completion_or_live_process_identity_rejected(self):
        p=self.attempt/'closed_placed_source_completion.json';v=json.loads(p.read_text())
        for change in ({'processes_gone':False},{'checkpoint':{**v['checkpoint'],'sha256':'0'*64}}):
            with self.assertRaisesRegex(ValueError,'closure changed|closed native place'):self.check({p:json.dumps({**v,**change})})

class PlacedLiveGuard(prior_tests.RestoredPrePlaceLiveGuard):
    # Keep inherited generic tests in their original class only.
    def setUp(self):
        super().setUp()
        self.parent.update(phase='post_place_pre_physopt',physical_point='place')
        self.parent['historical_command_receipts']['place']=m.file_id(put(self.source/'place_command','phase=place\ncommand=place_design\nnative_tcl_code=0\n'))
        put(self.report/'recovery_parent.json',json.dumps(self.parent))
        command=json.loads((self.report/'command.json').read_text());command['environment']['HAP_PHYSICAL_REPORT_DIR']=command['environment'].pop('HAP_PRE_PLACE_REPORT_DIR')
        put(self.report/'command.json',json.dumps(command));manifest(self.report/'stage_inputs.sha256',[self.report/'recovery_parent.json',Path(self.parent['checkpoint']['path']),self.scope,self.original])
        patch.object(m,'recovery_placed_parent',side_effect=lambda *a,**kw:self.parent).start()
    def check(self,create=True):return m.physical_resume_evidence(self.report,create=create)
    def test_physical_live_guard_and_original_pre_place_are_distinct(self):
        v=self.check();self.assertEqual(v['physical_point'],'place');self.assertEqual(v['inherited_pre_place'],self.parent['inherited_pre_place'])
        self.assertTrue(v['diagnostic_eligible']);self.assertEqual(v,self.check(create=False))
    def test_live_guard_changed_drc_or_clock_blocks(self):
        put(self.report/'pre_place_restore_guard.txt',self.guard.replace('drc_blockers=0','drc_blockers=1'))
        with self.assertRaisesRegex(ValueError,'native DRC/clock'):self.check()
    def test_final_and_route_parent_keep_only_fresh_physopt_receipt(self):
        # Scope serialization is separate from native POST collection/chronology.
        put(self.report/'integrity_place.json','fresh completed place POST scope fixture')
        with patch.object(m,'completed_placed_post'):
            value,project=prior_tests.RestoredPrePlaceLiveGuard.final_fixture(self)
            self.assertEqual(set(value['command_receipts']),{'physopt'})
            self.assertEqual(set(value['historical_command_receipts']),{'opt','debug_materialization','place'})
            self.assertEqual(value['pre_place'],self.parent['inherited_pre_place'])
            self.assertEqual(m.parent_recovered_place(self.report/'diagnostic_evidence.json',project,self.parent['synthesis'])['checkpoint'],value['checkpoint'])
            value['command_receipts']['place']=self.parent['historical_command_receipts']['place'];put(self.report/'diagnostic_evidence.json',json.dumps(value))
            with self.assertRaisesRegex(ValueError,'historical/new command scopes'):m.parent_recovered_place(self.report/'diagnostic_evidence.json',project,self.parent['synthesis'])
    def test_complete_post_is_required_before_independent_physopt(self):
        put(self.report/'place_result.txt','completed=1\ndiagnostic_eligible=1\n');put(self.report/'place.dcp','new actual POST checkpoint fixture')
        graph=put(self.report/'reset_graph_place.tsv');integrity={'phase':'place','gate_issues':[],'reset_structure':{'qualified':True,'source':m.file_id(graph)},'cdc_classification':{}}
        put(self.report/'integrity_place.json',json.dumps(integrity));put(self.report/'physopt_command_result.txt','started_epoch=3\n')
        log=f"Command: open_checkpoint {self.parent['checkpoint']['path']}\nM002_DIAGNOSTIC_STEP_COMPLETED place\nCommand: phys_opt_design\n"
        put(self.report/'vivado.log',log)
        with patch.object(m,'verify_reset_proof'),patch.object(m,'verify_cdc_proof'):
            m.completed_placed_post(self.report)
            put(self.report/'place_command_result.txt','repeated place')
            with self.assertRaisesRegex(ValueError,'place command repeated'):m.completed_placed_post(self.report)
            (self.report/'place_command_result.txt').unlink();put(self.report/'vivado.log',log.replace('M002_DIAGNOSTIC_STEP_COMPLETED place','missing'))
            with self.assertRaisesRegex(ValueError,'chronology'):m.completed_placed_post(self.report)
            put(self.report/'vivado.log',log);put(self.report/'place_result.txt','completed=0\ndiagnostic_eligible=0\n')
            with self.assertRaisesRegex(ValueError,'POST incomplete'):m.completed_placed_post(self.report)
    def test_fresh_post_then_physopt_order_without_place_opt_debug(self):
        text=(SCRIPTS/'m002_resume_physical.tcl').read_text();flow=text[text.index('if {$stage eq "place"} {'):text.index('m002_put [file join $report_dir implementation_checkpoint.sha256]')]
        for deny in (0,1):
            prefix=f'''set stage place
set ::env(HAP_RECOVERY_PHASE) post_place_pre_physopt
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
            rows=result.stdout.splitlines();self.assertEqual(rows[0],str(deny),result.stderr)
            self.assertEqual(rows[1],'pre_place_restore live_admission'+('' if deny else ' post_place physopt post_physopt'))
# Avoid inheriting tests written for a different checkpoint phase.
for name in list(prior_tests.RestoredPrePlaceLiveGuard.__dict__):
    if name.startswith('test_'):setattr(PlacedLiveGuard,name,None)

class ClosedSourceManifestIsolation(unittest.TestCase):
    def test_old_archive_is_bound_and_independently_verified_without_relabeling_as_new_code(self):
        text=(SCRIPTS/'run_m002_physical_stage.py').read_text()
        self.assertIn("'source_completion','source_post_manifest','source_original_POST_failure'",text)
        self.assertNotIn("identities += list(input_manifest(Path(inherited['source_post_manifest']['path'])))",text)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);report=root/'new';old=put(root/'old/stage_sources/same.py','old frozen code');current=put(root/'scripts/same.py','new execution code')
            archived=put(report/'stage_sources/same.py','new execution code')
            old_manifest=root/'old/closed.sha256';manifest(old_manifest,[old])
            manifest(report/'stage_inputs.sha256',[current,old_manifest]);manifest(report/'archived_sources.sha256',[archived])
            m.validate_stage_archive(report,m.file_id(report/'stage_inputs.sha256'),m.file_id(report/'archived_sources.sha256'))
            m.input_manifest(old_manifest)
            put(old,'tampered old archive')
            with self.assertRaisesRegex(ValueError,'changed input'):m.input_manifest(old_manifest)

class NoWallPolicy(unittest.TestCase):
    def test_no_budget_wall_or_no_output_stop_branch(self):
        text=(SCRIPTS/'run_m002_no_wall.py').read_text();tree=ast.parse(text)
        self.assertFalse(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='budget' for n in ast.walk(tree)))
        self.assertNotIn('stage_wall_timeout',text);self.assertNotIn('global_deadline =',text)
        for required in ('task_tree_rss_above_192GiB','system_mem_available_below_48GiB_for_30s','disk_free_below_30GiB','flock','17acf924'):
            self.assertIn(required,text)
    def test_real_isolated_process_exit_and_resource_receipt_for_both_stages(self):
        workspace=REAL.parent.parent
        for stage,rc in (('place',7),('route',0)):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as d:
                root=Path(d);hardware=root/'project/hardware';scripts=hardware/'vivado/scripts';scripts.mkdir(parents=True)
                for name in ('run_m002_no_wall.py','m002_execution_profile.py'):shutil.copy2(SCRIPTS/name,scripts/name)
                put(scripts/'run_m002_physical_stage.py',f'import time\ntime.sleep(0.15)\nraise SystemExit({rc})\n')
                for name in ('full_implementation_contract_2026-10-15.md','full_implementation_continuation_2026-10-15.md'):
                    src=workspace/'mission/M002_ddr_separation_and_timing_recovery'/name;dest=root/src.relative_to(workspace);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
                # Old wall anchor is deliberately far in the past; it must never stop this child.
                base=root/'project/E003_m002_full_implementation/experiment_results';put(base/'physical_budget_anchor.json','{"launched_utc":"2000-01-01T00:00:00+00:00"}')
                attempt=base/f'runs/{"R002" if stage=="place" else "R003"}/attempts/AT001_selftest';report=hardware/'vivado/reports/selftest';project=hardware/'vivado/project/selftest';project.mkdir(parents=True)
                result=subprocess.run([sys.executable,str(scripts/'run_m002_no_wall.py'),stage,'--attempt',str(attempt),'--report',str(report),'--project',str(project),'--execution-profile','m002_full_implementation'],text=True,capture_output=True,timeout=25)
                self.assertEqual(result.returncode,rc,result.stderr);v=json.loads((attempt/'status.json').read_text());self.assertIsNone(v['stop_reason']);self.assertEqual(v['native_exit_code'],rc)
                self.assertEqual(v['owned_survivors'],[]);self.assertTrue(v['wall_clock_stop_disabled']);self.assertIsNone(v['timeout_seconds']);self.assertTrue((attempt/'resources.jsonl').stat().st_size)

if __name__=='__main__':unittest.main()
