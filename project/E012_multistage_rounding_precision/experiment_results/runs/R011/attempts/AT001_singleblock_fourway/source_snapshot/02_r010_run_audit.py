"""R010: one bounded two-weight original-arithmetic lastlayer replay, no model."""
from __future__ import annotations
import argparse,hashlib,json,math,os,signal,subprocess,sys,threading,time,traceback,gc
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;S=HERE.parent;ROOT=S.parents[4];sys.path.insert(0,str(S))
GPU='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
def now():return datetime.now(timezone.utc).isoformat()
def write(p,x):
    p=Path(p);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def append(p,x):
    with Path(p).open('a') as f:f.write(json.dumps(x,ensure_ascii=False,allow_nan=False)+'\n');f.flush()
def identity(p):
    p=Path(p).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def arrid(a):
    import numpy as np
    a=np.ascontiguousarray(a);return dict(shape=list(a.shape),dtype=str(a.dtype),sha256=hashlib.sha256(a.tobytes()).hexdigest())
def stage(out,name,**kw):
    x=dict(at=now(),pid=os.getpid(),stage=name,**kw);append(out/'stages.jsonl',x);write(out/'status.json',dict(execution_state='running',**x));print(json.dumps(x),flush=True)
def free_gpu():
    x=subprocess.check_output(['nvidia-smi','--id='+GPU,'--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip().split(',');assert x[0].strip()==GPU;return int(x[1])*(1<<20)
def ram_available():
    return next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))
def roster():
    import numpy as np
    r6=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R006';rows=[]
    for at in sorted(r6.glob('attempts/*formal_tv_resident*')):
        dirs=[d for d in sorted((at/'documents').glob('doc*')) if (d/'dynamic_current_layer31_prepare_fixed_activation_01.npz').exists()]
        if not dirs:continue
        witness_manifest=json.loads((at/'node_witnesses/manifest.json').read_text());assert len(dirs)==len(witness_manifest['audit_doc_ids'])==1
        doc=dirs[0];docid=witness_manifest['audit_doc_ids'][0]
        dynamic={}
        with (at/'dynamic_metadata.jsonl').open() as f:
            for line in f:
                d=json.loads(line)
                if d['doc_id']==docid and d['arm']=='current' and d['layer']==31 and d['function']=='prepare_fixed_activation' and d['ordinal'] in [1,3]:dynamic[d['ordinal']]=d
        local={}
        with (at/'local_tensor_metrics.jsonl').open() as f:
            for line in f:
                d=json.loads(line)
                if d['doc_id']==docid and d['layer']==31 and d['op'] in ['o_proj','down_proj']:local[d['op']]=d
        row=dict(index=len(rows),doc_id=docid,r006_attempt=str(at),directory=str(doc),inputs={},local_metrics=local,witness_manifest=identity(at/'node_witnesses/manifest.json'),witnesses={})
        for op,ordinal in [('o_proj',1),('down_proj',3)]:
            p=doc/f'dynamic_current_layer31_prepare_fixed_activation_{ordinal:02d}.npz'
            with np.load(p) as z:
                assert set(z.files)=={'values_u8','codes_u8','shifts_u8','zero_points_u8'}
                for key in z.files:assert arrid(z[key])['sha256']==dynamic[ordinal]['identity'][key]['sha256']
                tokens=int(z['values_u8'].shape[0]);assert z['values_u8'].shape==(tokens,128 if op=='o_proj' else 448,32)
            row['tokens']=tokens;row['inputs'][op]=dict(**identity(p),saved_identity=dynamic[ordinal]['identity'])
            wr=next(d for d in witness_manifest['records'] if d['doc_id']==docid and d['layer']==31 and d['node']=='linear' and d['op_name']==op)
            assert wr['status']=='saved';row['witnesses'][op]=dict(**wr,absolute_path=str(at/'node_witnesses'/wr['path']))
        assert len(local)==2;rows.append(row)
    assert len(rows)==15 and sum(d['tokens'] for d in rows)==1746
    return rows

def shift_histogram(act,wc,ws):
    import numpy as np
    total=np.zeros(127,dtype=np.int64)
    for g in range(act['codes_u8'].shape[1]):
        ah=np.bincount(act['shifts_u8'][act['codes_u8'][:,g]!=0,g],minlength=64)
        wh=np.bincount(ws[wc[:,g]!=0,g],minlength=64)
        total+=np.convolve(ah,wh)
    right=np.zeros(32,dtype=np.int64);left=np.zeros(25,dtype=np.int64)
    for shift,count in enumerate(total):
        if count:right[max(shift-24,0)]+=count;left[max(24-shift,0)]+=count
    return total,right,left

def run(args):
    import numpy as np,torch,psutil
    from numerical_reference.model_compat import production_module
    from numerical_reference.chunked_quantization import chunked_weight_context
    from numerical_reference.gpu_reference import grouped_linear_exact
    from run_paired_numerical_model import reset_audit,audit_report
    from r010_audit_cpu import cpu_qualification,oracle_one,comparisons,metric_from_integers
    from r010_qualification import gpu_qualification
    from r010_audit_kernels import capture
    v5=production_module();out=args.output_dir;torch.set_num_threads(1);assert os.environ.get('CUDA_VISIBLE_DEVICES')==GPU
    cpu=cpu_qualification();write(out/'cpu_qualification.json',dict(**cpu,at=now()));docs=roster()
    source_paths=[Path(__file__),HERE/'r010_audit_kernels.py',HERE/'r010_audit_cpu.py',HERE/'r010_qualification.py',Path(v5.__file__),S/'numerical_reference/gpu_reference.py',S/'numerical_reference/chunked_quantization.py',S/'numerical_reference/model_compat.py',ROOT/'project/software/model/export_scalellm_llama31_artifacts.py',ROOT/'project/software/model/fixbit_v2.py']
    sources=[identity(p) for p in source_paths];manifest=dict(schema='m005_r010_lastlayer_replay_v1',created_at=now(),pid=os.getpid(),command=sys.argv,scope='original layer31 o_proj/down_proj only; no full model, optimization or prefix replay',documents=docs,source=sources,contract=identity(out.parents[1]/'lastlayer_rounding_audit_contract.json'),checkpoint_config=identity(args.model_dir/'config.json'),checkpoint_index=identity(args.model_dir/'model.safetensors.index.json'),limits=dict(gpu_seconds=900,cpu_threads=1,rss_gib=8,gpu_gib=24,evidence_mib=512),output_count=14303232)
    write(out/'manifest.json',manifest);snap=out/'source_snapshot';snap.mkdir()
    for i,e in enumerate(sources):(snap/f'{i:02d}_{Path(e["path"]).name}').write_bytes(Path(e['path']).read_bytes())
    assert free_gpu()>=30*(1<<30) and ram_available()>=32*(1<<30)
    started=now();begin=time.monotonic();done=threading.Event()
    def monitor():
        while not done.is_set():
            try:
                row=dict(at=now(),elapsed_seconds=time.monotonic()-begin,rss_bytes=psutil.Process().memory_info().rss,free_gpu_bytes=free_gpu(),ram_available_bytes=ram_available(),gpu_allocated_bytes=torch.cuda.memory_allocated(),evidence_bytes=sum(p.stat().st_size for p in out.parents[1].rglob('*') if p.is_file()));append(out/'resources.jsonl',row)
                if row['elapsed_seconds']>900 or row['rss_bytes']>8*(1<<30) or row['free_gpu_bytes']<8*(1<<30) or row['ram_available_bytes']<32*(1<<30) or row['gpu_allocated_bytes']>24*(1<<30) or row['evidence_bytes']>512*(1<<20):write(out/'resource_violation.json',row);os.kill(os.getpid(),signal.SIGTERM);return
            except Exception as e:append(out/'monitor_errors.jsonl',dict(at=now(),error=str(e)))
            done.wait(10)
    def stopped(n,f):raise RuntimeError('R010 authorized resource/time guard')
    signal.signal(signal.SIGTERM,stopped);signal.signal(signal.SIGALRM,stopped);signal.alarm(900);threading.Thread(target=monitor,daemon=True).start()
    try:
        stage(out,'gpu_qualification_started');qual=gpu_qualification();write(out/'gpu_qualification.json',dict(**qual,at=now()));stage(out,'gpu_qualification_passed')
        checkpoint=v5.LlamaCheckpoint(args.model_dir);audit=v5.V5Audit(torch.device('cuda:0'));modules={};weights={}
        for op in ['o_proj','down_proj']:
            attention=op=='o_proj';name='model.layers.31.'+('self_attn.' if attention else 'mlp.')+op+'.weight';stage(out,'loading_weight',op=op);t=time.monotonic();reader=checkpoint._reader(name);raw=reader.raw(name)
            weights[op]=dict(tensor_name=name,shard_path=str(reader.path),shard_bytes=reader.path.stat().st_size,tensor_info=reader.info(name),raw_identity=arrid(raw));del raw
            with chunked_weight_context(v5,128):module=v5._quantized_linear_from_checkpoint(checkpoint=checkpoint,tensor_name=name,op_name=op,weight_bits=8 if attention else 4,input_width=24 if attention else 32,hadamard_width=27 if attention else 35,output_width=24 if attention else 32,device=torch.device('cuda:0'),audit=audit,strict_total_shift=True,software_extended=False,down_shift12_candidate=not attention)
            modules[op]=module;weights[op]['quantized_identity']={k:arrid(getattr(module,k).cpu().numpy()) for k in ['weight_s8','weight_codes_u8','weight_shifts_u8']};stage(out,'weight_loaded',op=op,seconds=time.monotonic()-t)
        write(out/'weights_identity.json',weights)
        records=[];checks=[];cpu_count=0
        for doc in docs:
            directory=out/'documents'/f'doc{doc["index"]:03d}';directory.mkdir(parents=True)
            for op in ['o_proj','down_proj']:
                t=time.monotonic();module=modules[op]
                with np.load(doc['inputs'][op]['path']) as z:act_arrays={k:z[k].copy() for k in z.files}
                act=v5.PreparedActivation(*(torch.from_numpy(act_arrays[k]).cuda() for k in ['values_u8','codes_u8','shifts_u8','zero_points_u8']),leading_shape=(1,doc['tokens']))
                reset_audit(audit);original=module.project_prepared(act);original_audit=audit_report(audit)
                observed=capture(act,module);assert torch.equal(original.reshape(act.rows,4096),observed['current_code']),(doc['index'],op,'original output mismatch')
                refs=[torch.zeros((),device='cuda:0',dtype=torch.int64) for _ in range(5)]
                exact=grouped_linear_exact(act,module.weight_s8,module.weight_codes_u8,module.weight_shifts_u8,26 if op=='o_proj' else 12,47 if op=='o_proj' else 44,42 if op=='o_proj' else 54,42 if op=='o_proj' else 54,42 if op=='o_proj' else 45,True,False,*refs,output_min=-(1<<(module.output_width-1)),output_max=(1<<(module.output_width-1))-1)
                assert torch.equal(exact.reshape(act.rows,4096),observed['reference_code'])
                arrays={k:observed[k].cpu().numpy().copy() for k in ['accumulator','current_code','reference_code','exact_quotient','exact_remainder']};bits=observed['common_bits']
                host_actual=(original.to(torch.float32)/65536).cpu().numpy().reshape(act.rows,4096)
                host_diff=host_actual.astype(np.float64)-arrays['current_code'].astype(np.float64)/65536
                host_audit=dict(actual_dtype=str(host_actual.dtype),count=int(host_diff.size),changed_count=int(np.count_nonzero(host_diff)),absolute_max=float(np.max(np.abs(host_diff))),error_energy=float(np.sum(host_diff*host_diff)),absolute_rmse=float(np.sqrt(np.mean(host_diff*host_diff))))
                counter_values=[int(x.item()) for x in observed['counters']];olda=original_audit['linear'][module.module_name]
                assert counter_values==[olda[k] for k in ['linear_output_saturation','linear_group_guard_overflow_s37','linear_software_group_guard_overflow','linear_accumulator_overflow','linear_software_accumulator_overflow']]
                wc=module.weight_codes_u8.cpu().numpy();ws=module.weight_shifts_u8.cpu().numpy();total_hist,right_hist,left_hist=shift_histogram(act_arrays,wc,ws)
                got_hist=observed['active_shift_hist'].cpu().numpy();lost_hist=observed['nonzero_remainder_hist'].cpu().numpy();assert np.array_equal(right_hist,got_hist) and (lost_hist<=got_hist).all() and lost_hist[0]==0
                wr=doc['witnesses'][op];wp=Path(wr['absolute_path']);assert identity(wp)['sha256']==wr['sha256']
                with np.load(wp) as z:witness={k:z[k].copy() for k in z.files}
                ids=witness['_witness_output_flat_indices'];assert np.array_equal(arrays['current_code'].reshape(-1)[ids],witness['_witness_current_code']) and np.array_equal(arrays['reference_code'].reshape(-1)[ids],witness['_witness_reference_code'])
                w=module.weight_s8.cpu().numpy()
                selected=sorted(set(ids.tolist()+[0,1,arrays['current_code'].size//2,arrays['current_code'].size-1]))
                for idx in selected:
                    row,col=divmod(idx,4096);oracle=oracle_one(act_arrays['values_u8'][row],w[col],act_arrays['codes_u8'][row],act_arrays['shifts_u8'][row],act_arrays['zero_points_u8'][row],wc[col],ws[col],op=='o_proj')
                    for key in arrays:assert int(arrays[key].reshape(-1)[idx])==oracle[key],(doc['index'],op,idx,key)
                    cpu_count+=1
                # Verify full dependency of each R006 fixed witness against saved input and quantized checkpoint.
                for j,idx in enumerate(ids):
                    row,col=divmod(int(idx),4096)
                    assert np.array_equal(witness['q_a'][j],act_arrays['values_u8'][row]) and np.array_equal(witness['q_w'][j],w[col])
                    assert np.array_equal(witness['act_code'][j],act_arrays['codes_u8'][row]) and np.array_equal(witness['weight_code'][j],wc[col])
                comps=comparisons(arrays,bits);summary={k:metric_from_integers(*v) for k,v in comps.items()};local=doc['local_metrics'][op]['metrics']['current_vs_reference'];actual=summary['additional_intermediate']
                assert actual['count']==local['total_elements'] and math.isclose(actual['error_energy'],local['error_energy'],rel_tol=1e-12,abs_tol=1e-20) and math.isclose(actual['signal_energy'],local['signal_energy'],rel_tol=1e-12,abs_tol=1e-12) and actual['absolute_max']==local['absolute_max'],(doc['index'],op,'R006 aggregate mismatch',actual,local)
                rawpath=directory/f'{op}_raw.npz'
                with rawpath.open('xb') as f:np.savez_compressed(f,**arrays)
                rec=dict(doc_index=doc['index'],doc_id=doc['doc_id'],op=op,tokens=doc['tokens'],count=arrays['current_code'].size,common_bits=bits,output_fractional_bits=16,final_drop_bits=8,raw=identity(rawpath),arrays={k:arrid(v) for k,v in arrays.items()},statistics=summary,group_histograms=dict(denominator='active row/output-channel/group terms, not scalar outputs',active_pairs=int(got_hist.sum()),inactive_pairs=int(act.rows*4096*act.groups-got_hist.sum()),rightshift_bits=got_hist.tolist(),leftshift_bits=left_hist.tolist(),total_shift_bits=total_hist.tolist(),nonzero_discarded_remainder_by_rightshift=lost_hist.tolist(),discarded_one_bits=int(observed['discarded_one_bits'])),original_audit=original_audit,host_fp32_decode_audit=host_audit,observer_counters=counter_values,reference_saturation=int(observed['reference_saturation']),verification=dict(original_output_and_counters_equal=True,independent_sameF16_reference_equal=True,r006_witness_and_inputs_equal=True,r006_local_aggregate_equal=True,arbitrary_precision_output_checks=len(selected),active_shift_hist_cpu_equal=True),seconds=time.monotonic()-t)
                write(directory/f'{op}_summary.json',rec);append(out/'operator_records.jsonl',rec);records.append(rec);stage(out,'operator_completed',doc_index=doc['index'],op=op,count=rec['count'],seconds=rec['seconds'],total_loss_rmse=summary['total_rounding']['absolute_rmse'],cut8_above_1pct=summary['final_cut8']['relative_thresholds']['1']['percent_of_nonzero'],total_above_1pct=summary['total_rounding']['relative_thresholds']['1']['percent_of_nonzero'])
                del original,exact,observed,act,arrays,comps,act_arrays,w;gc.collect()
            stage(out,'document_completed',documents_completed=doc['index']+1,total=15)
        assert sum(r['count'] for r in records)==14303232
        unchanged=all(identity(e['path'])['sha256']==e['sha256'] for e in sources);assert unchanged
        result=dict(execution_state='completed',documents=15,tokens=1746,operator_rows=len(records),scalar_outputs=sum(r['count'] for r in records),arbitrary_precision_scalar_checks=cpu_count,all_hard_checks_passed=True,source_unchanged=unchanged,original_arithmetic_only=True,full_model_loaded=False,gpu_wall_seconds=time.monotonic()-begin,maximum_allocated_bytes=torch.cuda.max_memory_allocated())
        write(out/'result.json',result);stage(out,'all_documents_completed',documents=15,scalar_outputs=result['scalar_outputs']);write(out/'status.json',dict(at=now(),**result))
        return result
    finally:done.set();signal.alarm(0)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--model-dir',type=Path,required=True);args=p.parse_args();started=now();begin=time.monotonic();code=1
    try:r=run(args);code=0
    except BaseException as e:
        write(args.output_dir/'failure.json',dict(at=now(),type=type(e).__name__,error=str(e),traceback=traceback.format_exc()));write(args.output_dir/'status.json',dict(execution_state='failed',at=now(),error=str(e)));raise
    finally:write(args.output_dir/'execution_receipt.json',dict(execution_state='completed' if code==0 else 'failed',native_exit_code=code,started_at=started,ended_at=now(),wall_seconds=time.monotonic()-begin))
if __name__=='__main__':main()
