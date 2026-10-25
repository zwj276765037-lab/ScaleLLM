#!/usr/bin/env python3
"""Frozen, bounded role decisions from actual native/library pin evidence.

This file never executes generated Tcl. Unknown or conflicting roles stop the
candidate before any timing constraint is reset or changed.
"""
import argparse,hashlib,json
from pathlib import Path

FD={'FDRE','FDSE','FDCE','FDPE','FDRE_1','FDSE_1','FDCE_1','FDPE_1'}
BUF={'BUFG','BUFGCE','BUFGCE_DIV','BUFGCTRL','BUFG_GT','BUFG_GT_SYNC','BUFH','BUFHCE','BUFR','BUFCE_LEAF','BUFCE_ROW','BUFCE_ROW_FSR'}

def flag(value):
 if value in (True,1,'1','true','TRUE'):return True
 if value in (False,0,'0','false','FALSE'):return False
 return None

def primitive_role(ref,pin):
 if ref in FD:
  if pin=='C':return 'CLOCK'
  if pin=='Q':return 'LAUNCH'
  if pin in {'D','CE','R','S','CLR','PRE'}:return 'CAPTURE'
 if ref in BUF:
  if pin in {'I','I0','I1'}:return 'CLOCK'
  if pin in {'O','O0','O1'}:return 'LAUNCH'
  if pin.startswith('CE') or pin in {'CLR','S0','S1','IGNORE0','IGNORE1','DIV0','DIV1','DIV2'}:return 'CAPTURE'
 if ref in {'DSP48E1','DSP48E2'} and pin=='CLK':return 'CLOCK'
 if ref in {'RAMB18E1','RAMB18E2','RAMB36E1','RAMB36E2'} and pin in {'CLKARDCLK','CLKBWRCLK'}:return 'CLOCK'
 if ref in {'URAM288','URAM288_BASE'} and pin=='CLK':return 'CLOCK'
 return 'UNKNOWN'

def decide(fact,bound_refs):
 role=primitive_role(fact['owner_ref'],fact['ref_pin'])
 inward=fact['direction'] in {'IN','INOUT'};ld=fact['library_direction'];lc=flag(fact['library_is_clock']);ldata=flag(fact['library_is_data']);native_clock=flag(fact['is_clock'])
 evidence={'primitive_role':role,'bound_vendor_model':fact['owner_ref'] in bound_refs,'library_is_clock':lc,'library_is_data':ldata,'native_clock_member':fact['native_clock_member'],'native_output_member':fact['native_output_member']}
 if fact['library_pin_count']!=1:return 'UNKNOWN','ambiguous_or_missing_library_pin',evidence
 if lc is True and ldata is True:return 'UNKNOWN','library_flags_indicate_dual_role',evidence
 if inward and ld in {'IN','INOUT'}:
  if role=='CAPTURE' and fact['owner_ref'] in bound_refs and lc is not True and native_clock is True:
   return 'ADD_EXACT_CAPTURE','bound_primitive_capture_or_control_role_and_inward_library_pin',evidence
  if lc is False and native_clock is True and any(k in fact['categories'] for k in ['data','asynchronous','clock_enable','clock_gating_CE']):
   return 'ADD_EXACT_CAPTURE','native_capture_requirement_and_inward_nonclock_library_role',evidence
  if role=='CLOCK' and fact['owner_ref'] in bound_refs and native_clock is True and lc is True and (fact['native_clock_member'] or fact['pin_clocks']):
   return 'EXCLUDE_PROVEN_NONCAPTURE','bound_pure_clock_primitive_role_library_clock_and_actual_clock',evidence
 if fact['direction']=='OUT' and ld=='OUT' and role=='LAUNCH' and fact['owner_ref'] in bound_refs and fact['native_output_member']:
  return 'EXCLUDE_PROVEN_NONCAPTURE','bound_pure_launch_output_role_and_actual_native_output',evidence
 return 'UNKNOWN','role_not_proven_by_frozen_rules',evidence

def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('facts',type=Path);ap.add_argument('models',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
 sources=json.loads(a.models.read_text())['models']
 for ref,item in sources.items():
  if digest(Path(item['path']))!=item['sha256']:raise ValueError('vendor model drift: '+ref)
 facts=[json.loads(line) for line in a.facts.read_text().splitlines() if line.strip()]
 if len(facts)>512:raise ValueError('capture role discovery exceeds512 bounded records')
 decisions=[];extras={'ddr0':[],'ddr1':[]};unknown=0
 for fact in facts:
  if fact['domain'] not in extras or any(c in fact['name'] for c in '\t\n\r'):raise ValueError('invalid native fact identity')
  action,reason,evidence=decide(fact,set(sources));unknown+=action=='UNKNOWN'
  decisions.append({**fact,'action':action,'reason':reason,'role_evidence':evidence})
  if action=='ADD_EXACT_CAPTURE':extras[fact['domain']].append(fact['name'])
 output={'status':'UNKNOWN_REJECTED_BEFORE_TIMING_MUTATION' if unknown else 'ALL_DISCOVERED_ROLES_PROVEN','facts_sha256':digest(a.facts),'models_sha256':digest(a.models),'unknown_count':unknown,'extra_capture_pins':{d:sorted(set(v)) for d,v in extras.items()},'decisions':decisions}
 a.output.write_text(json.dumps(output,indent=2)+'\n')
 with a.output.with_suffix('.tsv').open('w') as f:
  for row in decisions:f.write('\t'.join([row['domain'],row['action'],row['name']])+'\n')
 print(json.dumps({'status':output['status'],'records':len(facts),'unknown':unknown,'extra':{d:len(v) for d,v in extras.items()}}))
 return 2 if unknown else 0
if __name__=='__main__':raise SystemExit(main())
