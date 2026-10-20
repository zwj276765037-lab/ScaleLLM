"""Strict normalized clock evidence; no old-schema fallback or native0 claim."""
import argparse,hashlib,json,re
from pathlib import Path
PREFIX='inst/u_core/u_compute/u_attention/u_meta/'
def validate(groups,endpoints):
 errors=[]
 def need(v,m):
  if not v:errors.append(m)
 by={};aliases={}
 for g in groups:
  gid=g.get('id');need(bool(gid) and gid not in by,'duplicate/empty group identity');by[gid]=g
  nets=g.get('nets',[]);need(g.get('canonical_top_net') in nets,'canonical top membership');need('core_clk' in nets,'selected core_clk boundary missing');need(isinstance(nets,list) and bool(nets) and len(nets)==len(set(nets)),'group nets missing/duplicate')
  for n in nets:need(n not in aliases,'overlapping group aliases');aliases[n]=gid
  ds=g.get('leaf_drivers',[]);os=g.get('driver_cells',[]);refs=g.get('driver_refs',[]);ps=g.get('primary_ports',[]);dirs=g.get('primary_port_directions',[])
  need(len(ds)==len(os)==len(refs) and len(ds)==len(set(ds)),'driver owner/ref coverage')
  need(all(d.rsplit('/',1)[0]==o for d,o in zip(ds,os)),'driver owner identity')
  need((len(ds)==1 and not ps and not dirs) or (not ds and len(ps)==len(dirs)==1 and dirs==['IN']),'unresolved/multiple clock source')
 seen=set();used=set();expanded=[]
 for e in endpoints:
  c=e.get('cell','');m=re.fullmatch(re.escape(PREFIX)+r'g_m003_width_slices\.g_slice\[([01])\]\.meta_mem_reg_uram_(0|[1-9][0-9]*)',c)
  need(m is not None,'endpoint cell identity')
  key=(int(m[1]),int(m[2])) if m else (-1,-1)
  need(key not in seen,'duplicate endpoint');seen.add(key)
  need(e.get('slice')==key[0] and e.get('ordinal')==key[1] and e.get('CLK_pin')==c+'/CLK','endpoint pin/slice/ordinal identity')
  gid=e.get('group');need(gid in by,'unknown endpoint group');used.add(gid)
  direct=e.get('direct_nets',[]);need(len(direct)==1 and all(aliases.get(n)==gid for n in direct),'actual direct-net group membership')
  if gid in by:
   g=by[gid];expanded.append(dict(cell=c,CLK_pin=e.get('CLK_pin'),nets=g['nets'],leaf_drivers=g['leaf_drivers'],primary_ports=g['primary_ports'],primary_port_directions=g['primary_port_directions']))
 need(len(endpoints)==80 and seen=={(s,n) for s in (0,1) for n in range(40)},'exact80 endpoint coverage')
 need(used==set(by),'unused/missing group coverage')
 return dict(passed=not errors,errors=errors,endpoint_count=len(endpoints),group_count=len(groups),scope='Normalized same-call actual native membership/source facts only; no native exit/G4'),expanded

def load(path):
 with Path(path).open() as f:return [json.loads(x) for x in f]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);a=p.parse_args();r=a.report
 result,expanded=validate(load(r/'clock_groups.jsonl'),load(r/'clock_endpoints.jsonl'))
 complete=json.loads((r/'diagnostic_complete.json').read_text())
 if complete.get('execution')!='completed' or complete.get('schema')!='M003_grouped_clock_v1' or complete.get('endpoints')!=80 or complete.get('groups')!=result['group_count']:result['passed']=False;result['errors'].append('completion/schema mismatch')
 (r/'grouped_clock_qualification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(not result['passed'])
