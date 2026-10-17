"""E005 fresh-project provenance fixtures; never run a hardware tool."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]/'vivado/scripts'
sys.path.insert(0, str(SCRIPTS))
import m002_physical_evidence as m
import m002_fresh_project_opt_recovery as fresh
import run_m002_physical_stage as runner


def put(path, body='fixture'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


class FreshPHY(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.attempt = self.root/'attempt'
        self.project = self.root/'project'
        self.report = self.root/'report'
        self.original = self.project/'scalellm_vcu118_f05.runs/impl_1/.Xil/Vivado-987654321-user/987654321'
        self.archive = self.attempt/'generated_phy_snapshot'
        self.repo = self.project/'scalellm_vcu118_f05.cache/ip'
        self.repo.mkdir(parents=True)
        self.modules = [f'scalellm_vcu118_f05_bd_ddr4_{d}_0_phy' for d in (1, 0)]
        assignments = dict(part='xcvu9p-flga2104-2L-e', board_part='xilinx.com:vcu118:part0:2.0',
            ip_vlnv='{xilinx.com:ip:ddr4_phy:2.2 xilinx.com:ip:ddr4_phy:2.2}',
            ip_module_name='{'+ ' '.join(self.modules)+'}',
            output_dcp='{\n'+'\n'.join(str(self.original/'out'/(name+'.0')/'result.dcp') for name in self.modules)+'\n}',
            output_xci='{\n'+'\n'.join(str(self.original/'out'/(name+'.0')/'result.xci') for name in self.modules)+'\n}',
            ip_output_repo=str(self.repo), ip_cache_permissions='disable')
        self.script = ''.join(f'set {key} {value}\n' for key, value in assignments.items())
        self.bodies = {self.original/'get_cs_ip.tcl': self.script}
        for d in (0, 1):
            name = f'scalellm_vcu118_f05_bd_ddr4_{d}_0_phy'
            self.bodies[self.original/(name+'.dcp')] = f'new PHY {d}'
            self.bodies[self.original/'out'/(name+'.0')/'result.dcp'] = f'new PHY {d}'
            self.bodies[self.original/f'phy{d}.xdc'] = f'worker constraint {d}'
            self.bodies[self.original/'out'/(name+'.0')/'main.xdc'] = f'generated main candidate {d}'
        self.refresh_log()
        put(self.attempt/'status.json', json.dumps(dict(project=str(self.project), report=str(self.report),
            exit_code=1, native_exit_code=1, stop_reason=None, owned_survivors=[], tracked_identities={'987654321': 1})))
        put(self.report/'command.json', json.dumps(dict(stage='place', execution_mode='project_runs',
            managed_attempt=str(self.attempt))))
        put(self.report/'implementation_run.log', ''.join(f'INFO: [IP_Flow 19-5647] Added synthesis output to IP cache for IP {name}, cache-ID = fixture\n' for name in self.modules))
        self.auth = dict(profile=m.full_impl.OPTIMIZED_PROFILE, stage='place', managed_attempt=str(self.attempt))
        self.patcher = patch.object(m.full_impl, 'report_authorization', return_value=self.auth)
        self.patcher.start(); self.addCleanup(self.patcher.stop)
        self.save()

    def refresh_log(self):
        self.bodies[self.original/'get_cs_ip.tcl'] = self.script
        trace = ''.join('# '+line+'\n' for line in self.script.splitlines())
        self.bodies[self.original/'vivado.log'] = trace+''.join(
            f'DBG: no cache hit, so run synth\nParsing XDC File [{self.original/f"phy{d}.xdc"}]\nsynth_design completed successfully\n'
            for d in (0, 1))+'Exiting Vivado\n'

    def save(self):
        files = []
        for source, body in self.bodies.items():
            copy = put(self.archive/source.relative_to(self.original), body)
            files.append(dict(source_path=str(source), **m.file_id(copy)))
        put(self.attempt/'generated_phy_evidence.json', json.dumps(dict(source_root=str(self.original),
            archive_root=str(self.archive), cache_miss_count=2, actual_synth_success_count=2, files=files)))
        put(self.attempt/'generated_phy_snapshot.sha256', ''.join(f"{row['sha256']}  {row['path']}\n" for row in files))

    def check(self):
        return m.generated_phy_parent(self.attempt, fresh_project=self.project, create_terminal_observation=True)

    def test_complete_disabled_cache_new_pair(self):
        result = self.check()
        self.assertEqual(result['fresh_disabled_cache_qualification']['cache_permissions'], 'disable')
        for pair in result['outputs'].values():
            self.assertEqual(set(pair), {'produced', 'output'})
            self.assertEqual(pair['produced']['sha256'], pair['output']['sha256'])

    def test_legacy_still_requires_third_copy(self):
        with self.assertRaisesRegex(ValueError, 'post-synthesis cache bytes differ'):
            m.generated_phy_parent(self.attempt)

    def test_duplicate_permission_assignment_rejected(self):
        self.script += 'set ip_cache_permissions disable\n'; self.refresh_log(); self.save()
        with self.assertRaisesRegex(ValueError, 'assignment missing or repeated'):
            self.check()

    def test_module_assignment_cannot_hide_behind_name_elsewhere(self):
        self.script = self.script.replace('set ip_module_name {', 'set ip_module_name {foreign ')
        self.refresh_log(); self.save()
        with self.assertRaisesRegex(ValueError, 'assignment differs: ip_module_name'):
            self.check()

    def test_output_dcp_order_rejected(self):
        old = fresh.literal_assignment(m, self.script, 'output_dcp')
        self.script = self.script.replace('\n'.join(old), '\n'.join(reversed(old)))
        self.refresh_log(); self.save()
        with self.assertRaisesRegex(ValueError, 'assignment differs: output_dcp'):
            self.check()

    def test_foreign_board_rejected(self):
        self.script = self.script.replace('xilinx.com:vcu118:part0:2.0', 'xilinx.com:foreign:part0:2.0')
        self.refresh_log(); self.save()
        with self.assertRaisesRegex(ValueError, 'assignment differs: board_part'):
            self.check()

    def test_substituted_repo_rejected(self):
        self.script = self.script.replace('set ip_output_repo '+str(self.repo), 'set ip_output_repo $foreign')
        self.refresh_log(); self.save()
        with self.assertRaisesRegex(ValueError, 'executable substitution'):
            self.check()

    def test_actual_cache_copy_rejected_by_new_branch(self):
        put(self.repo/'unknown'/ (self.modules[0]+'.dcp'))
        with self.assertRaisesRegex(ValueError, 'unexpected declared-repo third'):
            self.check()

    def test_result_byte_difference_rejected(self):
        name = self.modules[0]
        self.bodies[self.original/'out'/(name+'.0')/'result.dcp'] = 'foreign PHY bytes'
        self.save()
        with self.assertRaisesRegex(ValueError, 'produced/result PHY mismatch'):
            self.check()

    def test_original_repo_observation_stays_fixed(self):
        original = self.check()
        put(self.repo/'later_unrelated.txt', 'unrelated later metadata')
        self.assertEqual(original, self.check())

    def test_source_attempt_mismatch_rejected(self):
        self.auth['managed_attempt'] = str(self.root/'other_attempt')
        with self.assertRaisesRegex(ValueError, 'genuine failed E005 fresh project'):
            self.check()

    def test_main_cache_message_is_not_erased(self):
        put(self.report/'implementation_run.log', 'no cache message\n')
        with self.assertRaisesRegex(ValueError, 'main-log cache dispositions'):
            self.check()

    def test_read_only_missing_observation_is_not_rebuilt(self):
        with self.assertRaisesRegex(ValueError, 'repository observation is missing'):
            m.generated_phy_parent(self.attempt, fresh_project=self.project)
        self.assertFalse((self.attempt/'generated_phy_terminal_repository_observation.json').exists())


class Directives(unittest.TestCase):
    def test_e005_explicit_and_legacy_unchanged(self):
        auth = dict(profile=m.full_impl.OPTIMIZED_PROFILE)
        self.assertEqual(fresh.expected_physical_command('place', 'place_design', auth),
                         'place_design -directive SSI_SpreadSLLs')
        self.assertEqual(fresh.expected_physical_command('route', 'route_design', auth),
                         'route_design -directive Default')
        self.assertEqual(fresh.expected_physical_command('physopt', 'phys_opt_design', None), 'phys_opt_design')


class TransitiveArchive(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.report=self.root/'new_report'
        self.old=put(self.root/'old_report/stage_sources/same.py', 'immutable earlier code')
        self.current=put(self.root/'scripts/same.py', 'new current code')
        self.archive=put(self.report/'stage_sources/same.py', 'new current code')
        put(self.report/'stage_inputs.sha256', ''.join(f'{m.sha256(p)}  {p}\n' for p in [self.current,self.old]))
        put(self.report/'archived_sources.sha256', f'{m.sha256(self.archive)}  {self.archive}\n')

    def check(self):
        return m.validate_stage_archive(self.report,m.file_id(self.report/'stage_inputs.sha256'),
                                        m.file_id(self.report/'archived_sources.sha256'))

    def test_same_basename_previous_archive_keeps_own_bytes(self):
        self.assertEqual(self.check()[self.old], m.sha256(self.old))

    def test_changed_previous_archive_is_not_masked_by_new_code(self):
        put(self.old, 'new current code')
        with self.assertRaisesRegex(ValueError, 'design/probe input changed'):
            self.check()


class CurrentCDCProbe(unittest.TestCase):
    def setUp(self):
        self.parent = dict(phase='post_opt_pre_debug', opt_evidence_complete=False,
            opt_execution_proof_kind='native_project_log_derived', opt_reports_complete=True,
            inherited_reports={'cdc_opt.rpt':dict(path='/fresh/current/cdc_opt.rpt')})

    def test_bound_new_report_supplies_actual_probe_sources(self):
        self.assertEqual(runner.critical_probe_report('place', True, self.parent, None), Path('/fresh/current/cdc_opt.rpt'))

    def test_incomplete_report_cannot_supply_new_probe_sources(self):
        self.parent['opt_reports_complete'] = False
        self.assertIsNone(runner.critical_probe_report('place', True, self.parent, None))

    def test_foreign_proof_kind_cannot_supply_new_probe_sources(self):
        self.parent['opt_execution_proof_kind'] = 'foreign'
        self.assertIsNone(runner.critical_probe_report('place', True, self.parent, None))


class NativeOPT(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.hardware = self.root/'hardware'
        self.source = self.hardware/'vivado/reports/original'
        self.project = self.hardware/'vivado/project/fresh'
        self.attempt = self.root/'attempt'
        self.report = self.hardware/'vivado/reports/continuation'
        self.report.mkdir(parents=True)
        self.lineage = dict(project=str(self.project), source_rows=342, checkpoint_paths=45)
        self.auth = dict(profile=m.full_impl.OPTIMIZED_PROFILE, stage='place', managed_attempt=str(self.attempt))
        self.patches = [patch.object(m, 'ROOT', self.hardware),
            patch.object(m.full_impl, 'report_authorization', return_value=self.auth),
            patch.object(m, 'generated_phy_parent', return_value=dict(main_generated_xdc_candidates={})),
            patch.object(m, 'generated_debug_parent', return_value=dict(main_generated_xdc_candidates={}))]
        for p in self.patches:
            p.start(); self.addCleanup(p.stop)
        put(self.source/'command.json', json.dumps(dict(stage='place', execution_mode='project_runs',
            managed_attempt=str(self.attempt), synthesis=self.lineage)))
        manager = dict(stage='place', project=str(self.project), report=str(self.source),
                       execution_profile=m.full_impl.OPTIMIZED_PROFILE, started_utc='2026-10-16T02:00:00+00:00')
        started = dict(**manager, supervisor_pid=987654320, leader_pid=987654321, process_group=987654321)
        status = dict(**started, exit_code=1, native_exit_code=1, stop_reason=None,
                      tracked_identities={'987654321': 1}, owned_survivors=[], owned_before_reap=[])
        put(self.attempt/'command.json', json.dumps(manager))
        put(self.attempt/'started.json', json.dumps(started))
        put(self.attempt/'status.json', json.dumps(status))
        put(self.source/'launcher_status.txt', f'stage=place\nexit_code=1\nnative_exit_code=1\nproject={self.project}\nreports={self.source}\n')
        put(self.source/'init_result.txt', 'completed=1\nphase=init\n')
        put(self.source/'opt_result.txt', 'completed=0\nphase=opt\nblackboxes=1\n')
        put(self.source/'implementation_settings.txt', 'STEPS.PLACE_DESIGN.ARGS.DIRECTIVE=SSI_SpreadSLLs\nSTEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE=Default\nSTEPS.ROUTE_DESIGN.ARGS.DIRECTIVE=Default\n')
        source_script = put(self.hardware/'vivado/scripts/native_fixture.py')
        archived_script = put(self.source/'stage_sources/native_fixture.py')
        put(self.source/'stage_inputs.sha256', f'{m.sha256(source_script)}  {source_script}\n')
        put(self.source/'archived_sources.sha256', f'{m.sha256(archived_script)}  {archived_script}\n')
        frozen_rows = [m.file_id(put(self.hardware/'fixture_design'/f'{n}.v', f'input {n}')) for n in range(142)]
        frozen_path = put(self.root/'E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_physical.json',
                          json.dumps(dict(files=frozen_rows)))
        self.freeze_patch = patch.object(fresh, 'FROZEN_SHA', m.sha256(frozen_path))
        self.freeze_patch.start(); self.addCleanup(self.freeze_patch.stop)
        self.xdc = [put(self.project/'fixture_constraints'/f'{n}.xdc', f'constraint {n}') for n in range(162)]
        self.metadata = {str(p):['implementation','0','1','1','','','NORMAL'] for p in self.xdc}
        self.hashes = {str(p):m.sha256(p) for p in self.xdc}
        registry = put(self.source/'xdc_registry_opt_hashed.tsv', 'header\n'+''.join(
            '\t'.join([str(p), *self.metadata[str(p)], self.hashes[str(p)]])+'\n' for p in self.xdc))
        project_constraints = put(self.source/'constraints_project.json', json.dumps(dict(metadata=self.metadata, hashes=self.hashes)))
        init_constraints = put(self.source/'constraints_init.json', json.dumps(dict(phase='init', parent=m.file_id(project_constraints))))
        self.log = ''.join(f"Parsing XDC File [{p}] for cell 'instance{n}'\n" for n,p in enumerate(self.xdc))
        self.log += f"Command: opt_design\nopt_design completed successfully\nsource {self.hardware/'vivado/scripts/m002_diagnostic_opt_post.tcl'}\nThe checkpoint '{self.source/'opt.dcp'}' has been generated\n{fresh.GUARD}\n"
        put(self.source/'implementation_run.log', self.log)
        actual = [dict(line=n+1, path=str(p), scope=f'instance{n}', sha256=self.hashes[str(p)]) for n,p in enumerate(self.xdc)]
        reads = put(self.source/'actual_xdc_reads_opt.json', json.dumps(dict(records=actual)))
        put(self.source/'constraints_opt.json', json.dumps(dict(phase='opt', parent=m.file_id(init_constraints),
            registry=m.file_id(registry), actual_reads=m.file_id(reads), metadata=self.metadata, hashes=self.hashes)))
        put(self.source/'native_run_receipts/scalellm_vcu118_f05_bd_wrapper.tcl',
            f'  opt_design\n  source {self.hardware/"vivado/scripts/m002_diagnostic_opt_post.tcl"}\nstep_failed opt_design\nreturn -code error\n')
        put(self.source/'native_run_receipts/.opt_design.error.rst', '')
        checkpoint = self.source/'opt.dcp'
        with zipfile.ZipFile(checkpoint, 'w') as z:
            z.writestr('dcp.xml', '<Checkpoint>'+''.join(f'<{key} Name="{value}"/>' for key,value in {
                'Part':'xcvu9p-flga2104-2L-e','Top':'scalellm_vcu118_f05_bd_wrapper',
                'BoardPart':'xilinx.com:vcu118:part0:2.0','BUILD_NUMBER':'6299465','PRODUCT':'Vivado v2025.2 (64-bit)'}.items())+'</Checkpoint>')
        for name in ('timing_opt.rpt','utilization_opt.rpt','drc_opt.rpt','check_timing_opt.rpt','clocks_opt.rpt',
                     'cdc_opt.rpt','clock_interaction_opt.rpt','exceptions_opt.rpt','pulse_width_opt.rpt','bus_skew_opt.rpt',
                     'reset_cdc_and_io_probe_opt.tsv','xpm_invalid_endpoint_probe_opt.tsv','head_wave_local_opt.tsv'):
            put(self.source/name)

    def check(self, write=True):
        return fresh.qualify_native_project(m, self.source, self.project, self.lineage, self.report, write=write)

    def mutate_reads(self, change):
        p = self.source/'actual_xdc_reads_opt.json'; value=json.loads(p.read_text()); change(value['records']); put(p,json.dumps(value))
        c = self.source/'constraints_opt.json'; value=json.loads(c.read_text()); value['actual_reads']=m.file_id(p); put(c,json.dumps(value))

    def test_real_command_success_failed_POST_stays_separate(self):
        value = self.check()
        self.assertFalse(value['opt_evidence_complete'])
        self.assertTrue(value['opt_reports_complete'])
        self.assertFalse((self.source/'opt_command_result.txt').exists())
        self.assertFalse((self.report/'opt_command_result.txt').exists())
        self.assertEqual(value, self.check(write=False))

    def test_deleted_constraint_read_cannot_pass_updated_identity(self):
        self.mutate_reads(lambda rows: rows.pop())
        with self.assertRaisesRegex(ValueError, 'actual constraint records'):
            self.check()

    def test_wrong_constraint_scope_cannot_pass_updated_identity(self):
        self.mutate_reads(lambda rows: rows[0].update(scope='foreign_instance'))
        with self.assertRaisesRegex(ValueError, 'actual constraint records'):
            self.check()

    def test_missing_opt_success_rejected(self):
        put(self.source/'implementation_run.log', self.log.replace('opt_design completed successfully', 'failure'))
        with self.assertRaisesRegex(ValueError, 'chronology'):
            self.check()

    def test_fake_original_receipt_rejected(self):
        put(self.source/'opt_command_result.txt', 'command=opt_design\nnative_tcl_code=0\n')
        with self.assertRaisesRegex(ValueError, 'synthetic success artifacts'):
            self.check()

    def test_actual_later_debug_execution_rejected(self):
        put(self.source/'implementation_run.log', self.log+'Command: implement_debug_core\n')
        with self.assertRaisesRegex(ValueError, 'chronology'):
            self.check()

    def test_wrong_authorized_attempt_rejected(self):
        self.auth['managed_attempt'] = str(self.root/'other')
        with self.assertRaisesRegex(ValueError, 'without configured stop'):
            self.check()

    def test_started_leader_mismatch_rejected(self):
        p=self.attempt/'started.json';value=json.loads(p.read_text());value['leader_pid']=123;put(p,json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'command/started/status chain'):
            self.check()

    def test_read_only_validation_cannot_rebuild_missing_terminal_observation(self):
        with self.assertRaisesRegex(ValueError, 'terminal identity observation is missing'):
            self.check(write=False)
        self.assertFalse((self.attempt/'native_project_opt_terminal_identity_observation.json').exists())

    def test_configured_stop_rejected(self):
        p=self.attempt/'status.json';value=json.loads(p.read_text());value['stop_reason']='resource_limit';put(p,json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'without configured stop'):
            self.check()

    def test_native_OPT_success_receipt_not_invented(self):
        put(self.source/'native_run_receipts/.opt_design.end.rst', '')
        with self.assertRaisesRegex(ValueError, 'generated native Tcl/error receipt'):
            self.check()

    def make_restored(self):
        original = self.check()
        restored = self.report
        attempt = self.root/'restored_attempt'
        authorization = dict(profile=m.full_impl.OPTIMIZED_PROFILE, stage='place', managed_attempt=str(attempt))
        m.full_impl.report_authorization.side_effect = lambda report: self.auth if report == self.source else authorization
        manager = dict(stage='place', project=str(self.project), report=str(restored),
                       execution_profile=m.full_impl.OPTIMIZED_PROFILE, started_utc='2026-10-16T03:00:00+00:00')
        started = dict(**manager, supervisor_pid=987654322, leader_pid=987654323, process_group=987654323)
        put(attempt/'command.json', json.dumps(manager)); put(attempt/'started.json', json.dumps(started))
        put(attempt/'status.json', json.dumps(dict(**started, exit_code=1, native_exit_code=1,
            stop_reason=None, owned_survivors=[], tracked_identities={'987654323': 1})))
        put(restored/'command.json', json.dumps(dict(stage='place', managed_attempt=str(attempt),
            synthesis=self.lineage, execution_mode='checkpoint_restored_commands', environment={'HAP_OPT_REPORT_DIR': str(self.source)})))
        put(restored/'launcher_status.txt', f'stage=place\nexit_code=1\nnative_exit_code=1\nproject={self.project}\nreports={restored}\n')
        put(restored/'implementation_run.log', f"Command: open_checkpoint {original['checkpoint']['path']}\nfailed OPT POST\n")
        put(restored/'opt_result.txt', 'completed=0\nphase=opt\nevidence_origin=inherited_identical_opt_checkpoint\n')
        put(restored/'constraints_opt.json', json.dumps(dict(mode='embedded_checkpoint_inherited',
            candidate_metadata=original['source_metadata'], hashes=original['hashes'], source_archives={})))
        shutil.copy2(self.source/'opt.dcp', restored/'opt.dcp')
        for name, identity in original['inherited_reports'].items():
            shutil.copy2(Path(identity['path']), restored/name)
        for name in ('implementation_settings.txt','xdc_registry_opt_hashed.tsv'):
            shutil.copy2(self.source/name, restored/name)
        code = put(self.hardware/'vivado/scripts/restored_fixture.py')
        archive = put(restored/'stage_sources/restored_fixture.py')
        put(restored/'stage_inputs.sha256', f'{m.sha256(code)}  {code}\n')
        put(restored/'archived_sources.sha256', f'{m.sha256(archive)}  {archive}\n')
        target = self.hardware/'vivado/reports/second_continuation'; target.mkdir()
        return restored, target

    def test_failed_identical_restored_OPT_POST_can_continue_without_command_replay(self):
        source, target = self.make_restored()
        value = fresh.qualify_restored_opt(m, source, self.project, self.lineage, target)
        self.assertEqual(value['opt_execution_proof_kind'], 'native_project_log_derived')
        self.assertFalse(value['opt_evidence_complete'])
        self.assertFalse((target/'opt_command_result.txt').exists())

    def test_later_debug_checkpoint_requires_its_own_continuation(self):
        source, target = self.make_restored()
        put(source/'debug_materialized.dcp', 'later completed step')
        with self.assertRaisesRegex(ValueError, 'later executed-command evidence'):
            fresh.qualify_restored_opt(m, source, self.project, self.lineage, target)

    def test_restored_OPT_report_modification_rejected(self):
        source, target = self.make_restored()
        put(source/'cdc_opt.rpt', 'foreign report')
        with self.assertRaisesRegex(ValueError, 'copied reports differ'):
            fresh.qualify_restored_opt(m, source, self.project, self.lineage, target)

    def test_restored_OPT_cannot_hide_replayed_OPT_command(self):
        source, target = self.make_restored()
        p=source/'implementation_run.log'; put(p, p.read_text()+'Command: opt_design\n')
        with self.assertRaisesRegex(ValueError, 'new transformation or later command'):
            fresh.qualify_restored_opt(m, source, self.project, self.lineage, target)


class CurrentTargetedCDC(unittest.TestCase):
    def setUp(self):
        self.fixture = NativeOPT(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.old = self.fixture.source
        self.write_report(self.old/'cdc_opt.rpt', m.opt_reset_cdc_rows())
        self.source, self.target = self.fixture.make_restored()
        self.raw = self.source/'cdc_changed_reset_opt.tsv'
        pairs = sorted({row[1:3] for row in m.opt_reset_cdc_rows()})
        lines = []
        for i, ((source,target),count) in enumerate(zip(pairs,(668,668,768,769))):
            name = f'm002_changed_reset_opt_{i}'
            report = self.source/f'cdc_changed_opt_{i}.rpt'
            command = f'report_cdc -from {source} -to {target} -severity Critical -all_checks_per_endpoint -details -name {name} -file {report}'
            lines += [f'TARGETED_CDC_COMMAND\t{source}\t{target}\t{command}',
                      f'TARGETED_CDC_VIOLATION_COUNT\t{source}\t{target}\t{count}\tLIMIT=64',
                      f'TARGETED_CDC_VIOLATIONS_UNKNOWN\t{name}']
            self.write_report(report, {row for row in m.opt_reset_cdc_rows() if row[1:3] == (source,target)}, (source,target,i))
        put(self.raw,'\n'.join(lines)+'\n')
        for name in ('reset_graph_opt.tsv','bram_port_clocks_opt.tsv'):
            put(self.source/name)
        c = self.source/'command.json'; value=json.loads(c.read_text())
        value['environment'].update(HAP_RECOVERY_PHASE='post_opt_pre_debug',HAP_RECOVERY_OPT_LOG_DERIVED='1',HAP_SYNTH_REPORT_DIR=str(self.fixture.root/'synth'))
        put(c,json.dumps(value))
        put(self.source/'integrity_opt.json',json.dumps(dict(phase='opt',synthesis=self.fixture.lineage,
            constraints=m.file_id(self.source/'constraints_opt.json'),
            gate_issues=['critical_CDC: ValueError: exact OPT reset CDC requires actual chain/polarity/HostSplit/fanout diagnostic proof'])))
        with (self.source/'stage_inputs.sha256').open('a') as inputs, (self.source/'archived_sources.sha256').open('a') as archive:
            for name in ('m002_diagnostic_common.tcl','m002_resume_physical.tcl','probe_targets.tcl'):
                original = self.source/name if name=='probe_targets.tcl' else self.fixture.hardware/'vivado/scripts'/name
                body = 'set ::m002_actual_critical_clock_pairs {}' if name=='probe_targets.tcl' else (SCRIPTS/name).read_text()
                put(original,body); retained=put(self.source/'stage_sources'/name,body)
                inputs.write(f'{m.sha256(original)}  {original}\n');archive.write(f'{m.sha256(retained)}  {retained}\n')

    @staticmethod
    def write_report(path, rows, pair=None):
        from collections import Counter
        rows=sorted(rows);counts=Counter(row[0] for row in rows)
        body=[]
        if pair:
            source,target,i=pair
            command=f'report_cdc -from [get_clocks -quiet {source}] -to [get_clocks -quiet {target}] -severity Critical -all_checks_per_endpoint -details -name m002_changed_reset_opt_{i} -file {path}'
            body += ['| Tool Version : Vivado v.2025.2 (lin64) Build 6299465 fixture',
                     '| Design : scalellm_vcu118_f05_bd_wrapper','| Device : xcvu9p-flga2104',
                     '| Design State : Optimized','| Command : '+command]
        body += ['CDC Report']+[f'{k} Critical {n} description' for k,n in sorted(counts.items())]
        for i,(kind,source,target,start,end) in enumerate(rows,1):
            body += [f'Source Clock: {source}',f'Destination Clock: {target}',
                     f'{i}  {kind}  Critical  description  {start}  {end}']
        return put(path,'\n'.join(body)+'\n')

    def check(self,write=True):
        return fresh.qualify_targeted_cdc_reports(m,self.source,write=write)

    def test_complete_current_reports_keep_raw_cap_and_legacy_hashes(self):
        legacy=m.TARGETED_OPT_REPORT_HASHES
        value=self.check();actual=m.auxiliary_cdc_limits(self.raw)
        self.assertEqual(actual['critical_rows'],8)
        self.assertEqual(actual['object_counts'],[668,668,768,769])
        self.assertEqual(actual['coverage'],'coverage_limited')
        self.assertEqual(len(actual['raw_sentinels']),4)
        self.assertEqual(value['formal_reset_cdc_safety'],'OPEN')
        self.assertEqual(m.TARGETED_OPT_REPORT_HASHES,legacy)

    def test_new_report_without_binding_cannot_use_legacy_branch(self):
        with self.assertRaisesRegex(ValueError,'complete report identity changed'):
            m.auxiliary_cdc_limits(self.raw)

    def test_read_only_cannot_create_receipt(self):
        with self.assertRaisesRegex(ValueError,'fixed binding is missing'):self.check(False)
        self.assertFalse((self.source/fresh.TARGETED_RECEIPT).exists())

    def test_changed_report_after_binding_rejected(self):
        self.check();p=self.source/'cdc_changed_opt_0.rpt';put(p,p.read_text()+'changed\n')
        with self.assertRaisesRegex(ValueError,'binding identity changed'):self.check(False)

    def test_missing_report_rejected(self):
        (self.source/'cdc_changed_opt_1.rpt').unlink()
        with self.assertRaises((ValueError,FileNotFoundError)):self.check()

    def test_wrong_report_command_rejected(self):
        p=self.source/'cdc_changed_opt_0.rpt';put(p,p.read_text().replace('-severity Critical','-severity Warning'))
        with self.assertRaisesRegex(ValueError,'Command header mismatch'):self.check()

    def test_wrong_report_name_rejected(self):
        p=self.source/'cdc_changed_opt_0.rpt';put(p,p.read_text().replace('m002_changed_reset_opt_0','foreign_name'))
        with self.assertRaisesRegex(ValueError,'Command header mismatch'):self.check()

    def test_wrong_report_pair_rejected(self):
        p=self.source/'cdc_changed_opt_0.rpt';put(p,p.read_text().replace('[get_clocks -quiet mmcm_clkout0]','[get_clocks -quiet foreign]'))
        with self.assertRaisesRegex(ValueError,'Command header mismatch'):self.check()

    def test_wrong_phase_rejected(self):
        p=self.source/'command.json';v=json.loads(p.read_text());v['environment']['HAP_RECOVERY_PHASE']='post_debug_pre_place';put(p,json.dumps(v))
        with self.assertRaisesRegex(ValueError,'actual restored OPT phase'):self.check()

    def test_wrong_tool_rejected(self):
        p=self.source/'cdc_changed_opt_0.rpt';put(p,p.read_text().replace('Build 6299465','Build 1'))
        with self.assertRaisesRegex(ValueError,'tool header mismatch'):self.check()

    def test_wrong_design_state_rejected(self):
        p=self.source/'cdc_changed_opt_0.rpt';put(p,p.read_text().replace('Optimized','Placed'))
        with self.assertRaisesRegex(ValueError,'Design State header mismatch'):self.check()

    def test_raw_count_must_remain_measured(self):
        put(self.raw,self.raw.read_text().replace('\t668\tLIMIT=64','\t667\tLIMIT=64',1))
        with self.assertRaisesRegex(ValueError,'command/name/clock/count mismatch'):self.check()

    def test_unknown_critical_tuple_rejected(self):
        p=self.source/'cdc_changed_opt_0.rpt';put(p,p.read_text().replace('calDone_gated_reg/C','foreign_reg/C'))
        with self.assertRaisesRegex(ValueError,'critical tuples changed'):self.check()

    def test_additional_critical_tuple_rejected(self):
        p=self.source/'cdc_changed_opt_0.rpt';s=p.read_text();put(p,s.replace('CDC-10 Critical 3','CDC-10 Critical 4')+'4  CDC-10  Critical  description  foreign/C  foreign/D\n')
        with self.assertRaisesRegex(ValueError,'critical tuples changed'):self.check()

    def test_full_report_changed_even_with_same_semantics_rejected(self):
        p=self.source/'cdc_opt.rpt';put(p,p.read_text()+'changed full identity\n')
        with self.assertRaisesRegex(ValueError,'copied reports differ'):self.check()

    def test_incomplete_full_union_rejected(self):
        rows=set(m.opt_reset_cdc_rows());rows.pop()
        for directory in (self.old,self.source):self.write_report(directory/'cdc_opt.rpt',rows)
        with self.assertRaisesRegex(ValueError,'tuple union mismatch'):self.check()

    def test_changed_dcp_rejected(self):
        put(self.source/'opt.dcp','changed')
        with self.assertRaisesRegex(ValueError,'checkpoint bytes transformed'):self.check()

    def test_changed_constraints_rejected(self):
        p=self.source/'constraints_opt.json';v=json.loads(p.read_text());v['hashes']={};put(p,json.dumps(v))
        with self.assertRaisesRegex(ValueError,'constraints changed'):self.check()

    def test_changed_producer_archive_rejected(self):
        put(self.source/'stage_sources/m002_diagnostic_common.tcl','changed producer')
        with self.assertRaisesRegex(ValueError,'changed input'):self.check()

    def test_missing_producer_binding_rejected(self):
        p=self.source/'stage_inputs.sha256';put(p,''.join(row+'\n' for row in p.read_text().splitlines() if not row.endswith('/m002_diagnostic_common.tcl')))
        with self.assertRaisesRegex(ValueError,'producer source is not archived/bound'):self.check()

    def test_changed_raw_graph_after_binding_rejected(self):
        self.check();put(self.source/'reset_graph_opt.tsv','changed graph')
        with self.assertRaisesRegex(ValueError,'binding identity changed'):self.check(False)


if __name__ == '__main__':
    unittest.main()
