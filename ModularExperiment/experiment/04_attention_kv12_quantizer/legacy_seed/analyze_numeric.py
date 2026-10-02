#!/usr/bin/env python3
"""Measure matched KV12/FP16-scale/FP32-scale KV16 reconstruction error."""
from __future__ import annotations
import json, struct
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
DATA=HERE.parents[2]/"HAP_new"/"data"/"kv12_quantizer"

def signed(v:int,w:int)->int:
    return v-(1<<w) if v&(1<<(w-1)) else v
def unpack(line:str,w:int,n:int)->list[int]:
    x=int(line,16);return [signed((x>>(i*w))&((1<<w)-1),w) for i in range(n)]
def f16(v:float)->float:return float(np.float16(v))
def f32(v:float)->float:return float(np.float32(v))

inputs=[unpack(x,24,32) for x in (DATA/"input_s24.mem").read_text().splitlines()]
q12=[unpack(x,12,32) for x in (DATA/"expected_s12.mem").read_text().splitlines()]
metas=[int(x,16) for x in (DATA/"expected_meta.mem").read_text().splitlines()]

def stats(kind:str)->dict:
    errors=[];clips=0
    for src,qv,meta in zip(inputs,q12,metas):
        if kind=="kv12":
            code=meta&255;shift=(meta>>8)&63
            rec=[round(q*code*(1<<16)/(1<<shift)) if code else 0 for q in qv]
        else:
            ma=max(abs(x) for x in src)
            ideal=(ma/32767.0)/(1<<16) if ma else 0.0
            stored=f16(ideal) if kind=="fp16" else f32(ideal)
            # Quantization uses the ideal max-derived scale; reconstruction
            # uses the physically stored IEEE metadata.
            qi=[int(np.floor(abs(x)*32767/ma+0.5))* (-1 if x<0 else 1) if ma else 0 for x in src]
            clips+=sum(abs(x)>32767 for x in qi)
            rec=[round(q*stored*(1<<16)) for q in qi]
        errors.extend(abs(a-b) for a,b in zip(src,rec))
    a=np.asarray(errors,dtype=np.float64)
    return {"case":kind,"samples":int(a.size),"mae_s24_lsb":float(a.mean()),
            "rmse_s24_lsb":float(np.sqrt(np.mean(a*a))),"max_abs_s24_lsb":int(a.max()),
            "clip_count":clips}

out={"schema":"m6_kv_numeric_v1","cases":[stats(x) for x in ("kv12","fp16","fp32")]}
(HERE/"artifacts"/"numeric.json").write_text(json.dumps(out,indent=2)+"\n")
print("M6_NUMERIC_JSON:",json.dumps(out,sort_keys=True))
