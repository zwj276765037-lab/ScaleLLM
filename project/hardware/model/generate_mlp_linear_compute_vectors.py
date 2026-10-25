#!/usr/bin/env python3
"""Independent integer projection oracle for bounded real-RTL tests.
No DUT counters, ordering internals, RTL imports or simulated values are read.
"""
import hashlib,json
from pathlib import Path
HW=Path(__file__).resolve().parents[1]
OUT=HW/'data/mlp_linear_compute'
def av(g,r,k):return (g*3+r*5+k*7)%31-15
def wv(g,c,m,k):return (g*7+c*3+m*5+k*11)%16-8
def project(op,m,r,c):
    groups=128 if op==1 else 448
    shift=(20 if op==1 else 12)+r%2+c%2
    guards=[];dots=[]
    for g in range(groups):
        dot=sum(av(g,r,k)*wv(g,c,m,k) for k in range(32))
        raw=dot*(r+1)*(1+c%7)
        guard=raw << (24-shift)
        assert -(1<<44)<=guard<(1<<44)
        dots.append(dot);guards.append(guard)
    aligned=sum(guards)
    rounded=-((-aligned+128)//256) if aligned<0 else (aligned+128)//256
    bits=24 if op==1 else 32
    value=max(-(1<<(bits-1)),min((1<<(bits-1))-1,rounded))
    return value,dots,guards

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inventory={}
    for op,columns,name in [(1,128,'gu128'),(2,32,'down32'),(2,64,'down64')]:
        bits=24 if op==1 else 32
        values=[]
        for m in range(2 if op==1 else 1):
            for r in range(16):
                for c in range(columns):values.append(project(op,m,r,c)[0])
        p=OUT/(name+'_gold.mem');p.write_text(''.join(f'{v&((1<<bits)-1):0{bits//4}x}\n' for v in values))
        inventory[name]=dict(path=str(p),count=len(values),bits=bits,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),min=min(values),max=max(values))
    value,dots,guards=project(1,0,0,0)
    assert value==-125 and sum(dots)==-1994 and sum(guards)==-31904
    (OUT/'oracle.json').write_text(json.dumps(dict(generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),formula='dot=sum_k(av*wv); guard=dot*(row+1)*(1+column%7)<<[24-total_shift]; sum all128/448 groups; half-away shift8; saturate S24/S32',first_gu_coordinate=dict(value=value,dots=dots,guards=guards,dot_sum=sum(dots),guard_sum=sum(guards)),vectors=inventory),indent=2)+'\n')
    print(json.dumps(inventory,indent=2))
if __name__=='__main__':main()
