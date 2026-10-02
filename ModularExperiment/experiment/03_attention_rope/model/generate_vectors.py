#!/usr/bin/env python3
"""Generate 512 common S24/S18 RoPE pairs and matched FP goldens."""
from __future__ import annotations
import json, random, struct
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;OUT=HERE.parent/'data';N=512;SEED=0x4D35524F5045
MASK24=(1<<24)-1
def bits32(x):return struct.unpack('<I',struct.pack('<f',float(np.float32(x))))[0]
def sx(x,w):return x-(1<<w) if x&(1<<(w-1)) else x
def sat24(x):return min((1<<23)-1,max(-(1<<23),x))
def fixed_round(v):
    return (v+32768)>>16 if v>=0 else (v+32767)>>16
def fp_round_s24(v):return sat24(int(np.rint(float(np.float32(v))*(1<<16))))
def ftz16(v):
 v=np.float16(v);b=int(v.view(np.uint16));return np.float16(-0.0 if b&0x8000 else 0.0) if b&0x7c00==0 else v
def op16(a,b,op):return ftz(np.float32(ftz16(a))+np.float32(ftz16(b))) if False else ftz16(op(np.float32(ftz16(a)),np.float32(ftz16(b))))
def bits16(x):return int(np.float16(x).view(np.uint16))
def main():
 rng=random.Random(SEED); rec=[]
 for i in range(N):
  if i==0:x0=x1=0;c=65536;s=0
  elif i==1:x0=(1<<23)-1;x1=-(1<<23);c=s=46341
  else:
   x0=rng.randrange(-(1<<21),1<<21);x1=rng.randrange(-(1<<21),1<<21)
   theta=rng.uniform(-np.pi,np.pi);c=int(round(np.cos(theta)*65536));s=int(round(np.sin(theta)*65536))
   c=max(-65536,min(65536,c));s=max(-65536,min(65536,s))
  fy0=sat24(fixed_round(x0*c)-fixed_round(x1*s));fy1=sat24(fixed_round(x0*s)+fixed_round(x1*c))
  xf0=np.float32(x0/(1<<16));xf1=np.float32(x1/(1<<16));cf=np.float32(c/(1<<16));sf=np.float32(s/(1<<16))
  py0=np.float32(np.float32(xf0*cf)-np.float32(xf1*sf));py1=np.float32(np.float32(xf0*sf)+np.float32(xf1*cf))
  fpy0=fp_round_s24(py0);fpy1=fp_round_s24(py1)
  h0,h1,hc,hs=map(np.float16,(xf0,xf1,cf,sf))
  hp0=op16(h0,hc,lambda a,b:a*b);hp1=op16(h1,hs,lambda a,b:a*b);hp2=op16(h0,hs,lambda a,b:a*b);hp3=op16(h1,hc,lambda a,b:a*b)
  hy0=op16(hp0,hp1,lambda a,b:a-b);hy1=op16(hp2,hp3,lambda a,b:a+b)
  hpy0=fp_round_s24(np.float32(ftz16(hy0)));hpy1=fp_round_s24(np.float32(ftz16(hy1)))
  rec.append((x0,x1,c,s,fy0,fy1,fpy0,fpy1,hpy0,hpy1,xf0,xf1,cf,sf,h0,h1,hc,hs))
 OUT.mkdir(parents=True,exist_ok=True)
 names=['input_fixed.mem','input_fp16.mem','input_fp32.mem','expected_fixed.mem','expected_fp16.mem','expected_fp32.mem']
 fs={n:(OUT/n).open('w') for n in names}
 try:
  for x0,x1,c,s,fy0,fy1,py0,py1,hy0,hy1,xf0,xf1,cf,sf,h0,h1,hc,hs in rec:
   fs['input_fixed.mem'].write(f'{((s&((1<<18)-1))<<66)|((c&((1<<18)-1))<<48)|((x1&MASK24)<<24)|(x0&MASK24):021x}\n')
   fs['input_fp32.mem'].write(f'{(bits32(sf)<<96)|(bits32(cf)<<64)|(bits32(xf1)<<32)|bits32(xf0):032x}\n')
   fs['input_fp16.mem'].write(f'{(bits16(hs)<<48)|(bits16(hc)<<32)|(bits16(h1)<<16)|bits16(h0):016x}\n')
   fs['expected_fixed.mem'].write(f'{((fy1&MASK24)<<24)|(fy0&MASK24):012x}\n')
   fs['expected_fp32.mem'].write(f'{((py1&MASK24)<<24)|(py0&MASK24):012x}\n')
   fs['expected_fp16.mem'].write(f'{((hy1&MASK24)<<24)|(hy0&MASK24):012x}\n')
 finally:
  [f.close() for f in fs.values()]
 m={'schema':'hap_m5_rope_v1','seed':SEED,'vectors':N,'common_output':'two S24 Q8.16 values','fp_input':'exact S24/S18 values converted to FP32','fp_output_rounding':'nearest-even to S24'}
 (OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n');print('M5_VECTOR_JSON:',json.dumps(m,sort_keys=True))
if __name__=='__main__':main()
