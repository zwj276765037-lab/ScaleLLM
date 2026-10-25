#!/usr/bin/env python3
"""Independent arbitrary-integer full-K gold for the M006 production TB.
Only materializes reference evidence; never alters TB or production files.
"""
from pathlib import Path
import hashlib,json,os,platform,resource,sys,time
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
TB=ROOT/'project/hardware/tb/hap_attention_mlp_linear_integration_tb.sv'

def scalar(op,co,m,r,c):
    acc=0
    for g in range(128 if op==1 else 448):
        dot=sum(((3*g+5*r+7*k+11*co)%31-15)*((7*g+3*c+5*m+11*k)%16-8) for k in range(32))
        raw=dot*(1+r%7+co)*(1+(c+g+m)%7)
        shift=(10 if op==1 else 6)+(g+r)%2+(10 if op==1 else 6)+10*(c%3)+g%2
        acc += raw << (24-shift) if shift<=24 else raw >> (shift-24)
    rounded=(acc+128)>>8 if acc>=0 else -((-acc+128)>>8)
    bits=24 if op==1 else 32
    return acc,max(-(1<<(bits-1)),min((1<<(bits-1))-1,rounded))

def main():
    started=time.monotonic();cpus=sorted(os.sched_getaffinity(0))[:8];os.sched_setaffinity(0,cpus)
    available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
    assert available>=64*1024**3
    values=[];table=bytearray();rows=[]
    for co in range(2):
        for m in range(2):
            for r in range(16):
                data=bytearray()
                for c in range(128):
                    acc,value=scalar(1,co,m,r,c)
                    values.append(dict(op=1,cohort=co,matrix=m,row=r,col=c,guard_sum=acc,value=value))
                    data+=value.to_bytes(3,'little',signed=True)
                table+=data;rows.append(f"  frozen_gu_rows[{(co*2+m)*16+r}]=3072'h{int.from_bytes(data,'little'):0768x};")
    for co in range(2):
        for r in range(16):
            data=bytearray()
            for c in range(64):
                acc,value=scalar(2,co,0,r,c)
                values.append(dict(op=2,cohort=co,matrix=0,row=r,col=c,guard_sum=acc,value=value))
                data+=value.to_bytes(4,'little',signed=True)
            table+=data;rows.append(f"  frozen_down_rows[{co*16+r}]=2048'h{int.from_bytes(data,'little'):0512x};")
    spots=[((1,0,0,0,0),44916,175),((1,1,1,15,127),-576,-2),((1,0,1,10,125),-58,0),((2,0,0,0,0),-26638336,-104056),((2,1,0,15,63),1247232,4872),((2,1,0,10,62),-161,-1)]
    spot_results=[]
    for coordinate,acc_expected,value_expected in spots:
        acc,value=scalar(*coordinate)
        assert (acc,value)==(acc_expected,value_expected)
        spot_results.append(dict(coordinate=coordinate,guard_sum=acc,value=value,pass_check=True))
    (OUT/'all_values.json').write_text(json.dumps(values,separators=(',',':'))+'\n')
    (OUT/'gold_words.bin').write_bytes(table)
    (OUT/'gold_rows.svtext').write_text('\n'.join(rows)+'\n')
    source=TB.read_text()
    assert len(values)==10240 and len(table)==32768 and all(line in source for line in rows)
    manifest=dict(python=sys.version,platform=platform.platform(),command=[sys.executable,'-B',str(Path(__file__).resolve())],cwd=str(ROOT),cpu_affinity=cpus,mem_available_before_bytes=available,elapsed_seconds=time.monotonic()-started,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),tb_sha256=hashlib.sha256(TB.read_bytes()).hexdigest(),value_count=10240,group_count=1966080,lane_products=62914560,embedded_rows_match=True,six_literals=spot_results,exit_code=0,scope='Independent CPU reference generation only; no explanation of failing SV implementation, no RTL result',outputs_sha256={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['all_values.json','gold_words.bin','gold_rows.svtext']})
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__': main()
