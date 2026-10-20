"""R010 actual GPU conformance against original arithmetic and independent CPU Fraction."""
import numpy as np
from r010_audit_cpu import oracle_one,cpu_qualification

def gpu_qualification():
    import torch
    from numerical_reference.model_compat import production_module
    from numerical_reference.gpu_reference import grouped_linear_exact
    from r010_audit_kernels import capture
    v5=production_module();rng=np.random.default_rng(2026102010);count=0;histchecks=0
    for attention in [True,False]:
        rows,cols,groups=3,17,3
        av=rng.integers(0,256,(rows,groups,32),dtype=np.uint8);zp=rng.integers(0,256,(rows,groups),dtype=np.uint8)
        ac=rng.integers(1,256,(rows,groups),dtype=np.uint8);ash=np.tile(np.array([13,15,63] if attention else [6,15,63],dtype=np.uint8),(rows,1));ac[:,-1]=0
        w=rng.integers(-127 if attention else -7,128 if attention else 8,(cols,groups,32),dtype=np.int8)
        wc=rng.integers(1,256,(cols,groups),dtype=np.uint8);wsh=np.tile(np.array([13,20,63] if attention else [6,20,63],dtype=np.uint8),(cols,1));wc[:,-1]=0
        # Positive/negative exact final ties; other groups inactive for these columns.
        av[0,0]=16;zp[0,0]=0;ac[0,0]=1
        w[0,0]=1;w[1,0]=-1;wc[:2,0]=1;wc[:2,1]=0
        audit=v5.V5Audit(torch.device('cuda:0'))
        module=v5.V5ProductionLinear(module_name='qualification.'+('o_proj' if attention else 'down_proj'),op_name='o_proj' if attention else 'down_proj',weight_s8=w,weight_codes_u8=wc,weight_shifts_u8=wsh,input_width=24 if attention else 32,hadamard_width=27 if attention else 35,output_width=24 if attention else 32,device=torch.device('cuda:0'),audit=audit,strict_total_shift=True,software_extended=False,down_shift12_candidate=not attention)
        act=v5.PreparedActivation(*(torch.from_numpy(x).cuda() for x in [av,ac,ash,zp]),leading_shape=(1,rows))
        observed=capture(act,module);original=module.project_prepared(act)
        assert torch.equal(original.reshape(rows,cols),observed['current_code'])
        refs=[torch.zeros((),device='cuda:0',dtype=torch.int64) for _ in range(5)]
        reference=grouped_linear_exact(act,module.weight_s8,module.weight_codes_u8,module.weight_shifts_u8,26 if attention else 12,47 if attention else 44,42 if attention else 54,42 if attention else 54,42 if attention else 45,True,False,*refs,output_min=-(1<<(module.output_width-1)),output_max=(1<<(module.output_width-1))-1)
        assert torch.equal(reference.reshape(rows,cols),observed['reference_code'])
        got={k:v.cpu().numpy() for k,v in observed.items() if isinstance(v,torch.Tensor)}
        hist=np.zeros(32,dtype=np.int64);lost=np.zeros_like(hist);ones=0;guardover=0;accover=0;sat=0;refsat=0
        for i in range(rows):
            for j in range(cols):
                oracle=oracle_one(av[i],w[j],ac[i],ash[i],zp[i],wc[j],wsh[j],attention)
                for key in ['accumulator','current_code','reference_code','exact_quotient','exact_remainder']:assert int(got[key][i,j])==oracle[key],(attention,i,j,key,int(got[key][i,j]),oracle[key])
                hist+=oracle['active_shift_hist'];lost+=oracle['nonzero_remainder_hist'];ones+=oracle['discarded_one_bits'];guardover+=oracle['software_group_guard_overflow'];accover+=oracle['accumulator_overflow'];sat+=oracle['saturation'];refsat+=oracle['reference_saturation'];count+=1
        assert np.array_equal(hist,got['active_shift_hist']) and np.array_equal(lost,got['nonzero_remainder_hist']) and ones==int(got['discarded_one_bits'])
        counters=[int(x.item()) for x in observed['counters']]
        assert counters==[sat,0,guardover,accover,accover],(attention,counters,sat,guardover,accover)
        assert int(observed['reference_saturation'])==refsat
        histchecks+=1
    return dict(passed=True,scalar_fraction_checks=count,whole_histogram_and_discarded_onebit_checks=histchecks,original_output_parity=True,independent_reference_parity=True,inactive_shift126=True,positive_negative_ties=True,saturation_and_counter_comparison=True)
