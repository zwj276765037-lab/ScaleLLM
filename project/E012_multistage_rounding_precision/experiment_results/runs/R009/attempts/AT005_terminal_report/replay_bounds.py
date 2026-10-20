"""Reproducible postrun replay of the prelaunch supplemental integer bounds."""
import json
from pathlib import Path
n=0
for b in [0,2,4]:
 for base in [9,37,42,44,45,54]:
  w=base+b;lo=-(1<<(w-1));hi=(1<<(w-1))-1
  for x in [lo-513,lo-1,lo,lo+1,-513,-257,-129,-128,-127,-1,0,1,127,128,129,257,513,hi-1,hi,hi+1,hi+513]:
   assert ((x-lo)&((1<<w)-1))+lo==((x-lo)%(1<<w))+lo;n+=1
 for base in [24,32]:
  w=base+b;lo=-(1<<(w-1));hi=(1<<(w-1))-1
  for x in [lo-1,lo,lo+1,-1,0,1,hi-1,hi,hi+1]:
   y=max(lo,min(hi,x));assert lo<=y<=hi and (y!=x)==(x<lo or x>hi);n+=1
assert n==432
Path(__file__).with_name('bounds_replay_result.json').write_text(json.dumps(dict(passed=True,cases=n,scope='Postrun exact reproducibility replay of prelaunch supplemental432 wrap/saturation assertions; no GPU'),indent=2)+'\n')
