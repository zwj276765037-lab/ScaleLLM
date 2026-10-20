"""Independent integer/Fraction CPU oracle and GPU conformance for R007."""
from __future__ import annotations
import random
from fractions import Fraction
from types import SimpleNamespace


def oracle(x,s):
    if s<=0:return x << -s
    return round(Fraction(x,1<<s))


def scalar(x,s):
    if s<=0:return x << -s
    q=x >> s;r=x-(q << s);h=1 << (s-1)
    return q+int(r>h or (r==h and (q&1)))


def cpu_tests():
    cases=[(x,s) for s in range(-3,25) for x in range(-300,301)]
    for s in [1,2,8,23,24,40,61,62]:
        for q in [-33,-32,-3,-2,-1,0,1,2,3,31,32]:
            for offset in [-1,0,1]:
                x=q*(1<<s)+(1<<(s-1))+offset
                if -(1<<63)<=x<(1<<63):cases.append((x,s))
    for x,s in cases:assert scalar(x,s)==oracle(x,s),(x,s)
    # Width wrapping and final half-away/saturation are independently exact.
    for width in [9,37,42,44,45,54]:
        lo=-(1<<(width-1));hi=(1<<(width-1))-1;mask=(1<<width)-1
        for x in [lo-1,lo,lo+1,-1,0,1,hi-1,hi,hi+1]:
            wrapped=((x-lo)&mask)+lo
            assert lo<=wrapped<=hi
            assert wrapped==((x+(1<<(width-1)))%(1<<width))-(1<<(width-1))
    # Per-term RNE has no universal exit-rounding dominance: preserve a case.
    floor_codes=[126,0];rne_codes=[127,1]
    assert sum(floor_codes)==126 and sum(rne_codes)==128
    return dict(passed=True,oracle='Python Fraction round ties-to-even, independent of candidate implementation',scalar_cases=len(cases),widths=[9,37,42,44,45,54],inactive_shift102_policy='effective shift zero before arithmetic',pointwise_nonregression_guarantee=False)


def gpu_tests():
    import torch
    from candidate import _rne_vector,round_shift_even,grouped_linear_s24,_pv_s24
    from numerical_reference.model_compat import production_module
    v5=production_module();dev='cuda:0';rng=random.Random(2026102007)
    cases=[(x,s) for s in [-2,0,1,2,8,20,23,24,40,61,62] for x in [-1000001,-513,-512,-511,-257,-256,-255,-129,-128,-127,-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7,127,128,129,255,256,257,511,512,513,1000001]]
    for s in [1,8,20,23,24,40]:
        for q in [-3,-2,-1,0,1,2,3]:
            cases += [(q*(1<<s)+(1<<(s-1))+d,s) for d in [-1,0,1]]
    x=torch.tensor([a for a,b in cases],device=dev,dtype=torch.int64)
    s=torch.tensor([b for a,b in cases],device=dev,dtype=torch.int64)
    out=torch.empty_like(x);_rne_vector[(1,)](x,s,out,N=x.numel(),B=1024)
    expected=torch.tensor([oracle(a,b) for a,b in cases],dtype=torch.int64)
    assert torch.equal(out.cpu(),expected)
    assert torch.equal(round_shift_even(x,s).cpu(),expected)
    # Grouped geometry masks and signed integer correlations, inactive shift126.
    rows,cols,groups=3,5,4
    av=torch.tensor([rng.randrange(256) for _ in range(rows*groups*32)],dtype=torch.uint8).reshape(rows,groups,32)
    az=torch.tensor([rng.randrange(256) for _ in range(rows*groups)],dtype=torch.uint8).reshape(rows,groups)
    w=torch.tensor([rng.randrange(-127,128) for _ in range(cols*groups*32)],dtype=torch.int8).reshape(cols,groups,32)
    ac=torch.tensor([[0,127,91,31],[63,0,127,13],[1,127,0,127]],dtype=torch.uint8)
    wc=torch.tensor([[0,127,1,127],[127,0,127,1],[7,127,0,17],[127,127,127,0],[31,67,17,11]],dtype=torch.uint8)
    ash=torch.tensor([[63,13,20,22],[12,63,17,24],[19,20,63,23]],dtype=torch.uint8)
    wsh=torch.tensor([[63,13,20,25],[24,63,14,20],[13,21,63,20],[26,14,17,63],[12,23,24,24]],dtype=torch.uint8)
    a=SimpleNamespace(values_u8=av.to(dev),zero_points_u8=az.to(dev),codes_u8=ac.to(dev),shifts_u8=ash.to(dev),rows=rows,groups=groups,leading_shape=(rows,))
    results=[]
    for width,gwidth,zero_invalid,outlo,outhi in [(42,37,False,-8388608,8388607),(9,8,True,-2,2)]:
        expected_out=[];counts=[0,0,0,0,0]
        lo=-(1<<(width-1));hi=(1<<(width-1))-1
        glo=-(1<<(gwidth-1));ghi=(1<<(gwidth-1))-1
        for i in range(rows):
            line=[]
            for j in range(cols):
                acc=0
                for g in range(groups):
                    corr=sum((int(av[i,g,k])-int(az[i,g]))*int(w[j,g,k]) for k in range(32))
                    raw=corr*int(ac[i,g])*int(wc[j,g]);active=int(ac[i,g])!=0 and int(wc[j,g])!=0
                    delta=int(ash[i,g])+int(wsh[j,g])-24
                    aligned=oracle(raw,delta) if active else 0
                    over=active and not glo<=aligned<=ghi
                    counts[1]+=int(over);counts[2]+=int(over)
                    guard=0 if zero_invalid and active and not 26<=delta+24<=47 else aligned
                    nxt=acc+guard;overflow=not lo<=nxt<=hi
                    counts[3]+=int(overflow);counts[4]+=int(overflow)
                    acc=((nxt-lo)&((1<<width)-1))+lo
                rounded=(acc+128)//256 if acc>=0 else -((-acc+128)//256)
                sat=max(outlo,min(outhi,rounded));counts[0]+=int(sat!=rounded);line.append(sat)
            expected_out.append(line)
        counters=[torch.zeros((),device=dev,dtype=torch.int64) for _ in range(5)]
        out=grouped_linear_s24(a,w.to(dev),wc.to(dev),wsh.to(dev),26,47,width,width,gwidth,zero_invalid,True,*counters,output_min=outlo,output_max=outhi)
        assert torch.equal(out.cpu(),torch.tensor(expected_out,dtype=torch.int32)),(out.cpu(),expected_out)
        actual=[int(c.item()) for c in counters]
        assert actual==counts,(actual,counts)
        results.append(dict(accumulator_width=width,guard_width=gwidth,zero_invalid=zero_invalid,counts=counts))
    # PV exact Fraction oracle, positive/negative ties and inactive code63 shifts.
    prob=torch.tensor([[[[1,128,255],[65535,1,128]]]],device=dev,dtype=torch.int64)
    values=torch.tensor([rng.randrange(-2048,2048) for _ in range(1*3*1*4*32)],dtype=torch.int64).reshape(1,3,1,4,32)
    codes=torch.tensor([[[[127,31,1,0]],[[1,127,0,17]],[[19,1,127,31]]]],dtype=torch.uint8)
    shifts=torch.tensor([[[[8,9,32,63]],[[16,24,63,8]],[[9,17,24,32]]]],dtype=torch.uint8)
    kv=SimpleNamespace(values_s12=values.to(dev),codes_u8=codes.to(dev),shifts_u8=shifts.to(dev))
    audit=v5.V5Audit(torch.device(dev));actual=_pv_s24(prob,kv,1,audit).cpu()
    expected=torch.zeros((1,1,2,128),dtype=torch.int32)
    for q in range(2):
        for g in range(4):
            for k in range(32):
                accum=0
                for t in range(3):
                    code=int(codes[0,t,0,g]);shift=int(shifts[0,t,0,g])-8 if code else 0
                    accum+=oracle(int(prob[0,0,q,t])*int(values[0,t,0,g,k])*code,shift)
                rounded=(accum+128)//256 if accum>=0 else -((-accum+128)//256)
                expected[0,0,q,g*32+k]=max(-8388608,min(8388607,rounded))
    assert torch.equal(actual,expected)
    torch.cuda.synchronize()
    return dict(passed=True,vector_cases=len(cases),linear_outputs=rows*cols*2,linear_fixtures=results,pv_outputs=256,all_equal_independent_cpu=True,negative_ties=True,inactive_linear_shift126=True,inactive_pv_shift63=True)
