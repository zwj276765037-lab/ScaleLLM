#!/usr/bin/env python3
"""Same-stage same-metric M003 synth resource comparison, never route subtraction."""
from pathlib import Path
import argparse,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'agent/A007/M003_SM015_SM017_review_20261018/E005_same_stage_synthesis_baseline_review.json'
BASE_SHA='cd15c3a0ed905cc283633ca856b92e9815863cf5b282ae5ef055ad2e2472dc2b'
KEYS=['total_LUTs','logic_LUTs','LUTRAMs','SRLs','FFs_report_including_AND_OR','RAMB36','RAMB18','URAM','DSP']
def identity(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def qualify_header(p):
 text=p.read_text();header=text.split('Utilization Design Information',1)[0]
 expected={'Design':'scalellm_vcu118_f05_bd_wrapper','Device':'xcvu9p-flga2104-2L-e','Design State':'Synthesized'}
 for key,value in expected.items():
  rows=re.findall(r'^\| '+re.escape(key)+r'[ \t]*:[ \t]*(.*)$',header,re.M)
  if rows!=[value]:raise ValueError('native report header mismatch '+key)
 tools=re.findall(r'^\| Tool Version[ \t]*:[ \t]*(.*)$',header,re.M)
 if len(tools)!=1 or not tools[0].startswith('Vivado v.2025.2 (lin64) Build 6299465 '):raise ValueError('native tool report identity mismatch')
 return True
def parse_hierarchy(p):
 qualify_header(p)
 out={}
 for line in p.read_text().splitlines():
  f=[x.strip() for x in line.split('|')[1:-1]]
  if len(f)!=11 or not all(re.fullmatch(r'\d+',x) for x in f[2:]):continue
  if f[0] in ('scalellm_vcu118_f05_bd_wrapper','u_meta','u_shared_compute','(u_shared_compute)'):
   key={'scalellm_vcu118_f05_bd_wrapper':'top','(u_shared_compute)':'u_shared_compute_self'}.get(f[0],f[0])
   if key in out:raise ValueError('ambiguous native hierarchy role '+key)
   out[key]=dict(zip(KEYS,map(int,f[2:])))
 if set(out)!={'top','u_meta','u_shared_compute','u_shared_compute_self'}:raise ValueError('missing native resource hierarchy')
 return out
def parse_carry(p):
 qualify_header(p)
 rows=[int(m[1]) for m in re.finditer(r'^\| CARRY8[ \t]+\|[ \t]+(\d+)[ \t]+\|[ \t]+CLB[ \t]+\|$',p.read_text(),re.M)]
 if len(rows)!=1:raise ValueError('missing/duplicate native CARRY8 primitive count')
 return rows[0]
def compare(new,old,carry,oldcarry):
 errors=[];deltas={k:{m:new[k][m]-old[k][m] for m in KEYS} for k in new}
 limits={'top':(177,34),'u_meta':(96,34),'u_shared_compute':(81,0),'u_shared_compute_self':(81,0)}
 for scope,(luts,ffs) in limits.items():
  d=deltas[scope]
  if d['total_LUTs']>luts or d['logic_LUTs']>luts or d['FFs_report_including_AND_OR']>ffs:errors.append(scope+' LUT/FF delta budget exceeded')
  for hard in ('RAMB36','RAMB18','URAM','DSP','LUTRAMs','SRLs'):
   if d[hard]!=0:errors.append(scope+' changed fixed resource '+hard)
 if carry-oldcarry>8:errors.append('global CARRY8 delta budget exceeded')
 if new['u_meta']['URAM']!=80:errors.append('meta URAM total not80')
 return dict(passed=not errors,errors=errors,same_stage='post_synth',deltas=deltas,global_CARRY8_delta=carry-oldcarry,units='native utilization report LUT/FF metrics; separate exact new-cone checks required')
def main():
 p=argparse.ArgumentParser();p.add_argument('--report-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if identity(BASE)['sha256']!=BASE_SHA:raise ValueError('qualified baseline review identity changed')
 baseline=json.loads(BASE.read_text())
 for e in baseline['reports'][:2]:
  if identity(Path(e['path']))['sha256']!=e['sha256']:raise ValueError('qualified baseline report identity changed')
 n=a.report_dir/'utilization_hierarchical_post_synth.rpt';g=a.report_dir/'utilization_post_synth.rpt'
 result=compare(parse_hierarchy(n),{k:{m:v[m] for m in KEYS} for k,v in baseline['hierarchical_resources'].items()},parse_carry(g),baseline['global_primitives']['CARRY8']['count'])
 result.update(baseline_review=identity(BASE),new_reports=[identity(n),identity(g)])
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':sys.exit(main())
