"""Recheck real AT008 completed POST and recovery lineage; no new live EDA evidence."""
from pathlib import Path
import os, sys, json, shutil, datetime as dt
sys.dont_write_bytecode = True
at = Path(__file__).resolve().parent
sys.path.insert(0, str(at / 'source_archive'))
import m002_physical_evidence as m
workspace = at.parents[6]
hw = workspace / 'project/hardware'
m.ROOT = hw
reports = hw / 'vivado/reports'
source = reports / 'm002_E002_R003_AT008_complete_opt_gate_debug_place_physopt'
project = hw / 'vivado/project/m002_E002_R001_AT001_fresh'
synth = reports / 'm002_E002_R001_AT002_fresh_synth'
synth_at = at.parents[2] / 'R001/attempts/AT002_fresh_synth'
out = at / 'replayed_completed_debug_post'
out.mkdir()
for p in source.iterdir():
    if p.is_file() and p.suffix not in {'.dcp', '.jou'} and p.name not in {
            'vivado.log', 'implementation_run.log', 'launcher_status.txt',
            'integrity_debug_materialized.json', 'reset_structure_debug_materialized.json',
            'admission_debug_materialized.txt', 'pre_place_evidence.json'}:
        shutil.copy2(p, out / p.name)
identities = []
for p, digest in m.manifest_records(source / 'stage_inputs.sha256').items():
    archived = source / 'stage_sources' / p.name
    if archived.is_file() and m.sha256(archived) == digest:
        p = archived
    identities.append(p)
identities += [p for p in (at / 'source_archive').iterdir() if p.is_file()]
identities += [source / 'stage_inputs.sha256', at / 'archived_sources.sha256', Path(__file__)]
(out / 'stage_inputs.sha256').write_text(''.join(
    f'{m.sha256(p)}  {p}\n' for p in sorted(set(identities))))
os.environ.update(HAP_PROJECT_DIR=str(project), HAP_SYNTH_REPORT_DIR=str(synth),
                  HAP_SYNTH_ATTEMPT_DIR=str(synth_at),
                  HAP_EXECUTION_MODE='checkpoint_restored_commands', HAP_STAGE='place')
started = dt.datetime.now(dt.timezone.utc).isoformat()
m.hook_batch('debug_materialized', out)
value = json.loads((out / 'integrity_debug_materialized.json').read_text())
m.verify_cdc_proof(value['cdc_classification'])
m.verify_reset_proof(value['reset_structure'])
lineage = m.synth_lineage(project, synth, synth_at)
parent_out = at / 'actual_completed_pre_place_parent_final'
parent_out.mkdir()
parent = m.recovery_pre_place_parent(source, project, lineage, parent_out)
result = dict(
    verdict='PASS', started_utc=started, ended_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
    gate_issues=value['gate_issues'], actual_bram_ports=value['reset_fanout_observation']['bram_port_clock_endpoints'],
    actual_critical_CDC=value['cdc_classification']['classified_opt_reset'],
    actual_async_chains=len(value['reset_structure']['async_reset_chains']),
    actual_aux_chains=len(value['reset_structure']['aux_chains']),
    actual_host_split_chains=len(value['reset_structure']['host_split_reset_chains']),
    actual_primitive_exports=len(value['reset_structure']['explicit_primitive_exports']),
    source_scope='replay of original AT008 actual complete POST; no reports regenerated in original source',
    new_live_restore_guard='NOT_RUN; required in actual new Vivado restore before place',
    parent_phase=parent['phase'], original_debug_checkpoint=parent['checkpoint'],
    historical_command_receipts=parent['historical_command_receipts'],
    current_checker_archive=m.file_id(at / 'archived_sources.sha256'),
    original_pre_place=parent['inherited_pre_place'], original_post_manifest=parent['inherited_post_manifest'],
    replay_inputs=m.file_id(out / 'stage_inputs.sha256'),
    replay_integrity=m.file_id(out / 'integrity_debug_materialized.json'),
    actual_recovery_parent=m.file_id(parent_out / 'recovery_parent.json'),
    formal_reset_cdc_safety='OPEN', physical_signoff=False)
(at / 'actual_replay_status.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
