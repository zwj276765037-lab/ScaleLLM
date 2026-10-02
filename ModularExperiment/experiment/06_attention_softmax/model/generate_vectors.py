#!/usr/bin/env python3
from __future__ import annotations
import json,struct
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;SRC=Path('/home/user/EDA-202/zhuowenjun/ScaleLLM/data/softmax_row_128');OUT=HERE.parent/'data';N=32*128
def bits32(x):return struct.unpack('<I',struct.pack('<f',float(np.float32(x))))[0]
def bits16(x):return int(np.float16(x).view(np.uint16))
def sx(x,w):return x-(1<<w) if x&(1<<(w-1)) else x
lines=(SRC/'input.mem').read_text().splitlines();inp=[int(x,16) for x in lines];OUT.mkdir(parents=True,exist_ok=True)
f16=[];f32=[];mask=[];p16=[];p32=[];sumerr16=[];sumerr32=[]
for r in range(32):
 vals=[sx(inp[r*128+i]&0xfffff,20)/(1<<14) for i in range(128)];ms=[(inp[r*128+i]>>20)&1 for i in range(128)];mask+=ms
 a=np.asarray(vals,dtype=np.float64);visible=np.asarray([not x for x in ms]);m=a[visible].max()
 e32=np.zeros(128,dtype=np.float32);e32[visible]=np.exp(np.float32(a[visible]-m),dtype=np.float32);q32=e32/np.float32(e32.sum(dtype=np.float32))
 e16=np.zeros(128,dtype=np.float16);e16[visible]=np.exp(np.asarray(a[visible]-m,dtype=np.float16)).astype(np.float16);s16=np.float16(0)
 for x in e16:s16=np.float16(s16+x)
 q16=np.asarray([np.float16(x/s16) for x in e16],dtype=np.float16)
 p32.extend(min(65535,max(0,int(np.rint(float(x)*65536)))) for x in q32);p16.extend(min(65535,max(0,int(np.rint(float(x)*65536)))) for x in q16)
 sumerr32.append(abs(sum(p32[-128:])-65536));sumerr16.append(abs(sum(p16[-128:])-65536));f32+=list(map(bits32,vals));f16+=list(map(bits16,vals))
def write(n,a,w): (OUT/n).write_text(''.join(f'{x:0{w}x}\n' for x in a))
write('score_fp16.mem',f16,4);write('score_fp32.mem',f32,8);write('mask.mem',mask,1);write('expected_fp16.mem',p16,4);write('expected_fp32.mem',p32,4)
m={'schema':'m8_matched_softmax_v1','rows':32,'keys':128,'common_output':'U16 probability','fp16_max_sum_error':max(sumerr16),'fp32_max_sum_error':max(sumerr32)};(OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print('M8_VECTOR_JSON:',json.dumps(m,sort_keys=True))
