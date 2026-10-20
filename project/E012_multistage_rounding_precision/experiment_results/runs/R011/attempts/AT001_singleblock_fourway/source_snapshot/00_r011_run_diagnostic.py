"""R011 bounded single decoder31 replay and two conditional downstream cuts."""
from __future__ import annotations
import argparse,gc,hashlib,json,math,os,signal,subprocess,sys,threading,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;S=HERE.parent;ROOT=S.parents[4];sys.path.insert(0,str(S))
from r010_run_audit import now,write,append,identity,stage,free_gpu,ram_available,GPU,arrid

def metrics(a,b,mask=None):
    import numpy as np
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);assert a.shape==b.shape
    if mask is not None:a=a[mask];b=b[mask]
    delta=a-b;energy=float(np.sum(delta*delta));sig=float(np.sum(b*b));n=delta.size
    return dict(count=n,error_energy=energy,signal_energy=sig,current_signal_energy=float(np.sum(a*a)),absolute_rmse=math.sqrt(energy/n),reference_rms=math.sqrt(sig/n),relative_l2_percent=100*math.sqrt(energy/sig) if sig else None,max_absolute_error=float(np.max(np.abs(delta))),max_reference_magnitude=float(np.max(np.abs(b))),changed_count=int(np.count_nonzero(delta)))

def decompose(a,b,c):
    import numpy as np
    a=a.astype(np.float64);b=b.astype(np.float64);c=c.astype(np.float64);full=a-b;local=a-c;inherited=c-b;cross=2*float(np.sum(local*inherited));ef=float(np.sum(full*full));el=float(np.sum(local*local));ei=float(np.sum(inherited*inherited))
    return dict(total_error_energy=ef,same_input_local_error_energy=el,inherited_input_error_energy=ei,cross_term=cross,energy_identity_residual=ef-el-ei-cross,vector_identity_max_absolute=float(np.max(np.abs(full-local-inherited))),local_over_total_energy=el/ef if ef else None,inherited_over_total_energy=ei/ef if ef else None)

def residual(a,b,left,branch,out):
    import numpy as np
    u=a.real(left)-b.real(left);v=a.real(branch)-b.real(branch);w=a.real(out)-b.real(out);rounding=w-u-v
    bl=b.real(left);br=b.real(branch);bo=b.real(out)
    return dict(input_error_energy=float(np.sum(u*u)),branch_error_energy=float(np.sum(v*v)),input_branch_error_cross=2*float(np.sum(u*v)),output_error_energy=float(np.sum(w*w)),FP32_addition_roundoff_difference_energy=float(np.sum(rounding*rounding)),FP32_addition_roundoff_difference_max=float(np.max(np.abs(rounding))),signal_left_energy=float(np.sum(bl*bl)),signal_branch_energy=float(np.sum(br*br)),signal_cross=2*float(np.sum(bl*br)),signal_output_energy=float(np.sum(bo*bo)),signal_cancellation_ratio=float(np.sum(bo*bo)/(np.sum(bl*bl)+np.sum(br*br))))

def documents():
    r=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R006';rows=[]
    for p in sorted(r.glob('attempts/*formal_tv_resident*/documents/*/hidden_layer30.npz')):
        at=p.parents[2];m=json.loads((at/'node_witnesses/manifest.json').read_text());assert len(m['audit_doc_ids'])==1
        rows.append(dict(index=len(rows),doc_id=m['audit_doc_ids'][0],input=identity(p),saved_output=identity(p.parent/'hidden_layer31.npz'),directory=str(p.parent),r006_attempt=str(at)))
    assert len(rows)==3;return rows

def run(args):
    import numpy as np,torch,psutil
    from r011_single_block import v5,SingleBlock,Trace,tracing,run_block,cpu_checks
    from numerical_reference.policy import CURRENT,OUTPUT_ONLY
    from run_paired_numerical_model import reset_audit,audit_report,buffer_signature
    out=args.output_dir;torch.set_num_threads(1);assert os.environ.get('CUDA_VISIBLE_DEVICES')==GPU
    qualification=cpu_checks();write(out/'cpu_qualification.json',dict(at=now(),**qualification));docs=documents()
    sources=[identity(p) for p in [Path(__file__),HERE/'r011_single_block.py',HERE/'r010_run_audit.py',HERE/'r008_operator_diagnostic.py',Path(v5.__file__),S/'numerical_reference/gpu_reference.py',S/'numerical_reference/policy.py',S/'numerical_reference/chunked_quantization.py',S/'numerical_reference/model_compat.py',ROOT/'project/software/model/export_scalellm_llama31_artifacts.py',ROOT/'project/software/model/fixbit_v2.py']]
    manifest=dict(schema='r011_single_block_diagnostic_v1',created_at=now(),pid=os.getpid(),command=sys.argv,documents=docs,source=sources,contract=identity(out.parents[1]/'causal_diagnostic_contract.json'),checkpoint_config=identity(args.model_dir/'config.json'),checkpoint_index=identity(args.model_dir/'model.safetensors.index.json'),primary_arms={'A':['CURRENT','current'],'B':['OUTPUT_ONLY','reference'],'C':['OUTPUT_ONLY','current'],'D':['CURRENT','reference']},targeted_cuts=['gated_product','down_proj'],cut_selection='Two MLP high-level cuts predeclared from independent full1024 existing stage evidence; conditional reference-trajectory substitution, not deployment or unique additive attribution',limits=dict(gpu_seconds=900,cpu_threads=1,rss_gib=8,gpu_gib=24,evidence_mib=512),scope='Three diagnostic documents, only decoder31 and finalnorm; no fullmodel/previous31/logits/ACC/PPL')
    write(out/'manifest.json',manifest);snap=out/'source_snapshot';snap.mkdir()
    for i,e in enumerate(sources):(snap/f'{i:02d}_{Path(e["path"]).name}').write_bytes(Path(e['path']).read_bytes())
    assert free_gpu()>=30*(1<<30) and ram_available()>=32*(1<<30)
    begin=time.monotonic();done=threading.Event()
    def monitor():
        while not done.is_set():
            try:
                x=dict(at=now(),elapsed_seconds=time.monotonic()-begin,rss_bytes=psutil.Process().memory_info().rss,gpu_allocated_bytes=torch.cuda.memory_allocated(),free_gpu_bytes=free_gpu(),ram_available_bytes=ram_available(),evidence_bytes=sum(p.stat().st_size for p in out.parents[1].rglob('*') if p.is_file()));append(out/'resources.jsonl',x)
                if x['elapsed_seconds']>900 or x['rss_bytes']>8*(1<<30) or x['gpu_allocated_bytes']>24*(1<<30) or x['free_gpu_bytes']<8*(1<<30) or x['ram_available_bytes']<32*(1<<30) or x['evidence_bytes']>512*(1<<20):write(out/'resource_violation.json',x);os.kill(os.getpid(),signal.SIGTERM);return
            except Exception as e:append(out/'monitor_errors.jsonl',dict(at=now(),error=str(e)))
            done.wait(10)
    def stopped(n,f):raise RuntimeError('R011 resource/time limit')
    signal.signal(signal.SIGTERM,stopped);signal.signal(signal.SIGALRM,stopped);signal.alarm(900);threading.Thread(target=monitor,daemon=True).start()
    try:
        stage(out,'constructing_only_decoder31');checkpoint=v5.LlamaCheckpoint(args.model_dir);block=SingleBlock(checkpoint,torch.device('cuda:0'),lambda name,**kw:stage(out,name,**kw));signature=buffer_signature(block)
        weights={op:{k:arrid(getattr(module,k).cpu().numpy()) for k in ['weight_s8','weight_codes_u8','weight_shifts_u8']} for op,module in block.linears.items()};write(out/'weights_identity.json',weights);stage(out,'single_block_ready',allocated_bytes=torch.cuda.memory_allocated())
        # Frozen-source qualification: unobserved native block versus observed native block,
        # source restoration under an intentional exception and buffer invariants.
        x=torch.zeros((1,3,4096),dtype=torch.float32,device='cuda:0');x[...,0]=.125
        class NoTrace:
            def emit(self,n,v,bits=0):return v
        with torch.inference_mode():plain=block(x,NoTrace())
        reset_audit(block.audit);observed,pre,final=run_block(block,x,CURRENT)
        assert torch.equal(plain[0],pre) and torch.equal(plain[1],final)
        symbols={n:getattr(v5,n) for n in ['prepare_fixed_activation','_fixed_rope','_kv12_quantize','_qk_scores_s20','_softmax_u16','_pv_s24','_swiglu_s32','grouped_linear_s24']}
        try:
            with tracing(block,Trace()):raise ValueError('expected exception restoration probe')
        except ValueError:pass
        assert all(getattr(v5,n) is f for n,f in symbols.items()) and buffer_signature(block)==signature
        write(out/'gpu_qualification.json',dict(passed=True,native_vs_observed_bitwise_equal=True,named_stage_count=len(observed.data),hook_ordinals=observed.ordinal,exception_restoration=True,buffers_unchanged=True,at=now()));del plain,observed,pre,final,x;stage(out,'gpu_qualification_passed')
        allrows=[];interventions=[]
        keep_base=['input','input_norm','attention_output','attention_residual','post_attention_norm','gate_proj','up_proj','silu','gated_product','prepare3_hadamard','prepare3_dequant','down_proj','mlp_output','final_residual','final_norm']
        keep_cross=['input','attention_residual','gated_product','down_proj','mlp_output','final_residual','final_norm']
        for doc in docs:
            directory=out/'documents'/f'doc{doc["index"]:03d}';directory.mkdir(parents=True)
            with np.load(doc['input']['path']) as z:inputs={k:z[k].copy() for k in z.files}
            with np.load(doc['saved_output']['path']) as z:expected={k:z[k].copy() for k in z.files}
            traces={};audit={};parity=[]
            for arm,policy,inp in [('A',CURRENT,'current'),('B',OUTPUT_ONLY,'reference'),('C',OUTPUT_ONLY,'current'),('D',CURRENT,'reference')]:
                reset_audit(block.audit);stage(out,'primary_started',doc_index=doc['index'],arm=arm);t=time.monotonic();tr,pre,final=run_block(block,torch.from_numpy(inputs[inp]).cuda(),policy);torch.cuda.synchronize();traces[arm]=tr;audit[arm]=audit_report(block.audit,reference=policy==OUTPUT_ONLY)
                assert buffer_signature(block)==signature
                checks={}
                if arm in ['A','B']:
                    checks['saved_hidden31_bitwise_equal']=np.array_equal(tr.data['final_residual'],expected[inp]);assert checks['saved_hidden31_bitwise_equal'],(doc['index'],arm,'hidden31 mismatch',float(np.max(np.abs(tr.data['final_residual']-expected[inp]))))
                    for name,values in tr.dynamic.items():
                        if name=='silu':continue
                        typ='prepare_fixed_activation' if name.startswith('prepare') else '_kv12_quantize';ordinal=int(name[-1]);path=Path(doc['directory'])/f'dynamic_{inp}_layer31_{typ}_{ordinal:02d}.npz'
                        with np.load(path) as z:assert all(np.array_equal(values[k],z[k]) for k in z.files),(doc['index'],arm,name)
                    checks['all_saved_prepared_and_KV_equal']=True
                    finalpath=Path(doc['directory'])/f'final_hidden_{inp}.npz'
                    with np.load(finalpath) as z:assert np.array_equal(tr.data['final_norm'],z['hidden'])
                    checks['saved_final_norm_bitwise_equal']=True
                keep=keep_base if arm in ['A','B'] else keep_cross
                raw={k:tr.data[k] for k in keep};raw.update({f'dynamic__{name}__{key}':val for name,d in tr.dynamic.items() for key,val in d.items()})
                with (directory/f'{arm}_trace.npz').open('xb') as f:np.savez_compressed(f,**raw)
                write(directory/f'{arm}_trace_metadata.json',dict(bits=tr.bits,all_stage_identity={k:arrid(v) for k,v in tr.data.items()},saved_stages=keep,dynamic_coordinates=list(tr.dynamic),audit=audit[arm],checks=checks))
                parity.append(dict(arm=arm,checks=checks));stage(out,'primary_completed',doc_index=doc['index'],arm=arm,seconds=time.monotonic()-t);del pre,final
            a,b,c,d=(traces[k] for k in ['A','B','C','D']);assert set(a.data)==set(b.data)==set(c.data)==set(d.data)
            rows=[]
            for name in a.data:
                arrays={arm:t.real(name) for arm,t in traces.items()};mask=None
                if name in ['qk_scores','attention_softmax']:
                    t=inputs['current'].shape[1];mask=np.broadcast_to(np.tri(t,dtype=bool),(1,32,t,t))
                row=dict(doc_index=doc['index'],doc_id=doc['doc_id'],stage=name,comparisons={key:metrics(arrays[x],arrays[y],mask) for key,x,y in [('AB_cross','A','B'),('AC_same_input_local','A','C'),('CB_inherited','C','B'),('DB_same_reference_input_local','D','B'),('AD_inherited_current_arithmetic','A','D')]})
                if name in ['input','attention_output','attention_residual','post_attention_norm','gated_product','down_proj','mlp_output','final_residual','final_norm']:row['decomposition']=decompose(arrays['A'],arrays['B'],arrays['C'])
                rows.append(row);append(out/'stage_metrics.jsonl',row)
            dyn=[]
            for name in a.dynamic:
                for key in a.dynamic[name]:
                    av=a.dynamic[name][key];bv=b.dynamic[name][key];cv=c.dynamic[name][key];dyn.append(dict(coordinate=name,field=key,count=av.size,AB_changed=int(np.count_nonzero(av!=bv)),AC_changed=int(np.count_nonzero(av!=cv)),A_min=int(av.min()),A_max=int(av.max()),B_min=int(bv.min()),B_max=int(bv.max())))
            residuals=dict(attention=residual(a,b,'input','attention_output','attention_residual'),mlp=residual(a,b,'attention_residual','mlp_output','final_residual'))
            row=dict(doc_index=doc['index'],doc_id=doc['doc_id'],tokens=int(inputs['current'].shape[1]),primary_parity=parity,stages=rows,dynamic=dyn,residual_decomposition=residuals,audit=audit)
            write(directory/'primary_summary.json',row);allrows.append(row);stage(out,'primary_trace_decisive',doc_index=doc['index'],input_AB=next(x for x in rows if x['stage']=='input')['comparisons']['AB_cross'],final_AB=next(x for x in rows if x['stage']=='final_residual')['comparisons']['AB_cross'],final_decomposition=next(x for x in rows if x['stage']=='final_residual')['decomposition'],mlp_residual=residuals['mlp'])
            # Conditional teacher-forcing cuts: change one current-trajectory stage and recompute suffix.
            for cut in ['gated_product','down_proj']:
                reset_audit(block.audit);tr,pre,final=run_block(block,torch.from_numpy(inputs['current']).cuda(),CURRENT,{cut:b.data[cut]})
                comparisons={n:metrics(tr.real(n),b.real(n)) for n in ['attention_residual','mlp_output','final_residual','final_norm']};inter=dict(doc_index=doc['index'],doc_id=doc['doc_id'],cut=cut,replacement_source='same stage from B OUTPUT_ONLY(Hr)',recomputed_suffix=True,compared_to='B',comparisons=comparisons,baseline_final_error_energy=next(x for x in rows if x['stage']=='final_residual')['comparisons']['AB_cross']['error_energy'])
                inter['conditional_final_error_energy_reduction_percent']=100*(1-comparisons['final_residual']['error_energy']/inter['baseline_final_error_energy'])
                if cut=='down_proj':
                    predicted=a.data['attention_residual']+b.data['mlp_output'];assert np.array_equal(predicted,tr.data['final_residual'])
                    inter['FP32_residual_from_current_skip_plus_reference_branch_bitwise_equal']=True
                interventions.append(inter);append(out/'interventions.jsonl',inter)
                with (directory/f'cut_{cut}_outputs.npz').open('xb') as f:np.savez_compressed(f,final_residual=tr.data['final_residual'],final_norm=tr.data['final_norm'],mlp_output=tr.data['mlp_output'])
                write(directory/f'cut_{cut}_summary.json',inter);stage(out,'intervention_completed',doc_index=doc['index'],cut=cut,reduction_percent=inter['conditional_final_error_energy_reduction_percent']);del tr,pre,final
            write(directory/'document_manifest.json',dict(doc=doc,files=[identity(p) for p in directory.iterdir() if p.is_file()]));del traces,a,b,c,d,arrays;gc.collect();stage(out,'document_completed',documents=len(allrows),total=3)
        source_unchanged=all(identity(e['path'])['sha256']==e['sha256'] for e in sources);assert source_unchanged
        result=dict(execution_state='completed',documents=3,tokens=sum(x['tokens'] for x in allrows),primary_singleblock_forwards=12,intervention_singleblock_forwards=6,source_unchanged=True,all_R006_hidden_and_dynamic_parity_passed=True,all_buffers_functions_attributes_restored=True,no_full_model_or_prefix_forward=True,gpu_wall_seconds=time.monotonic()-begin,maximum_allocated_bytes=torch.cuda.max_memory_allocated(),interventions=interventions,document_summaries=[dict(doc_index=x['doc_index'],doc_id=x['doc_id'],tokens=x['tokens'],residual_decomposition=x['residual_decomposition']) for x in allrows])
        write(out/'result.json',result);stage(out,'all_completed',documents=3);write(out/'status.json',dict(at=now(),**result));return result
    finally:done.set();signal.alarm(0)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--model-dir',type=Path,required=True);args=p.parse_args();begin=time.monotonic();started=now();code=1
    try:run(args);code=0
    except BaseException as e:write(args.output_dir/'failure.json',dict(at=now(),error=str(e),type=type(e).__name__,traceback=traceback.format_exc()));write(args.output_dir/'status.json',dict(execution_state='failed',at=now(),error=str(e)));raise
    finally:write(args.output_dir/'execution_receipt.json',dict(execution_state='completed' if code==0 else 'failed',native_exit_code=code,started_at=started,ended_at=now(),wall_seconds=time.monotonic()-begin))
if __name__=='__main__':main()
