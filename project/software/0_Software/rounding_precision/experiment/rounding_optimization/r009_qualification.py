"""Independent Python integer/Fraction oracles and R009 CPU/GPU conformance."""
from fractions import Fraction
from types import SimpleNamespace
import random


def away_fraction(x):
    q,r=divmod(x.numerator,x.denominator)
    return q+int(2*r>=x.denominator if q>=0 else 2*r>x.denominator)


def align(raw,total,f):
    d=total-f
    return (raw>>max(d,0))<<max(-d,0)


def oracle(correlations,ac,wc,ash,wsh,b,shift_min,shift_max,guard_width,acc_width,output_width,output_limits=None):
    lo=-(1<<(acc_width+b-1));hi=(1<<(acc_width+b-1))-1;acc=0;counts=[0,0,0,0,0];fraction=Fraction(0)
    for corr,a,w,sa,sw in zip(correlations,ac,wc,ash,wsh):
        raw=corr*a*w;active=a!=0 and w!=0;total=sa+sw
        term=align(raw,total,24+b) if active else 0
        outside=active and not -(1<<(guard_width+b-1))<=term<(1<<(guard_width+b-1))
        counts[1]+=int(outside);counts[2]+=int(outside)
        guard=0 if active and not shift_min<=total<=shift_max else term
        nxt=acc+guard;over=not lo<=nxt<=hi;counts[3]+=int(over);counts[4]+=int(over)
        acc=((nxt-lo)&((1<<(acc_width+b))-1))+lo
        if active:fraction+=Fraction(raw,1<<max(total-(16+b),0))*(1<<max(16+b-total,0))
    rounded=(acc+128)//256 if acc>=0 else -((-acc+128)//256)
    outlo,outhi=output_limits or (-(1<<(output_width+b-1)),(1<<(output_width+b-1))-1)
    code=max(outlo,min(outhi,rounded));counts[0]=int(code!=rounded)
    exact=max(outlo,min(outhi,away_fraction(fraction)))
    return code,counts,exact


def cpu_tests():
    import torch
    from r009_lastlayer_kernels import lastlayer_exit_context,interface_signature
    rng=random.Random(2026102009);n=0
    for b in [0,2,4]:
        for total in range(12,48):
            for raw in [-2**35,-65537,-65536,-32769,-257,-256,-255,-129,-128,-127,-1,0,1,127,128,129,255,256,257,32769,65536,65537,2**35]:
                got=align(raw,total,24+b)
                f=Fraction(raw,1<<max(total-(24+b),0))*(1<<max(24+b-total,0))
                assert got==f.numerator//f.denominator;n+=1
        for integer in [-(1<<35),-(1<<31)-1,-3,-2,-1,0,1,2,3,(1<<31)+1,(1<<35)-1]:
            for rem in [-129,-128,-127,-1,0,1,127,128,129]:
                acc=integer*256+rem
                got=(acc+128)//256 if acc>=0 else -((-acc+128)//256)
                assert got==away_fraction(Fraction(acc,256));n+=1
    class Linear:
        def __init__(self,w):self.output_width=w
        def project_prepared(self,x):return x
    class Attention:
        def __init__(self):self.o_proj=Linear(24);self.output_dtype=torch.float32
        def forward(self,x):return x,torch.tensor(7.),None
    class MLP:
        def __init__(self):self.down_proj=Linear(32);self.output_dtype=torch.float32
        def forward(self,x):return x
    att=Attention();mlp=MLP();model=SimpleNamespace(model=SimpleNamespace(layers=[None]*31+[SimpleNamespace(self_attn=SimpleNamespace(core=att),mlp=mlp)]));fake=SimpleNamespace(grouped_linear_s24=object());before=interface_signature(model);grouped=fake.grouped_linear_s24
    for b in [2,4]:
        for fail in [False,True]:
            try:
                with lastlayer_exit_context(fake,model,b,events=[]):
                    assert att.o_proj.output_width==24+b and mlp.down_proj.output_width==32+b
                    x=torch.tensor(float(1<<b),dtype=torch.float32);out=att.forward(x)
                    assert out[0].item()==1 and out[1].item()==7 and mlp.forward(x).item()==1
                    try:
                        with lastlayer_exit_context(fake,model,b):raise AssertionError('nested accepted')
                    except RuntimeError:pass
                    if fail:raise ValueError('intentional')
            except ValueError:pass
            assert interface_signature(model)==before and fake.grouped_linear_s24 is grouped
            assert not hasattr(fake,'_r009_exit_overlay_active')
    assert not torch.cuda.is_initialized()
    return dict(passed=True,integer_fraction_cases=n,host_scale_once_cases=4,attribute_and_binding_restoration=True,exception_restoration=True,nesting_rejected=True,reference_oracle='Independent Fraction sum and signed half-away',gpu_initialized=False)


def gpu_tests():
    import torch
    from r009_lastlayer_kernels import grouped_linear_wide,grouped_linear_wide_reference
    from numerical_reference.model_compat import production_module
    v5=production_module();device='cuda:0';rng=random.Random(2026102009);reports=[];beyond_int32=False;positive_above_s24=False
    for profile in ['attention','down','random']:
        rows,columns,groups=(1,1,1) if profile!='random' else (3,5,4)
        if profile=='attention':
            av=torch.full((rows,groups,32),255,dtype=torch.uint8);zp=torch.zeros((rows,groups),dtype=torch.uint8);wv=torch.full((columns,groups,32),127,dtype=torch.int8);ac=torch.full((rows,groups),63,dtype=torch.uint8);wc=torch.full((columns,groups),63,dtype=torch.uint8);ash=torch.full((rows,groups),13,dtype=torch.uint8);wsh=torch.full((columns,groups),13,dtype=torch.uint8);low,high,guard,acc,ow=26,47,42,42,24
        elif profile=='down':
            av=torch.full((rows,groups,32),127,dtype=torch.uint8);zp=torch.zeros((rows,groups),dtype=torch.uint8);wv=torch.full((columns,groups,32),4,dtype=torch.int8);ac=torch.full((rows,groups),63,dtype=torch.uint8);wc=torch.full((columns,groups),63,dtype=torch.uint8);ash=torch.full((rows,groups),6,dtype=torch.uint8);wsh=torch.full((columns,groups),6,dtype=torch.uint8);low,high,guard,acc,ow=12,44,45,54,32
        else:
            av=torch.tensor([rng.randrange(256) for _ in range(rows*groups*32)],dtype=torch.uint8).reshape(rows,groups,32);zp=torch.tensor([rng.randrange(256) for _ in range(rows*groups)],dtype=torch.uint8).reshape(rows,groups);wv=torch.tensor([rng.randrange(-127,128) for _ in range(columns*groups*32)],dtype=torch.int8).reshape(columns,groups,32);ac=torch.tensor([[0,127,91,31],[63,0,127,13],[1,127,0,127]],dtype=torch.uint8);wc=torch.tensor([[0,127,1,127],[127,0,127,1],[7,127,0,17],[127,127,127,0],[31,67,17,11]],dtype=torch.uint8);ash=torch.tensor([[63,13,20,22],[12,63,17,20],[19,20,63,23]],dtype=torch.uint8);wsh=torch.tensor([[63,13,20,25],[24,63,14,20],[13,21,63,20],[26,14,17,63],[12,23,24,24]],dtype=torch.uint8);ash=torch.where(ac!=0,ash.clamp(max=20),ash);wsh=torch.where(wc!=0,wsh.clamp(max=24),wsh);low,high,guard,acc,ow=12,44,45,54,32
        activation=SimpleNamespace(values_u8=av.to(device),zero_points_u8=zp.to(device),codes_u8=ac.to(device),shifts_u8=ash.to(device),rows=rows,groups=groups,leading_shape=(rows,))
        for b in [0,2,4]:
            counters=[torch.zeros((),device=device,dtype=torch.int64) for _ in range(5)];limits=(-(1<<(ow+b-1)),(1<<(ow+b-1))-1)
            args=(activation,wv.to(device),wc.to(device),wsh.to(device),low,high,acc,acc,guard,True,True,*counters)
            output=grouped_linear_wide(*args,output_min=limits[0],output_max=limits[1],extra_bits=b)
            expected=[];exact=[];counts=[0]*5
            for i in range(rows):
                line=[];eline=[]
                for j in range(columns):
                    corr=[sum((int(av[i,g,k])-int(zp[i,g]))*int(wv[j,g,k]) for k in range(32)) for g in range(groups)]
                    code,events,ref=oracle(corr,ac[i].tolist(),wc[j].tolist(),ash[i].tolist(),wsh[j].tolist(),b,low,high,guard,acc,ow)
                    line.append(code);eline.append(ref);counts=[x+y for x,y in zip(counts,events)]
                expected.append(line);exact.append(eline)
            assert output.dtype==torch.int64 and torch.equal(output.cpu(),torch.tensor(expected,dtype=torch.int64))
            assert [int(x.item()) for x in counters]==counts
            if b==0:
                original_counters=[torch.zeros((),device=device,dtype=torch.int64) for _ in range(5)]
                original=v5.grouped_linear_s24(*args[:11],*original_counters,output_min=limits[0],output_max=limits[1])
                assert torch.equal(original.cpu().to(torch.int64),output.cpu()) and [int(x.item()) for x in original_counters]==counts
            if profile!='random':
                ref_counters=[torch.zeros((),device=device,dtype=torch.int64) for _ in range(5)]
                ref=grouped_linear_wide_reference(*args[:11],*ref_counters,output_min=limits[0],output_max=limits[1],extra_bits=b)
                assert ref.dtype==torch.int64 and torch.equal(ref.cpu(),torch.tensor(exact,dtype=torch.int64))
            else:
                # random fixture uses supported (12,44) for the exact reference.
                ref_counters=[torch.zeros((),device=device,dtype=torch.int64) for _ in range(5)]
                refargs=(*args[:5],44,*args[6:11],*ref_counters)
                ref=grouped_linear_wide_reference(*refargs,output_min=limits[0],output_max=limits[1],extra_bits=b)
                assert torch.equal(ref.cpu(),torch.tensor(exact,dtype=torch.int64))
            if profile=='down' and b>0:beyond_int32|=bool((output.abs()>(1<<31)).any())
            if profile=='attention' and b>0:positive_above_s24|=bool((output>(1<<23)).any())
            reports.append(dict(profile=profile,b=b,outputs=rows*columns,counts=counts,expected=expected,independent_reference_fraction_equal=True))
    assert beyond_int32 and positive_above_s24
    torch.cuda.synchronize()
    return dict(passed=True,fixtures=reports,wide_output_beyond_int32=True,positive_s26_s28_above_s24=True,b0_original_raw_and_counter_parity=True,reference_fraction_oracle_equal=True)
