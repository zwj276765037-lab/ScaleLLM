"""Read-only qualification of genuine frozen AT008 and the 339/45 synthesis."""
import datetime as dt
import json
from pathlib import Path
import sys
WORKSPACE=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
STAGE=Path('/tmp/m002_full_impl_stage.5mzwlphv')
sys.path.insert(0,str(STAGE/'vivado/scripts'))
import m002_physical_evidence as m
import m002_execution_profile as p
m.ROOT=WORKSPACE/'project/hardware'
OUTPUT=Path(__file__).parent
project=m.ROOT/'vivado/project/m002_E002_R001_AT001_fresh'
synth=m.ROOT/'vivado/reports/m002_E002_R001_AT002_fresh_synth'
attempt=WORKSPACE/'project/E002_m002_synthesis_and_physical_baseline/experiment_results/runs/R001/attempts/AT002_fresh_synth'
source=m.ROOT/'vivado/reports/m002_E002_R003_AT008_complete_opt_gate_debug_place_physopt'
started=dt.datetime.now(dt.timezone.utc).isoformat()
lineage=m.synth_lineage(project,synth,attempt)
parent=m.recovery_pre_place_parent(source,project,lineage,OUTPUT,_write=False)
planned_attempt=WORKSPACE/p.EXPERIMENT/'experiment_results/runs/R002/attempts/AT001_full_pre_place_restore_place_physopt'
planned_report=m.ROOT/'vivado/reports/m002_E003_R002_AT001_full_pre_place_restore_place_physopt'
authorization=p.authorization(WORKSPACE,'place',planned_attempt,planned_report)
(OUTPUT/'qualified_original_pre_place_parent.json').write_text(json.dumps(parent,indent=2)+'\n')
(OUTPUT/'planned_E003_authorization.json').write_text(json.dumps(authorization,indent=2)+'\n')
result={'execution_state':'completed','verdict':'PASS','scope':'CPU-only immutable synthesis/AT008 actual source qualification; no new EDA or POST generation',
        'started_utc':started,'ended_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'synthesis':lineage,'checkpoint':parent['checkpoint'],'pre_place':parent['inherited_pre_place'],
        'post_completion':parent['post_termination_post_completion'],'contract':authorization['contract'],
        'legacy_source_policy_preserved':parent['single_bounded_restart'],
        'new_policy':'explicit E003 authorization is attached only by genuine managed launch',
        'source_rows':lineage['source_rows'],'checkpoint_paths':lineage['checkpoint_paths']}
(OUTPUT/'actual_source_qualification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True)
