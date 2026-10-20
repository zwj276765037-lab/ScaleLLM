from pathlib import Path
import hashlib,json,datetime
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');HERE=Path(__file__).resolve().parent
baseline=json.loads((ROOT/'agent/A006/M003_SM014_design_20261018/design_input_identities.json').read_text())['production_inputs']
allowed={'hap_mlp_shared_dual_slice16x12_s44_s54.sv','hap_weight_meta_resident.sv','hap_attention_board_cohort16_core.sv','create_vcu118_board.tcl','build_vcu118_board.tcl','m002_physical.tcl','m002_diagnostic_common.tcl'}
changed=[];same=[]
for e in baseline:
 p=Path(e['path']);digest=hashlib.sha256(p.read_bytes()).hexdigest()
 if digest!=e['sha256']:
  assert p.name in allowed,('unplanned changed baseline input',str(p));changed.append(dict(path=str(p),before_sha256=e['sha256'],after_sha256=digest))
 else:same.append(e)
assert {Path(e['path']).name for e in changed}==allowed
result=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),baseline_entries=len(baseline),unchanged=len(same),changed=changed,unplanned_changes=[],scope='SM014 frozen144 actual file audit; only three selected RTL and four public entry files changed')
out=HERE/'selected_input_audit_before_create_v3.json';assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='changed'}))
