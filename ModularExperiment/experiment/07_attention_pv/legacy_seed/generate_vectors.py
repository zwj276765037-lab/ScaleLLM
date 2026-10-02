#!/usr/bin/env python3
from __future__ import annotations
import json,struct
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent;S=H.parents[2]/'HAP_new'/'data'/'pv_tile16_s43';O=H/'data';N=4096
def sx(x,w):return x-(1<<w) if x&(1<<(w-1)) else x
def unpack(x,w,n):x=int(x,16);return [sx((x>>(i*w))&((1<<w)-1),w) for i in range(n)]
def b16(x):return int(np.float16(x).view(np.uint16))
def b32(x):return struct.unpack('<I',struct.pack('<f',float(np.float32(x))))[0]
pr=[int(x,16) for x in (S/'input_prob.mem').read_text().splitlines()];vs=[unpack(x,12,16) for x in (S/'input_v16_s12.mem').read_text().splitlines()];me=[int(x,16) for x in (S/'input_meta16.mem').read_text().splitlines()];O.mkdir(parents=True,exist_ok=True)
fs={n:(O/n).open('w') for n in ['prob16.mem','prob32.mem','v16.mem','v32.mem','e16.mem','e32.mem']};sat16=sat32=0
try:
 for r in range(32):
  a16=[np.float16(0)]*16;a32=[np.float32(0)]*16
  for k in range(128):
   z=r*128+k;p=pr[z]/65536;code=me[z]&255;sh=(me[z]>>8)&63;scale=code/(1<<sh) if code else 0
   v=[x*scale for x in vs[z]];fs['prob16.mem'].write(f'{b16(p):04x}\n');fs['prob32.mem'].write(f'{b32(p):08x}\n');fs['v16.mem'].write(f'{sum(b16(x)<<(i*16) for i,x in enumerate(v)):064x}\n');fs['v32.mem'].write(f'{sum(b32(x)<<(i*32) for i,x in enumerate(v)):0128x}\n')
   for i,x in enumerate(v):a16[i]=np.float16(a16[i]+np.float16(np.float16(p)*np.float16(x)));a32[i]=np.float32(a32[i]+np.float32(np.float32(p)*np.float32(x)))
  o16=[];o32=[]
  for x in a16:
   if np.isinf(x):q=8388607 if x>0 else -8388608
   else:q=int(np.rint(float(x)*65536))
   sat16+=q>=8388607 or q<=-8388608;o16.append(max(-8388608,min(8388607,q)))
  for x in a32:
   q=int(np.rint(float(x)*65536));sat32+=q>8388607 or q< -8388608;o32.append(max(-8388608,min(8388607,q)))
  fs['e16.mem'].write(f'{sum((x&0xffffff)<<(i*24) for i,x in enumerate(o16)):096x}\n');fs['e32.mem'].write(f'{sum((x&0xffffff)<<(i*24) for i,x in enumerate(o32)):096x}\n')
finally:[x.close() for x in fs.values()]
m={'schema':'m9_matched_pv_v1','rows':32,'keys':128,'lanes':16,'fp16_saturation':sat16,'fp32_saturation':sat32};(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('M9_VECTOR_JSON:',json.dumps(m))
