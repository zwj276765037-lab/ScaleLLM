#!/usr/bin/env python3
"""Generate one matched 8-row QK workload for fixed, FP16, and FP32 RTL."""
from __future__ import annotations
import json, struct, sys
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent; OUT=HERE/"data"
HAP=HERE.parents[2]/"HAP_new"; SRC=HAP/"data"/"qk_score_row_128"
sys.path.insert(0,str(HAP/"model"))
from fixbit_v2 import HEAD_SCALE_Q16

ROWS,KEYS,GROUPS=8,128,4
def sx(x,w):return x-(1<<w) if x&(1<<(w-1)) else x
def unpack(line,w,n):
 x=int(line,16);return [sx((x>>(i*w))&((1<<w)-1),w) for i in range(n)]
def bits16(v):return int(np.float16(v).view(np.uint16))
def bits32(v):return struct.unpack('<I',struct.pack('<f',float(np.float32(v))))[0]
def ftz16(v):
 v=np.float16(v);b=int(v.view(np.uint16));return np.float16(-0.0 if b&0x8000 else 0.0) if b&0x7c00==0 else v
def op16(a,b,op):
 v=op(np.float32(ftz16(a)),np.float32(ftz16(b)))
 # Xilinx Floating-Point v7.1 flushes rounded half subnormal results.
 return ftz16(v)
def clip(v):return max(-(16<<14),min(16<<14,int(v)))

queries=[unpack(x,24,32) for x in (SRC/"query_group_s24.mem").read_text().splitlines()]
keys12=[unpack(x,12,32) for x in (SRC/"key_group_s12.mem").read_text().splitlines()]
metas=[int(x,16) for x in (SRC/"key_meta16.mem").read_text().splitlines()]
masks=[int(x,16) for x in (SRC/"mask.mem").read_text().splitlines()]

OUT.mkdir(parents=True,exist_ok=True)
names=["query_fp16.mem","query_fp32.mem","key_fp16.mem","key_fp32.mem",
       "mask.mem","expected_fp16.mem","expected_fp32.mem"]
fs={n:(OUT/n).open('w') for n in names}; f16clips=f32clips=0
try:
 for row in range(ROWS):
  q16=[];q32=[]
  for group in range(GROUPS):
   for x in queries[row*GROUPS+group]:
    q=float(x)/(1<<16);q16.append(bits16(q));q32.append(bits32(q))
  fs['query_fp16.mem'].write(f'{sum(x<<(i*16) for i,x in enumerate(q16)):0{128*4}x}\n')
  fs['query_fp32.mem'].write(f'{sum(x<<(i*32) for i,x in enumerate(q32)):0{128*8}x}\n')
  for key in range(KEYS):
   kval=[]
   for group in range(GROUPS):
    i=(row*KEYS+key)*GROUPS+group; code=metas[i]&255;shift=(metas[i]>>8)&63
    scale=code/(1<<shift) if code else 0.0
    kval.extend(float(v)*scale for v in keys12[i])
   k16=[bits16(x) for x in kval];k32=[bits32(x) for x in kval]
   fs['key_fp16.mem'].write(f'{sum(x<<(i*16) for i,x in enumerate(k16)):0{128*4}x}\n')
   fs['key_fp32.mem'].write(f'{sum(x<<(i*32) for i,x in enumerate(k32)):0{128*8}x}\n')
   # Complete QK row semantics: 128 products, reduction, head scale,
   # conversion to common S20 Q6.14 and the production explicit +/-16 clip.
   # FP16 baseline uses half products promoted to FP32 before reduction.
   # Pure half accumulation overflows on the retained extreme row.
   products=[]
   kval16=[float(ftz16(np.float16(x))) for x in kval]
   for qi,ki in zip(sum(queries[row*GROUPS:(row+1)*GROUPS],[]),kval16):
    # The RTL uses the exactly rounded half head scale 0x2da8.
    qscaled=op16(np.float16(qi/(1<<16)),np.float16(HEAD_SCALE_Q16/(1<<16)),lambda a,b:a*b)
    products.append(np.float32(ftz16(op16(qscaled,np.float16(ki),lambda a,b:a*b))))
   # Match the seven-level 128-input hardware reduction tree.
   while len(products)>1:
    products=[np.float32(products[i]+products[i+1]) for i in range(0,len(products),2)]
   acc16=products[0]
   raw16=int(np.rint(float(acc16)*(1<<14)))
   s16=clip(raw16)
   qv=np.asarray(sum(queries[row*GROUPS:(row+1)*GROUPS],[]),dtype=np.float32)/np.float32(1<<16)
   kv=np.asarray(kval,dtype=np.float32)
   products32=list(np.float32(qv*kv))
   while len(products32)>1:
    products32=[np.float32(products32[i]+products32[i+1]) for i in range(0,len(products32),2)]
   acc32=products32[0]
   y32=np.float32(acc32*np.float32(HEAD_SCALE_Q16/(1<<16)))
   raw32=int(np.rint(float(y32)*(1<<14)))
   s32=clip(raw32)
   f16clips+=raw16!=s16;f32clips+=raw32!=s32
   fs['expected_fp16.mem'].write(f'{s16&0xfffff:05x}\n')
   fs['expected_fp32.mem'].write(f'{s32&0xfffff:05x}\n')
   fs['mask.mem'].write(f'{masks[row*KEYS+key]:01x}\n')
finally:
 [f.close() for f in fs.values()]
m={"schema":"m7_matched_qk_v1","rows":ROWS,"keys_per_row":KEYS,"head_dim":128,
   "common_output":"signed S20 Q6.14 with explicit +/-16 score clip","fp16_clip_count":f16clips,
   "fp32_clip_count":f32clips,"head_scale_fixed":HEAD_SCALE_Q16/(1<<16),
   "head_scale_fp16":float(np.float16(HEAD_SCALE_Q16/(1<<16))),
   "fp16_accumulator":"head-scale in FP16, FP16 products converted to FP32, FP32 reduction"}
(OUT/'manifest.json').write_text(json.dumps(m,indent=2,sort_keys=True)+'\n')
print('M7_VECTOR_JSON:',json.dumps(m,sort_keys=True))
