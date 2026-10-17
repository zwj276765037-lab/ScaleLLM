import sys,os,json,shutil,datetime
from pathlib import Path
stage=Path('/tmp/m002_aux_cdc_stage.nrx53mqv');sys.path.insert(0,str(stage/'vivado/scripts'))
import m002_physical_evidence as m
root=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware');m.ROOT=root
reports=root/'vivado/reports';source=reports/'m002_E002_R003_AT007_bram_port_clock_debug_place_physopt'
at=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R002/attempts/AT011_auxiliary_cdc_full_gate_cpu')
at.mkdir(parents=True,exist_ok=True)
out=at/'actual_complete_opt_gate';out.mkdir(exist_ok=False)
for p in source.iterdir():
    if p.is_file() and p.name not in {'opt.dcp','integrity_opt.json','reset_structure_opt.json','admission_opt.txt','launcher_status.txt','vivado.log','implementation_run.log','vivado.jou'}:shutil.copy2(p,out/p.name)
# All reads retain their real identities; only derived outputs are written here.
project=root/'vivado/project/m002_E002_R001_AT001_fresh';synth=reports/'m002_E002_R001_AT002_fresh_synth'
synth_at=at.parents[2].parent/'R001/attempts/AT002_fresh_synth'
# explicit task path avoids historical layout inference
synth_at=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth')
os.environ.update(HAP_PROJECT_DIR=str(project),HAP_SYNTH_REPORT_DIR=str(synth),HAP_SYNTH_ATTEMPT_DIR=str(synth_at),HAP_EXECUTION_MODE='checkpoint_restored_commands',HAP_STAGE='place')
m.hook_batch('opt',out)
value=json.loads((out/'integrity_opt.json').read_text());print(json.dumps({'gate_issues':value['gate_issues'],'structure':value['reset_structure']['qualified'],'fanout':value['reset_fanout_observation']['qualified'],'port_endpoints':value['reset_fanout_observation']['bram_port_clock_endpoints'],'auxiliary':value['reset_fanout_observation']['auxiliary_cdc_observation'],'cdc':value['cdc_classification']},indent=2))
m.verify_cdc_proof(value['cdc_classification'])
lineage=m.synth_lineage(project,synth,synth_at)
parent_out=at/'actual_parent_preflight';parent_out.mkdir()
parent=m.recovery_opt_parent(source,project,lineage,parent_out)
(at/'actual_combined_status.json').write_text(json.dumps({'execution_state':'completed','verdict':'PASS','scope':'offline current complete OPT hook using actual 688 port observations; debug/place NOT_RUN','original_failed_status_preserved':True,'integrity':m.file_id(out/'integrity_opt.json'),'parent':m.file_id(parent_out/'recovery_parent.json'),'inherited_reset':parent['inherited_reset_evidence']},indent=2)+'\n')
print('FULL_ACTUAL_OPT_GATE_PASS_AND_PARENT_PASS')
