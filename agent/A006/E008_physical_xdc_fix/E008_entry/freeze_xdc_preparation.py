#!/usr/bin/env python3
"""Freeze one physical-export API option delta; never execute native tools."""
import ast,json,os
from pathlib import Path
from datetime import datetime,timezone
from directed_evidence import identity
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
BASE=ROOT/'agent/A006/E008_native_property_policy_fix/E008_entry'
def write(p,v):
 with p.open('x') as f:f.write(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 original=BASE/'prepared_manifest.json';base=json.loads(original.read_text());target=HERE/'prepared_manifest.json';assert not target.exists()
 for row in base['own_sources']+base['reused_sources']+base['CPU_checks']+base['runtime_dependencies']+base['documentation']:assert identity(row['path'])==row
 for row in base['own_sources']:
  src=Path(row['path']);actual=(HERE/src.name).read_bytes()
  expected=src.read_bytes()
  if src.name=='candidate_hooks.tcl':
   assert expected.count(b'write_xdc -constraints physical ')==1
   expected=expected.replace(b'write_xdc -constraints physical ',b'write_xdc -type physical ')
  assert actual==expected,src.name
 cpu=HERE/'CPU_checks/CT002_physical_export/results.json';checks=json.loads(cpu.read_text())
 assert len(checks['cases'])==9 and all(checks['checks'].values()) and all(r['passed'] for r in checks['cases'])
 for key in ['source','baseline','fixture','producer']:assert identity(checks[key]['path'])==checks[key]
 for row in checks['cases']:
  for item in row['artifacts']:assert identity(item['path'])==item
 failed=ROOT/'project/E008_m002_exact_hotspot_offload_implementation/experiment_results/runs/R001/attempts/AT002_C01_native_policy_fix_full_implementation'
 facts=json.loads((failed/'terminal_facts.json').read_text());assert facts['closure_verified'] and all(facts['checks'].values())
 assert facts['native_exit_code']==facts['supervisor_exit_code']==1 and facts['stop_reason'] is None
 native=HERE.parent/'native_help';assert json.loads((native/'status_print.json').read_text())['returncode']==0
 log=(native/'vivado_print.log').read_text();assert 'Values: valid, invalid, all' in log and '[-type]' in log and 'physical' in log and 'E008_NATIVE_HELP_END write_xdc' in log
 manual=Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/doc/eng/man/write_xdc')
 reuse=dict(original_consumed_preparation=identity(original),original_unchanged_reuse_record=base['source_reuse_manifest'],actual_failed_attempt_terminal=identity(failed/'terminal_facts.json'),actual_native_failure=identity(failed/'status.json'),
  delta='Exactly one executable Tcl option: write_xdc -constraints physical to -type physical; same output path; no quiet/force/no_fixed_only/reload/policy/selector or physical acceptance change',
  reuse_scope='Unchanged original26 policy, collector/index/logging/full flow CPU evidence reused; only actual region export and error propagation checked in9cases',
  finite_native_API_help=[identity(native/name) for name in ['help_write_xdc_print.tcl','execution_print.json','status_print.json','vivado_print.log']],installed_2025_2_manual=identity(manual),
  full_design_implementation_executed=False)
 # The clone has not been consumed. Replace its copied historical reuse record before freeze.
 (HERE/'source_reuse_manifest.json').unlink();write(HERE/'source_reuse_manifest.json',reuse)
 own=[HERE/Path(row['path']).name for row in base['own_sources']]+[HERE/'check_xdc_export_CPU.py',Path(__file__).resolve()]
 for p in own:
  if p.suffix=='.py':ast.parse(p.read_text(),filename=str(p))
 value=dict(base);value.update(recorded_utc=datetime.now(timezone.utc).isoformat(),own_sources=[identity(p) for p in own],
  selector_reference=identity(HERE/'target_authority.json'),source_reuse_manifest=identity(HERE/'source_reuse_manifest.json'),CPU_checks=base['CPU_checks']+[identity(cpu)],documentation=[identity(HERE/'README.md')],
  shared_collector=identity(HERE/'directed_exporter.tcl'),shared_validator=identity(HERE/'directed_evidence.py'),original_preparation=identity(original),
  validation=dict(affected_actual_constrain_region_CPU='9 focused cases passed',unchanged_tests='Original26policy/index/collector/logging/full flow evidence reused, not rerun',
   finite_native_API_help='Actual Vivado2025.2 native0 help; no design opened',actual_pre_place_membership='NOT_RUN_IN_NEW_ATTEMPT',native_policy_preservation='NOT_RUN_IN_NEW_ATTEMPT',place_physopt_route='NOT_RUN',physical_signoff=False),
  physical_xdc_export_repair=reuse)
 write(target,value);print(json.dumps(identity(target)))
if __name__=='__main__':main()
