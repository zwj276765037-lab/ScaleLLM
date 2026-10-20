"""CPU-only independent R009 formula/context checks; no production writes."""
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace
from datetime import datetime,timezone
import hashlib,json,random,sys
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
S=ROOT/'project/software/0_Software/rounding_precision/experiment'
OUT=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R009/independent_review'

def identity(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
def gold_away(x):
    a=abs(x);m,r=divmod(a.numerator,a.denominator)
    return (-1 if x<0 else 1)*(m+(2*r>=a.denominator))
def main():
    start=datetime.now(timezone.utc).isoformat();rng=random.Random(90315);n=0;negative_halves=0
    # Independent exact real sums versus the GPU reference's q/r construction.
    for low,high,G in [(26,47,128),(12,44,448)]:
      for b in (0,2,4):
       F=16+b;K=high-F;D=1<<K
       for trial in range(200):
        qsum=rsum=0;gold=Fraction(0)
        for g in range(G if trial<4 else rng.randrange(1,12)):
         active=rng.randrange(8)!=0
         raw=rng.randrange(-67386708000,67386708001) if active else 0
         total=rng.randint(low,high) if active else 126
         k=total-F if active else 0
         right=max(k,0);left=max(-k,0)
         q=(raw>>right)<<left
         residue=raw-((raw>>right)<<right) if k>0 else 0
         qsum+=q;rsum+=residue<<(K-right)
         gold+=Fraction(raw,1<<max(k,0))*(1<<max(-k,0))
        qsum+=rsum>>K;rsum&=D-1
        got=qsum+int(2*rsum>=D if qsum>=0 else 2*rsum>D)
        assert Fraction(qsum)+Fraction(rsum,D)==gold
        assert got==gold_away(gold)
        n+=1
       for q in range(-20,21):
        for r in (0,D//2-1,D//2,D//2+1,D-1):
         got=q+int(2*r>=D if q>=0 else 2*r>D)
         assert got==gold_away(Fraction(q*D+r,D));n+=1
         negative_halves+=int(q<0 and r==D//2)
    import torch
    torch.set_num_threads(1)
    assert not torch.cuda.is_initialized()
    sys.path[:0]=[str(S),str(S/'rounding_optimization')]
    import r009_lastlayer_kernels_v2 as k
    original_candidate=k.grouped_linear_wide;original_ref=k.grouped_linear_wide_reference
    calls=[]
    def selected(*args,extra_bits,**kwargs):
        calls.append((extra_bits,kwargs['output_max']))
        return torch.tensor([kwargs['output_max']-124],dtype=torch.int64)
    k.grouped_linear_wide=selected;k.grouped_linear_wide_reference=selected
    def baseline(*args,**kwargs):return torch.tensor([12345],dtype=torch.int64)
    fake=SimpleNamespace(grouped_linear_s24=baseline)
    class Linear:
        def __init__(self,w):self.output_width=w
        def project_prepared(self,x):
            return fake.grouped_linear_s24(output_min=-(1<<(self.output_width-1)),output_max=(1<<(self.output_width-1))-1)
    class Attention:
        def __init__(self):self.o_proj=Linear(24);self.output_dtype=torch.float32
        def forward(self,x):return self.o_proj.project_prepared(x).float()/65536,torch.tensor(7.),None
    class MLP:
        def __init__(self):self.down_proj=Linear(32);self.output_dtype=torch.float32
        def forward(self,x):return self.down_proj.project_prepared(x).float()/65536
    att=Attention();mlp=MLP();model=SimpleNamespace(model=SimpleNamespace(layers=[None]*31+[SimpleNamespace(self_attn=SimpleNamespace(core=att),mlp=mlp)]))
    objects=[att,att.o_proj,mlp,mlp.down_proj];before=[o.__dict__.copy() for o in objects]
    contexts=0
    try:
      for b in (2,4):
       for reference in (False,True):
        for fail in (False,True):
         events=[]
         try:
          with k.lastlayer_exit_context(fake,model,b,reference=reference,events=events):
           assert att.o_proj.output_width==24+b and mlp.down_proj.output_width==32+b
           a=att.forward(None);m=mlp.forward(None)
           ar=torch.tensor([(1<<(24+b-1))-1-124],dtype=torch.int64)
           mr=torch.tensor([(1<<(32+b-1))-1-124],dtype=torch.int64)
           assert torch.equal(a[0],ar.float()/(1<<(16+b)))
           assert torch.equal(m,mr.float()/(1<<(16+b)))
           assert a[1].item()==7 and a[2] is None
           assert len(events)==4 and sum(e['kind']=='host_scale' for e in events)==2
           assert fake.grouped_linear_s24().item()==12345 # unselected global call unchanged
           if fail:raise ValueError('intentional context exit failure')
         except ValueError:
          assert fail
         assert all(o.__dict__==d for o,d in zip(objects,before))
         assert fake.grouped_linear_s24 is baseline and not hasattr(fake,'_r009_exit_overlay_active')
         contexts+=1
    finally:k.grouped_linear_wide=original_candidate;k.grouped_linear_wide_reference=original_ref
    assert not torch.cuda.is_initialized()
    attempt=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36'
    manifest=json.loads((attempt/'manifest.json').read_text())
    paths=[S/'rounding_optimization'/name for name in ('r009_lastlayer_kernels_v2.py','r009_qualification_v3.py','r009_run_lastlayer_precision_v3.py')]
    frozen={r['path']:r['sha256'] for r in manifest['source']}
    assert all(identity(p)['sha256']==frozen[str(p)] for p in paths)
    result={'execution_state':'completed','scope':'CPU-only independent q/r Fraction and actual-context checks; no GPU/model forward','started_at':start,'ended_at':datetime.now(timezone.utc).isoformat(),'reference_formula_cases':n,'negative_half_cases':negative_halves,'formula_mismatches':0,'actual_context_cases':contexts,'int64_wide_codes':True,'host_scale_once_aux_unchanged':True,'unselected_dispatch_unchanged':True,'exact_instance_dictionary_and_function_restoration':True,'exception_restoration':True,'cuda_initialized':False,'source_matches_AT003_manifest':True,'sources':[identity(p) for p in paths],'script':identity(Path(__file__))}
    (OUT/'A015_implementation_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
