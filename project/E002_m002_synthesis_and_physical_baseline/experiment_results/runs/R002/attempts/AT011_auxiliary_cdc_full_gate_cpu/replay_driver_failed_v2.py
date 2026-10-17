"""Replay the complete actual OPT hook with preserved sources after live installation."""
from pathlib import Path
import os,sys,json,shutil
at=Path(__file__).resolve().parent
sys.path.insert(0,str(at/'source_archive'))
import m002_physical_evidence as m
workspace=at.parents[6]
hw=workspace/'project/hardware';m.ROOT=hw
reports=hw/'vivado/reports';source=reports/'m002_E002_R003_AT007_bram_port_clock_debug_place_physopt'
out=at/'replayed_complete_opt_gate_v2';out.mkdir()
for p in source.iterdir():
    if p.is_file() and p.name not in {'opt.dcp','integrity_opt.json','reset_structure_opt.json','admission_opt.txt','launcher_status.txt','vivado.log','implementation_run.log','vivado.jou'}:shutil.copy2(p,out/p.name)
identities=[]
for p,digest in m.manifest_records(source/'stage_inputs.sha256').items():
    archived=source/'stage_sources'/p.name
    if archived.is_file() and m.sha256(archived)==digest:p=archived
    identities.append(p)
identities += list((at/'source_archive').iterdir())+[source/'stage_inputs.sha256',Path(__file__)]
(out/'stage_inputs.sha256').write_text(''.join(f'{m.sha256(p)}  {p}\n' for p in sorted(set(identities))))
project=hw/'vivado/project/m002_E002_R001_AT001_fresh';synth=reports/'m002_E002_R001_AT002_fresh_synth';synth_at=at.parents[2]/'R001/attempts/AT002_fresh_synth'
os.environ.update(HAP_PROJECT_DIR=str(project),HAP_SYNTH_REPORT_DIR=str(synth),HAP_SYNTH_ATTEMPT_DIR=str(synth_at),HAP_EXECUTION_MODE='checkpoint_restored_commands',HAP_STAGE='place')
m.hook_batch('opt',out)
value=json.loads((out/'integrity_opt.json').read_text());m.verify_cdc_proof(value['cdc_classification'])
print(json.dumps({'verdict':'PASS','gate_issues':value['gate_issues'],'actual_bram_ports':value['reset_fanout_observation']['bram_port_clock_endpoints'],'current_checker_archive':m.file_id(at/'archived_sources.sha256'),'preserved_original_stage_manifest':m.file_id(source/'stage_inputs.sha256'),'replay_inputs':m.file_id(out/'stage_inputs.sha256'),'replayed_integrity':m.file_id(out/'integrity_opt.json')},indent=2))
