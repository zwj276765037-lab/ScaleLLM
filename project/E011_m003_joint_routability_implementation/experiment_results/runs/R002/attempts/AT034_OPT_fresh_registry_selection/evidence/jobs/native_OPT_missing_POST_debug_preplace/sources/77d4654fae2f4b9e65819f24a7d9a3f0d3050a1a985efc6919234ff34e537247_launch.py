"""Launch only the pinned actual-INIT recovery under the existing owned supervisor."""
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import native_init_recovery as recovery

def main():
    p = argparse.ArgumentParser(); p.add_argument('--package', type=Path, required=True)
    p.add_argument('--archive-source', action='append', default=[]); p.add_argument('--check-only', action='store_true')
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--qualified-init-evidence', type=Path); a = p.parse_args()
    value = recovery.verify(a.package)
    expected = {r['path'] for r in value['sources']} | {r['path'] for r in recovery.entry.check_sources()['sources']}
    recovery.old.require(set(a.archive_source) == expected, 'full48+4 runtime source archive arguments required')
    qualified = None
    if a.qualified_init_evidence:
        qualified = json.loads(a.qualified_init_evidence.read_text())
        recovery.old.require(a.qualified_init_evidence == Path(value['reuse_init']['target']) / 'offline_init_requalification.json'
            and qualified['schema'] == 'M003_actual_AT029_INIT_POST_requalified_v1' and qualified['completed'] is True
            and qualified['INIT_executed'] is False and qualified['snapshot_recollected'] is False
            and qualified['package'] == recovery.old.file_id(a.package)
            and qualified['checkpoint'] == value['checkpoint'], 'actual reused INIT POST lineage mismatch')
        for row in [*qualified['outputs'],qualified['source_archive'],qualified['stage_inputs']]: recovery.old.verify_identity(row)
    if a.check_only: print(json.dumps(dict(passed=True, frozen_core_sources=48, external_adapter_sources=4, new_EDA=False))); return 0
    report = Path(os.environ['HAP_REPORT_DIR']); report.mkdir()
    recovery.stage.prepare_sources(report, recovery.SYNTH_REPORT)
    rows = json.loads((report / 'source_archive.json').read_text()); paths = [Path(r['path']) for r in value['sources']] + [a.package]
    with (report / 'stage_inputs.sha256').open('a') as stream:
        for path in paths:
            ident = recovery.old.file_id(path); target = report / 'stage_sources' / (ident['sha256'] + '_' + path.name)
            shutil.copyfile(path, target); recovery.old.require(recovery.old.sha256(target) == ident['sha256'], 'adapter archive mismatch')
            rows.append(dict(original=ident, preserved=recovery.old.file_id(target))); stream.write(ident['sha256'] + '  ' + str(path) + '\n')
    (report / 'source_archive.json').write_text(json.dumps(rows, indent=2) + '\n')
    if qualified:
        recovery.archive_extra(report, [a.qualified_init_evidence] + [Path(r['path']) for r in qualified['outputs']]
                               + [Path(qualified[k]['path']) for k in ('source_archive','stage_inputs')])
        for row in qualified['outputs']:
            name = Path(row['path']).name
            if 'init' in name and name != 'M003_init_recovery_parent.json':
                shutil.copyfile(row['path'], report / name)
                recovery.old.require(recovery.old.sha256(report / name) == row['sha256'], 'qualified inherited INIT output changed')
        shutil.copyfile(value['checkpoint']['path'], report / 'init.dcp')
        recovery.save(report / 'INIT_POST_evidence_origin.json',dict(original_native_attempt='AT029',
            snapshot_recollected=False,INIT_executed=False,strict_offline_requalification=recovery.old.file_id(a.qualified_init_evidence)))
    if value.get('reuse_opt'):
        inherited = value['reuse_opt']
        recovery.archive_extra(report, [Path(row['path']) for row in inherited['artifacts']] + [Path(inherited['qualification']['path'])])
        for row in inherited['artifacts']:
            target = report / Path(row['path']).name
            shutil.copyfile(row['path'], target)
            recovery.old.require(recovery.old.sha256(target)==row['sha256'], 'inherited actual OPT artifact changed')
        shutil.copyfile(inherited['qualification']['path'], report/'m003_qualification_opt.json')
        recovery.save(report/'OPT_POST_evidence_origin.json', dict(original_native_attempt='AT031',
            native_opt_tcl_code=0, original_outer_native_exit_code=1, OPT_executed=False, snapshot_recollected=False,
            missing_POST_still_required=True, complete_POST_inherited=False, package=recovery.old.file_id(a.package)))
    recovery.save(report / 'M003_init_recovery_parent.json', dict(package=recovery.old.file_id(a.package), checkpoint=value['checkpoint'], INIT='inherited original AT028; not executed in this attempt', restored_phase=value.get('restored_phase','init'), OPT_executed=not bool(value.get('reuse_opt')), original_native_exit_code=1, new_synthesis=False))
    env = {**os.environ, 'HAP_M003_SCRIPTS_DIR':str(recovery.HW / 'vivado/scripts'), 'HAP_PROJECT_DIR':str(recovery.PROJECT),
           'HAP_SYNTH_REPORT_DIR':str(recovery.SYNTH_REPORT), 'HAP_SYNTH_ATTEMPT_DIR':str(recovery.SYNTH_AT),
           'HAP_M003_INIT_RECOVERY_PACKAGE':str(a.package), 'HAP_RECOVERY_CHECKPOINT':value['checkpoint']['path'],
           'HAP_RECOVERY_PARENT_REPORT':str(recovery.REPORT), 'HAP_EXECUTION_MODE':'checkpoint_restored_commands',
           'HAP_M003_RECOVERED_SYNTHESIS':'1', 'HAP_BOARD_CORE_CLK_MHZ':'100.0', 'HAP_BOARD_DDR_UI_CLK_HZ':'200000000'}
    if value.get('reuse_opt'): env['HAP_M003_QUALIFIED_OPT_SNAPSHOT'] = value['reuse_opt']['input_snapshot']['path']
    if qualified: env['HAP_M003_QUALIFIED_INIT_REPORT'] = str(a.qualified_init_evidence.parent)
    cmd = ['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado', '-mode','batch','-notrace','-source',str(HERE / 'recover_init.tcl'),'-log',str(report / 'vivado.log'),'-journal',str(report / 'vivado.jou')]
    # This exact path is exercised offline all the way to the native call boundary.
    manifest = recovery.old.manifest_records(report/'stage_inputs.sha256')
    archive = json.loads((report/'source_archive.json').read_text())
    for row in archive:
        recovery.old.verify_identity(row['original']); recovery.old.verify_identity(row['preserved'])
        recovery.old.require(manifest[Path(row['original']['path'])]==row['original']['sha256'], 'prepared archive/manifest mismatch')
    recovery.old.require(len(manifest)==len(archive), 'prepared archive/manifest coverage differs')
    parent = json.loads((report/'M003_init_recovery_parent.json').read_text())
    recovery.old.require(parent['package']==recovery.old.file_id(a.package) and parent['checkpoint']==value['checkpoint'], 'new parent receipt not bound to current package/checkpoint')
    if value.get('reuse_opt'):
        forbidden = [row for row in value['reuse_opt']['artifacts'] if Path(row['path']).name=='M003_init_recovery_parent.json']
        recovery.old.require(not forbidden and parent['restored_phase']=='opt' and parent['OPT_executed'] is False, 'old parent receipt selected or fresh OPT falsely claimed')
    recovery.save(report/'native_launch_preparation.json', dict(completed=True, native_executed=False,
        prepare_only=a.prepare_only, command=cmd, cwd=str(recovery.HW/'vivado'), package=recovery.old.file_id(a.package),
        checkpoint=value['checkpoint'], new_parent_receipt=recovery.old.file_id(report/'M003_init_recovery_parent.json'),
        source_archive=recovery.old.file_id(report/'source_archive.json'), stage_inputs=recovery.old.file_id(report/'stage_inputs.sha256'),
        archive_bindings=len(archive), inherited_artifacts=len(value.get('reuse_opt',{}).get('artifacts',[])),
        environment={k:v for k,v in env.items() if k.startswith('HAP_')}, exact_native_call_boundary=True))
    if a.prepare_only:
        print(json.dumps(dict(prepared=True, new_EDA=False, exact_native_call_boundary=True, archive_bindings=len(archive)))); return 0
    started = recovery.stage.now(); code = subprocess.run(cmd, cwd=recovery.HW / 'vivado', env=env).returncode
    recovery.save(report / 'launcher_status.json', dict(stage='qualify_recovered_native_'+value.get('restored_phase','init'), project=str(recovery.PROJECT), started_utc=started, ended_utc=recovery.stage.now(), native_exit_code=code, command=cmd, INIT_reexecuted=False, bitstream=None))
    return code
if __name__ == '__main__': sys.exit(main())
