"""R008 fixed single-family arithmetic interventions; diagnostic, not optimization.
One resident model, original first4 development documents, unmodified reference.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict,replace
from datetime import datetime,timezone
import hashlib,json,math,os,signal,subprocess,sys,threading,time,traceback
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parent
S=HERE.parent
ROOT=S.parents[4]
sys.path.insert(0,str(S))
GPU='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
ARMS=['baseline_CURRENT','linear_only_OUTPUT_ONLY','rope_only_OUTPUT_ONLY','qk_only_OUTPUT_ONLY','softmax_only_OUTPUT_ONLY','pv_only_OUTPUT_ONLY','reference_OUTPUT_ONLY']
def now():return datetime.now(timezone.utc).isoformat()

def write(path,obj):
    p=Path(path);temp=p.with_name(p.name+'.tmp')
    with temp.open('w') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,p)

def identity(path):
    p=Path(path).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())

def append(path,obj):
    with Path(path).open('a') as f:f.write(json.dumps(obj,allow_nan=False)+'\n');f.flush()

def stage(out,name,**kw):
    row=dict(at=now(),pid=os.getpid(),stage=name,**kw);append(out/'stages.jsonl',row);write(out/'status.json',dict(execution_state='running',**row));print(json.dumps(row),flush=True)

def sha_array(x):
    import numpy as np
    a=np.ascontiguousarray(x);return dict(shape=list(a.shape),dtype=str(a.dtype),sha256=hashlib.sha256(a.tobytes()).hexdigest())

def gpu_free():
    text=subprocess.check_output(['nvidia-smi','--id='+GPU,'--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True).strip()
    uuid,free=[x.strip() for x in text.split(',')]
    if uuid!=GPU:raise RuntimeError('GPU UUID mismatch')
    return int(free)*(1<<20)

def ram_available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):return int(line.split()[1])*1024
    return 0

def summarize(rows):
    import numpy as np
    ans={}
    for arm in sorted({r['arm'] for r in rows}):
        items=[r for r in rows if r['arm']==arm];n=sum(r['tokens'] for r in items)
        metrics={}
        for key in ['layer32_pre_norm','final_hidden','logits']:
            vals=np.array([r[key]['relative_l2_percent'] for r in items])
            e=sum(r[key]['error_energy'] for r in items);sig=sum(r[key].get('signal_energy',r[key].get('reference_signal_energy',0)) for r in items)
            metrics[key]=dict(document_median_percent=float(np.median(vals)),document_mean_percent=float(np.mean(vals)),document_p95_percent=float(np.quantile(vals,.95)),document_max_percent=float(vals.max()),pooled_relative_l2_percent=100*math.sqrt(e/sig),per_document=vals.tolist())
        tv=[v for r in items for v in r['logits']['softmax_tv']['tv']]
        metrics['tv']=dict(pooled_mean=float(np.mean(tv)),position_median=float(np.median(tv)),position_p95=float(np.quantile(tv,.95)),position_p99=float(np.quantile(tv,.99)),position_max=float(max(tv)),positions_above_1pct=sum(x>.01 for x in tv),positions_above_5pct=sum(x>.05 for x in tv),positions_above_10pct=sum(x>.1 for x in tv),document_max_mean=max(r['logits']['softmax_tv']['document_mean'] for r in items))
        errors=sum(r['tokens']-r['logits']['top1_match_count'] for r in items)
        metrics.update(documents=len(items),positions=n,top1_errors=errors,top1_agreement=1-errors/n,forward_seconds=sum(r['forward_seconds'] for r in items),measurement_seconds=sum(r['measurement_seconds'] for r in items),counters={name:sum(r['audit']['counters'][name] or 0 for r in items) for name in items[0]['audit']['counters']})
        ans[arm]=metrics
    return ans

def policies():
    from numerical_reference.policy import CURRENT,OUTPUT_ONLY
    return dict(zip(ARMS,[CURRENT,replace(CURRENT,linear_group_floor=False),replace(CURRENT,rope_product_round=False),replace(CURRENT,qk_group_floor=False),replace(CURRENT,softmax_interpolation_round=False,softmax_reciprocal_round=False),replace(CURRENT,pv_term_floor=False),OUTPUT_ONLY]))


def cpu_tests(out):
    import torch
    from numerical_reference.gpu_reference import arithmetic_context
    names=['grouped_linear_s24','_fixed_rope','_qk_scores_s20','_softmax_u16','_pv_s24']
    expected=[set(),{names[0]},{names[1]},{names[2]},{names[3]},{names[4]},set(names)]
    rows=[]
    for (arm,policy),changes in zip(policies().items(),expected):
        original={name:object() for name in names};fake=SimpleNamespace(**original)
        with arithmetic_context(fake,policy):
            changed={name for name in names if getattr(fake,name) is not original[name]}
            assert changed==changes,(arm,changed,changes)
            if names[3] in changed:
                assert fake._softmax_u16.keywords==dict(interpolation_round=False,reciprocal_round=False)
            try:
                with arithmetic_context(fake,policy):raise AssertionError('nested context accepted')
            except RuntimeError:pass
        assert all(getattr(fake,n) is original[n] for n in names)
        assert not hasattr(fake,'_m005_arithmetic_context_active')
        try:
            with arithmetic_context(fake,policy):raise ValueError('intentional restoration probe')
        except ValueError:pass
        assert all(getattr(fake,n) is original[n] for n in names)
        assert not hasattr(fake,'_m005_arithmetic_context_active')
        rows.append(dict(arm=arm,policy=asdict(policy),changed_symbols=sorted(changes),normal_restoration=True,exception_restoration=True,nesting_rejected=True))
    assert not torch.cuda.is_initialized()
    write(out/'cpu_policy_qualification.json',dict(passed=True,arms=len(rows),mapping_and_restoration_checks=28,gpu_initialized=False,rows=rows,source=[identity(Path(__file__)),identity(S/'numerical_reference/policy.py'),identity(S/'numerical_reference/gpu_reference.py')]))


def freeze(out,args):
    from transformers import AutoTokenizer
    from run_paired_numerical_model import read_document,code_identities
    docs=[read_document(args.documents,i) for i in range(4)]
    if len({d['duplicate_cluster'] for d in docs})!=4:raise ValueError('duplicate development cluster')
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
    selected=[]
    for i,d in enumerate(docs):
        d['_encoded']=tokenizer(d['text'],return_tensors='pt',truncation=True,max_length=128,add_special_tokens=True,padding=False)
        e={k:d[k] for k in ['doc_id','domain','split','evidence_role','text_sha256','duplicate_cluster']};e.update(index=i,tokens=int(d['_encoded']['input_ids'].shape[1]),input_ids=d['_encoded']['input_ids'].tolist(),attention_mask=d['_encoded']['attention_mask'].tolist());selected.append(e)
    assert sum(d['tokens'] for d in selected)==398
    sources=code_identities()+[identity(p) for p in [Path(__file__),S/'logit_numerical_extension.py',S/'softmax_tv_extension_v2.py']]
    manifest=dict(schema='m005_r008_operator_diagnostic_v1',created_at=now(),pid=os.getpid(),runtime_id=f"pid:{os.getpid()} startticks:{Path('/proc/self/stat').read_text().split()[21]}",command=sys.argv,checkpoint_dir=str(args.model_dir),checkpoint_config=identity(args.model_dir/'config.json'),checkpoint_index=identity(args.model_dir/'model.safetensors.index.json'),document_source=identity(args.documents),documents=selected,source=sources,arms=ARMS,policy={k:asdict(v) for k,v in policies().items()},reference='Unmodified independent OUTPUT_ONLY arithmetic_context',model_loaded_once=True,each_arm_recomputes_activation_and_kv=True,maximum_tokens=128,scope='Single-family exploratory interventions on first4 dev,398 positions; not deployable optimization or unique/additive causal attribution',limits=dict(gpu_uuid=GPU,cpu_threads=1,max_rss_gib=8,max_gpu_gib=24,launch_free_gpu_gib=30,runtime_free_gpu_gib=8,min_ram_gib=32,gpu_wall_seconds=900,evidence_mib=256))
    write(out/'manifest.json',manifest);snap=out/'source_snapshot';snap.mkdir()
    for i,row in enumerate(sources):(snap/f"{i:02d}_{Path(row['path']).name}").write_bytes(Path(row['path']).read_bytes())
    return docs,manifest


def run(args):
    import numpy as np
    import torch
    import torch.nn as nn
    from capture_real_inputs import load_streamed_bf16_model
    from numerical_reference.model_compat import production_module,attach_v5_fullchain_compatible
    from numerical_reference.chunked_quantization import chunked_weight_context
    from numerical_reference.gpu_reference import arithmetic_context
    from run_paired_numerical_model import validate_attach,reset_audit,audit_report,buffer_signature
    from run_numerical_fidelity import energy_metrics
    import softmax_tv_extension_v2 as logit
    out=args.output_dir;torch.set_num_threads(1);torch.manual_seed(2026102008)
    if os.environ.get('CUDA_VISIBLE_DEVICES')!=GPU:raise RuntimeError('must bind exact GPU0 UUID only')
    assert json.loads((out/'cpu_policy_qualification.json').read_text())['passed']
    docs,manifest=freeze(out,args)
    if gpu_free()<30*(1<<30) or ram_available()<32*(1<<30):raise RuntimeError('launch resource threshold unmet')
    begin_gpu=time.monotonic();started=now();stopped=threading.Event()
    def monitor():
        while not stopped.is_set():
            try:
                import psutil
                row=dict(at=now(),elapsed_gpu_seconds=time.monotonic()-begin_gpu,rss_bytes=psutil.Process().memory_info().rss,gpu_free_bytes=gpu_free(),ram_available_bytes=ram_available(),evidence_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file()))
                append(out/'resources.jsonl',row)
                if row['rss_bytes']>8*(1<<30) or row['gpu_free_bytes']<8*(1<<30) or row['ram_available_bytes']<32*(1<<30) or row['evidence_bytes']>256*(1<<20) or row['elapsed_gpu_seconds']>900:
                    write(out/'resource_violation.json',row);os.kill(os.getpid(),signal.SIGTERM);return
            except Exception as e:append(out/'monitor_errors.jsonl',dict(at=now(),error=str(e)))
            stopped.wait(15)
    signal.signal(signal.SIGTERM,lambda n,f:(_ for _ in ()).throw(RuntimeError('owned R008 resource/time stop')))
    signal.signal(signal.SIGALRM,lambda n,f:(_ for _ in ()).throw(RuntimeError('900s GPU wall limit')))
    signal.alarm(900);threading.Thread(target=monitor,daemon=True).start()
    try:
        stage(out,'loading_model');t=time.monotonic();base=load_streamed_bf16_model(args.model_dir,'cuda:0',out)
        class Facade(nn.Module):
            def __init__(self,base):super().__init__();self.model=base;self.lm_head=nn.Identity();self.config=base.config
        model=Facade(base);v5=production_module();stage(out,'model_loaded',seconds=time.monotonic()-t);stage(out,'attaching_v5');t=time.monotonic()
        with chunked_weight_context(v5,128):metadata,audit=attach_v5_fullchain_compatible(model,checkpoint_dir=args.model_dir,device=torch.device('cuda:0'),strict_total_shift=True,software_extended=False,trace_layers=None,down_output_width=32,down_shift12_candidate=True)
        validate_attach(metadata);write(out/'attach_metadata.json',metadata);model.eval();del base;torch.cuda.empty_cache();stage(out,'v5_attached',seconds=time.monotonic()-t,allocated_bytes=torch.cuda.memory_allocated())
        head=logit.load_output_head(args.model_dir,torch.device('cuda:0'),out/'output_head');signature=buffer_signature(model);state={'layer':-1,'dynamic':{},'layers':{}};handles=[]
        for index,layer in enumerate(model.model.layers):
            def pre(module,inputs,index=index):state['layer']=index
            def capture(module,inputs,result,index=index):
                value=result[0] if isinstance(result,(tuple,list)) else result
                if value.dtype!=torch.float32 or not bool(torch.isfinite(value).all()):raise RuntimeError('bad decoder hidden')
                state['layers'][index]=value.detach().cpu().numpy().copy()
            handles.extend([layer.register_forward_pre_hook(pre),layer.register_forward_hook(capture)])
        dynamic_orig={name:getattr(v5,name) for name in ['prepare_fixed_activation','_kv12_quantize']}
        for name,original in dynamic_orig.items():
            def wrapper(*pos,name=name,original=original,**kw):
                key=f"{state['layer']}:{name}";state['dynamic'][key]=state['dynamic'].get(key,0)+1
                return original(*pos,**kw)
            setattr(v5,name,wrapper)
        prior=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36'
        old={r['doc_id']:r for r in map(json.loads,(prior/'metrics.jsonl').read_text().splitlines()) if r['partition']=='selection4' and r['arm']=='baseline'}
        rows=[];layer_rows=[];parity=[];reference_records=[]
        for index,doc in enumerate(docs):
            directory=out/'documents'/f'doc{index:03d}';directory.mkdir(parents=True);encoded={k:v.to('cuda:0') for k,v in doc['_encoded'].items()};tokens=int(encoded['input_ids'].shape[1]);data={}
            for arm,policy in policies().items():
                reset_audit(audit);state.update(layer=-1,dynamic={},layers={});stage(out,'forward_started',document_index=index,doc_id=doc['doc_id'],arm=arm,tokens=tokens);t=time.monotonic()
                with torch.inference_mode(),arithmetic_context(v5,policy):
                    result=model.model(**encoded,use_cache=False,return_dict=True);final=result.last_hidden_state.detach().clone();del result
                torch.cuda.synchronize();elapsed=time.monotonic()-t
                expected={f'{layer}:{name}':count for layer in range(32) for name,count in [('prepare_fixed_activation',4),('_kv12_quantize',2)]}
                if state['dynamic']!=expected or set(state['layers'])!=set(range(32)):raise RuntimeError('incomplete dynamic/layer coverage')
                if final.dtype!=torch.float32 or not bool(torch.isfinite(final).all()):raise RuntimeError('bad final hidden')
                if torch.cuda.max_memory_allocated()>24*(1<<30):raise RuntimeError('GPU allocated peak above24GiB')
                if buffer_signature(model)!=signature:raise RuntimeError('shared model buffers changed')
                final_cpu=final.cpu().numpy().copy();np.savez_compressed(directory/f'{arm}_hidden.npz',pre_norm=state['layers'][31],final=final_cpu)
                report=audit_report(audit,reference=not policy.linear_group_floor);report['arithmetic_policy']=asdict(policy);report['intervention_not_deployable']=arm!='baseline_CURRENT'
                write(directory/f'{arm}_audit.json',report)
                data[arm]=dict(layers=state['layers'],final_cpu=final_cpu,final=final,seconds=elapsed,audit=report)
                stage(out,'forward_complete',document_index=index,arm=arm,seconds=elapsed,dynamic_coordinates=192,hidden_layers=32)
            ref=data['reference_OUTPUT_ONLY'];reference_records.append(dict(index=index,doc_id=doc['doc_id'],seconds=ref['seconds'],audit=ref['audit'],final_identity=sha_array(ref['final_cpu'])))
            for arm in ARMS[:-1]:
                cur=data[arm];t=time.monotonic();lm=logit.measure_logits(cur['final'],ref['final'],head,doc);torch.cuda.synchronize();elapsed=time.monotonic()-t
                per_layer=[energy_metrics(cur['layers'][l],ref['layers'][l]) for l in range(32)]
                row=dict(index=index,doc_id=doc['doc_id'],partition='diagnostic4',tokens=tokens,arm=arm,layer32_pre_norm=per_layer[-1],final_hidden=energy_metrics(cur['final_cpu'],ref['final_cpu']),logits=lm,audit=cur['audit'],forward_seconds=cur['seconds'],reference_forward_seconds=ref['seconds'],measurement_seconds=elapsed,final_hidden_identity=sha_array(cur['final_cpu']),pre_norm_identity=sha_array(cur['layers'][31]),policy=asdict(policies()[arm]),dynamic_coordinates_per_arm=192)
                rows.append(row);append(out/'metrics.jsonl',row);write(directory/f'{arm}_comparison.json',row)
                for layer,metric in enumerate(per_layer):
                    lr=dict(index=index,doc_id=doc['doc_id'],tokens=tokens,arm=arm,layer=layer,metrics=metric);layer_rows.append(lr);append(out/'layer_curve.jsonl',lr)
                if arm=='baseline_CURRENT':
                    prev=old[doc['doc_id']];checks=dict(final_hidden_hashes=lm['final_hidden_identity']==prev['logits']['final_hidden_identity'],layer32_l2=row['layer32_pre_norm']==prev['layer32_pre_norm'],final_l2=row['final_hidden']==prev['final_hidden'],logit_l2=lm['relative_l2_percent']==prev['logits']['relative_l2_percent'],top1=lm['per_token']['top1_matches']==prev['logits']['per_token']['top1_matches'],tv=lm['softmax_tv']['tv']==prev['logits']['softmax_tv']['tv'])
                    parity.append(dict(index=index,doc_id=doc['doc_id'],passed=all(checks.values()),checks=checks));write(out/'prior_baseline_parity.json',dict(passed=all(r['passed'] for r in parity),rows=parity,prior_attempt=str(prior)))
                    if not all(checks.values()):raise RuntimeError('R007/R006 baseline parity failed')
                stage(out,'comparison_complete',document_index=index,arm=arm,pre_norm_l2=row['layer32_pre_norm']['relative_l2_percent'],final_l2=row['final_hidden']['relative_l2_percent'],logit_l2=lm['relative_l2_percent'],tv=lm['softmax_tv']['document_mean'],top1_errors=tokens-lm['top1_match_count'])
            write(out/'partial_summary.json',dict(completed_documents=index+1,summary=summarize(rows)));stage(out,'document_complete',document_index=index,doc_id=doc['doc_id'])
            del data,ref,cur,final,final_cpu,encoded;state['layers']={}
        for h in handles:h.remove()
        for name,value in dynamic_orig.items():setattr(v5,name,value)
        unchanged=all(identity(r['path'])['sha256']==r['sha256'] for r in manifest['source'])
        if not unchanged:raise RuntimeError('consumed source changed')
        result=dict(schema='m005_r008_result_v1',execution_state='completed',summary=summarize(rows),documents=4,positions=398,forward_count=28,comparison_rows=len(rows),layer_curve_rows=len(layer_rows),source_unchanged=unchanged,reference_records=reference_records,prior_baseline_parity=parity,peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),gpu_wall_seconds=time.monotonic()-begin_gpu,scope=manifest['scope'])
        write(out/'result.json',result);stage(out,'completed',documents=4,positions=398,forward_count=28);write(out/'execution_receipt.json',dict(execution_state='completed',native_exit_code=0,pid=os.getpid(),started_at=started,ended_at=now(),gpu_wall_seconds=time.monotonic()-begin_gpu,source_unchanged=unchanged,stop_reason=None));write(out/'status.json',dict(execution_state='completed',stage='completed',at=now(),pid=os.getpid()))
    except BaseException as e:
        write(out/'execution_receipt.json',dict(execution_state='failed',native_exit_code=1,pid=os.getpid(),started_at=started,ended_at=now(),gpu_wall_seconds=time.monotonic()-begin_gpu,error=str(e),traceback=traceback.format_exc(),stop_reason='resource/time' if 'stop' in str(e) or 'limit' in str(e) else None));write(out/'status.json',dict(execution_state='failed',stage='failed',at=now(),pid=os.getpid(),error=str(e)));raise
    finally:stopped.set();signal.alarm(0)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--model-dir',type=Path);p.add_argument('--documents',type=Path);p.add_argument('--cpu-only',action='store_true');a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    if a.cpu_only:cpu_tests(a.output_dir)
    else:run(a)

if __name__=='__main__':main()
