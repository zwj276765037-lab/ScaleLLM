"""CPU-independent exact arithmetic checks and R010 scalar metric definitions."""
from fractions import Fraction
import math
import numpy as np
THRESHOLDS=[('0.1',1000),('1',100),('5',20),('10',10)]

def away_fraction(x):
    sign=1 if x>=0 else -1;y=abs(x)
    return sign*((2*y.numerator+y.denominator)//(2*y.denominator))

def oracle_one(a,w,ac,ash,zp,wc,wsh,attention):
    aw,gw=(42,42) if attention else (54,45);low,high=(26,47) if attention else (12,44);outwidth=24 if attention else 32
    acc=0;exact=Fraction(0);hist=[0]*32;losthist=[0]*32;ones=0;guardover=0;accover=0
    for g in range(len(ac)):
        dot=sum((int(x)-int(zp[g]))*int(y) for x,y in zip(a[g],w[g]));raw=dot*int(ac[g])*int(wc[g]);s=int(ash[g])+int(wsh[g]);active=int(ac[g])!=0 and int(wc[g])!=0
        right=max(s-24,0);left=max(24-s,0);aligned=(raw>>right)<<left
        if active:
            hist[right]+=1;rem=raw-((raw>>right)<<right);losthist[right]+=int(rem!=0);ones+=rem.bit_count()
            exact+=Fraction(raw,1<<s)
            guardover+=int(not -(1<<(gw-1))<=aligned<(1<<(gw-1)))
        guard=0 if active and not low<=s<=high else aligned
        nxt=acc+guard;accover+=int(not -(1<<(aw-1))<=nxt<(1<<(aw-1)));acc=((nxt+(1<<(aw-1)))&((1<<aw)-1))-(1<<(aw-1))
    rounded=away_fraction(Fraction(acc,256));code=min(max(rounded,-(1<<(outwidth-1))),(1<<(outwidth-1))-1)
    x=exact*(1<<16);q=x.numerator//x.denominator;r=(x-q)*(1<<(high-16));assert r.denominator==1
    refround=away_fraction(x);ref=min(max(refround,-(1<<(outwidth-1))),(1<<(outwidth-1))-1)
    return dict(accumulator=acc,current_code=code,reference_code=ref,exact_quotient=q,exact_remainder=int(r),exact=exact,active_shift_hist=hist,nonzero_remainder_hist=losthist,discarded_one_bits=ones,software_group_guard_overflow=guardover,accumulator_overflow=accover,saturation=int(code!=rounded),reference_saturation=int(ref!=refround))

def cpu_qualification():
    n=0
    for bits in [0,1,2,8,20,23]:
        for x in list(range(-400,401))+[-(1<<40)+129,(1<<40)-129]:
            q=x>>bits;r=x-(q<<bits);assert 0<=r<(1<<bits)
            assert Fraction(q)+Fraction(r,1<<bits)==Fraction(x,1<<bits)
            expected=away_fraction(Fraction(x,1<<bits))
            got=(1 if x>=0 else -1)*((abs(x)+(1<<(bits-1)))>>bits) if bits else x
            assert got==expected;n+=1
    for width in [24,32,42,45,54]:
        for x in [-2**(width+1)-1,-2**(width-1)-1,-2**(width-1),-1,0,1,2**(width-1)-1,2**(width-1),2**(width+1)+1]:
            wrapped=((x+2**(width-1))&((1<<width)-1))-2**(width-1)
            assert -(1<<(width-1))<=wrapped<(1<<(width-1)) and (wrapped-x)%(1<<width)==0
            sat=max(-(1<<(width-1)),min(x,(1<<(width-1))-1));assert -(1<<(width-1))<=sat<(1<<(width-1));n+=1
    # Exact threshold behavior, negative denominator and zero denominator closure.
    ans=metric_from_integers(np.array([1000,-1000,0,0]),np.array([1,2,0,5]),1)
    assert ans['relative_thresholds']['0.1']['count']==1 and ans['zero_original_current_nonzero']==1
    return dict(passed=True,integer_fraction_cases=n,zero_denominator_and_strict_threshold_passed=True,cuda_initialized=False)

def metric_from_integers(before_num,difference_num,denominator):
    """Exact integer pointwise relative thresholds; FP64 decoded magnitudes/energy."""
    before_num=np.asarray(before_num,dtype=np.int64).reshape(-1);difference_num=np.asarray(difference_num,dtype=np.int64).reshape(-1)
    absn=np.abs(before_num);absd=np.abs(difference_num);nz=absn!=0
    assert len(absn)==len(absd) and (absn>=0).all() and (absd>=0).all()
    assert int(absd.max(initial=0))<=np.iinfo(np.int64).max//1000
    before=before_num.astype(np.float64)/denominator;diff=difference_num.astype(np.float64)/denominator;absolute=np.abs(diff)
    energy=float(np.dot(diff,diff));signal=float(np.dot(before,before));rms=math.sqrt(signal/len(before))
    rel=np.zeros(len(before),dtype=np.float64);rel[nz]=absd[nz].astype(np.float64)/absn[nz]
    quant=[.5,.9,.95,.99,.999,1.]
    result=dict(count=len(before),original_nonzero=int(nz.sum()),zero_original_current_zero=int(((~nz)&(absd==0)).sum()),zero_original_current_nonzero=int(((~nz)&(absd!=0)).sum()),changed_count=int((absd!=0).sum()),absolute_mean=float(absolute.mean()),absolute_rmse=math.sqrt(energy/len(before)),absolute_max=float(absolute.max(initial=0)),signed_mean=float(diff.mean()),error_energy=energy,signal_energy=signal,reference_rms=rms,pooled_relative_l2_percent=100*math.sqrt(energy/signal) if signal else None,absolute_quantiles={str(q):float(np.quantile(absolute,q)) for q in quant},relative_quantiles_percent={str(q):float(100*np.quantile(rel[nz],q)) for q in quant} if nz.any() else None,relative_thresholds={},rms_normalized_thresholds={})
    for label,den in THRESHOLDS:
        mask=nz&(absd*den>absn);rmsmask=absolute>rms/den
        result['relative_thresholds'][label]=dict(count=int(mask.sum()),nonzero_original_denominator=int(nz.sum()),percent_of_nonzero=100*float(mask.sum())/int(nz.sum()) if nz.any() else None,error_energy=float(np.dot(diff[mask],diff[mask])),error_energy_share_percent=100*float(np.dot(diff[mask],diff[mask]))/energy if energy else 0.)
        result['rms_normalized_thresholds'][label]=dict(count=int(rmsmask.sum()),all_output_denominator=len(before),percent=100*float(rmsmask.mean()),error_energy_share_percent=100*float(np.dot(diff[rmsmask],diff[rmsmask]))/energy if energy else 0.)
    return result

def comparisons(arrays,bits):
    a=arrays['accumulator'].astype(np.int64);current=arrays['current_code'].astype(np.int64);ref=arrays['reference_code'].astype(np.int64);q=arrays['exact_quotient'];r=arrays['exact_remainder'].astype(np.int64)
    rounded=np.where(a>=0,(a+128)>>8,-(((-a)+128)>>8))
    assert np.max(np.abs(q))<((1<<63)-1)//(1<<bits)-1
    num=q*(1<<bits)+r
    return {'final_cut8':(a,rounded*256-a,1<<24),'total_rounding':(num,current*(1<<bits)-num,1<<(bits+16)),'additional_intermediate':(ref,current-ref,1<<16),'saturation':(rounded,current-rounded,1<<16)}
