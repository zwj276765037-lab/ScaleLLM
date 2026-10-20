"""Offline selected-cell membership check; never invokes EDA or changes constraints."""
from pathlib import Path
import argparse,collections,hashlib,json

def identity(path):
 path=Path(path)
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
 return dict(path=str(path.resolve()),bytes=path.stat().st_size,sha256=h.hexdigest())
def check(stream,spec):
 s=json.loads(spec.read_text());groups={g['id']:g for g in s['groups']}
 bits={(g['family'],b):g for g in groups.values() for b in g['bits']}
 counts=collections.Counter();pblocks=collections.Counter();seen=set();errors=[];extra_c01=set()
 with stream.open() as source:
  for line in source:
   row=json.loads(line);role=row.get('role')
   if role not in ('payload','buffer','c01'):continue
   name=row['NAME'];counts[role]+=1
   if name in seen:errors.append('duplicate selected cell:'+name)
   seen.add(name);pb=set(x.strip('{}') for x in str(row.get('PBLOCKS','')).split())
   if role=='c01':
    if 'm002_exact_hotspot_SLR2' not in pb:errors.append('C01 lost SLR2:'+name)
    if any(n.startswith('m003_parent_') for n in pb):errors.append('C01 unexpectedly assigned M2 CR:'+name)
    extra_c01.update(pb-{'m002_exact_hotspot_SLR2'})
   else:
    g=groups[row['group']] if role=='buffer' else bits[(row['family'],int(row['bit']))]
    expected='m003_parent_'+g['clock_region']
    if expected not in pb:errors.append('M2 lost required CR:'+name)
    if any(n.startswith('m003_parent_') and n!=expected for n in pb):errors.append('M2 assigned wrong extra CR:'+name)
    pblocks[expected]+=1
 if counts['payload']!=13120 or counts['buffer']!=81 or counts['c01']<=0:errors.append('selected role coverage/count incomplete')
 return dict(passed=not errors,errors=errors,counts=dict(counts),M2_expected_region_member_counts=dict(sorted(pblocks.items())),C01_other_PBLOCKS=sorted(extra_c01),scope='Only saved selected-cell actual PBLOCKS; C01/M2 identity separation and no lost/wrong-M2 membership. Does not query Pblock PARENT or prove later-stage state.',stream=identity(stream),spec=identity(spec),checker=identity(Path(__file__)))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stream',type=Path,required=True);p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=check(a.stream,a.spec)
 with a.output.open('x') as stream:json.dump(r,stream,indent=2);stream.write('\n')
 print(json.dumps({k:r[k] for k in ('passed','counts','C01_other_PBLOCKS')}));raise SystemExit(0 if r['passed'] else 1)
