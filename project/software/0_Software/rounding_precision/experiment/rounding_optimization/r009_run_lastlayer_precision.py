"""R009 true last-layer F18/F20 branch exits, fixed/matched reference pairs."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib,json,math,os,signal,subprocess,sys,threading,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent
S=HERE.parent
ROOT=S.parents[4]
sys.path.insert(0,str(S))
GPU='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
ARMS=['baseline_b0','candidate_b2','candidate_b4','output_only_reference_b0','output_only_reference_b2','output_only_reference_b4']
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


def aggregate(rows,relation):
    selected=[r for r in rows if r['relation']==relation]
    if relation=='matched_format':selected += [r for r in rows if r['relation']=='common_fixed' and r['arm']=='candidate_b4']
    return summarize(selected) if selected else {}


def freeze(out,args):
    from transformers import AutoTokenizer
    from run_paired_numerical_model import read_document,code_identities
    docs=[read_document(args.documents,i) for i in range(36)];assert len({d['duplicate_cluster'] for d in docs})==36
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False);selected=[]
    for index,d in enumerate(docs):
        d['_encoded']=tokenizer(d['text'],return_tensors='pt',truncation=True,max_length=128,add_special_tokens=True,padding=False)
        entry={k:d[k] for k in ['doc_id','domain','split','evidence_role','text_sha256','duplicate_cluster']};entry.update(index=index,tokens=int(d['_encoded']['input_ids'].shape[1]),input_ids=d['_encoded']['input_ids'].tolist(),attention_mask=d['_encoded']['attention_mask'].tolist());selected.append(entry)
    assert sum(d['tokens'] for d in selected)==4494
    sources=code_identities()+[identity(p) for p in [Path(__file__),HERE/'r009_lastlayer_kernels.py',HERE/'r009_qualification.py',S/'logit_numerical_extension.py',S/'softmax_tv_extension_v2.py']]
    manifest=dict(schema='m005_r009_lastlayer_manifest_v1',created_at=now(),pid=os.getpid(),runtime_id=f"pid:{os.getpid()} startticks:{Path('/proc/self/stat').read_text().split()[21]}",command=sys.argv,checkpoint_dir=str(args.model_dir),checkpoint_config=identity(args.model_dir/'config.json'),checkpoint_index=identity(args.model_dir/'model.safetensors.index.json'),document_source=identity(args.documents),documents=selected,source=sources,arms=ARMS,common_reference='output_only_reference_b4',matched_reference_pairs=[['baseline_b0','output_only_reference_b0'],['candidate_b2','output_only_reference_b2'],['candidate_b4','output_only_reference_b4']],reference_drift_pairs=[['output_only_reference_b0','output_only_reference_b4'],['output_only_reference_b2','output_only_reference_b4']],experimental_format_overlay=dict(layer_index=31,projections=['o_proj','down_proj'],b_values=[2,4],intermediate_fractional_bits='24+b',output_fractional_bits='16+b',output_signed_bits={'o_proj':'24+b','down_proj':'32+b'},guard_acc_bits='original+b',output_dtype='int64',final_drop=8,host_dtype='float32',host_divisor='2^(16+b)',production_format05_ABI_modified=False),storage=dict(new_finalhidden_all_docs=True,pre_norm_raw_doc_indices=[0,4,35],legacy_raw_links_verified=True,prefix_hash_layers=list(range(31))),model_loaded_once=True,each_arm_recomputes_activation_and_kv=True,limits=dict(gpu_uuid=GPU,cpu_threads=1,max_rss_gib=8,max_gpu_gib=24,launch_free_gpu_gib=30,runtime_free_gpu_gib=8,min_ram_gib=32,gpu_wall_seconds=2400,evidence_mib=512),scope='Repeated development first36 documents; true last-layer output format overlay, main common ref4 plus matched-format and reference-drift pairs. No heldout/ACC/PPL/RTL timing claim.')
    write(out/'manifest.json',manifest);snap=out/'source_snapshot';snap.mkdir()
    for i,r in enumerate(sources):(snap/f"{i:02d}_{Path(r['path']).name}").write_bytes(Path(r['path']).read_bytes())
    return docs,manifest


def cpu(out):
    from r009_qualification import cpu_tests
    result=cpu_tests();write(out/'cpu_qualification.json',dict(**result,ended_at=now(),source=[identity(HERE/'r009_qualification.py'),identity(HERE/'r009_lastlayer_kernels.py'),identity(Path(__file__))]))


def run(args):
    import numpy as np
    import torch
    import torch.nn as nn
    from capture_real_inputs import load_streamed_bf16_model
    from numerical_reference.model_compat import production_module,attach_v5_fullchain_compatible
    from numerical_reference.chunked_quantization import chunked_weight_context
    from numerical_reference.gpu_reference import arithmetic_context
    from numerical_reference.policy import OUTPUT_ONLY
    from run_paired_numerical_model import validate_attach,reset_audit,audit_report,buffer_signature
    from run_numerical_fidelity import energy_metrics
    import softmax_tv_extension_v2 as logit
    from r009_lastlayer_kernels import lastlayer_exit_context,interface_signature
    from r009_qualification import gpu_tests
    out=args.output_dir;torch.set_num_threads(1);torch.manual_seed(2026102009)
    if os.environ.get('CUDA_VISIBLE_DEVICES')!=GPU:raise RuntimeError('must bind exact GPU0 UUID')
    assert json.loads((out/'cpu_qualification.json').read_text())['passed']
    docs,manifest=freeze(out,args)
    if gpu_free()<30*(1<<30) or ram_available()<32*(1<<30):raise RuntimeError('launch free thresholds unmet')
    started=now();begin_gpu=time.monotonic();stopped=threading.Event()
    def monitor():
        while not stopped.is_set():
            try:
                import psutil
                row=dict(at=now(),elapsed_gpu_seconds=time.monotonic()-begin_gpu,rss_bytes=psutil.Process().memory_info().rss,gpu_free_bytes=gpu_free(),ram_available_bytes=ram_available(),evidence_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file()));append(out/'resources.jsonl',row)
                if row['rss_bytes']>8*(1<<30) or row['gpu_free_bytes']<8*(1<<30) or row['ram_available_bytes']<32*(1<<30) or row['evidence_bytes']>512*(1<<20) or row['elapsed_gpu_seconds']>2400:
                    write(out/'resource_violation.json',row);os.kill(os.getpid(),signal.SIGTERM);return
            except Exception as e:append(out/'monitor_errors.jsonl',dict(at=now(),error=str(e)))
            stopped.wait(15)
    signal.signal(signal.SIGTERM,lambda n,f:(_ for _ in ()).throw(RuntimeError('owned R009 resource/time stop')));signal.signal(signal.SIGALRM,lambda n,f:(_ for _ in ()).throw(RuntimeError('2400s GPU wall limit')));signal.alarm(2400);threading.Thread(target=monitor,daemon=True).start()
    try:
        stage(out,'gpu_qualification_started');qualified=gpu_tests();write(out/'gpu_qualification.json',dict(**qualified,ended_at=now()));stage(out,'gpu_qualification_passed')
        stage(out,'loading_model');t=time.monotonic();base=load_streamed_bf16_model(args.model_dir,'cuda:0',out)
        class Facade(nn.Module):
            def __init__(self,base):super().__init__();self.model=base;self.lm_head=nn.Identity();self.config=base.config
        model=Facade(base);v5=production_module();stage(out,'model_loaded',seconds=time.monotonic()-t);stage(out,'attaching_v5');t=time.monotonic()
        with chunked_weight_context(v5,128):metadata,audit=attach_v5_fullchain_compatible(model,checkpoint_dir=args.model_dir,device=torch.device('cuda:0'),strict_total_shift=True,software_extended=False,trace_layers=None,down_output_width=32,down_shift12_candidate=True)
        validate_attach(metadata);write(out/'base_attach_metadata.json',metadata);model.eval();del base;torch.cuda.empty_cache();stage(out,'v5_attached',seconds=time.monotonic()-t,allocated_bytes=torch.cuda.memory_allocated())
        head=logit.load_output_head(args.model_dir,torch.device('cuda:0'),out/'output_head');buffers=buffer_signature(model);interfaces=interface_signature(model)
        symbol_names=['grouped_linear_s24','_fixed_rope','_qk_scores_s20','_softmax_u16','_pv_s24'];symbols={n:getattr(v5,n) for n in symbol_names}
        state={'layer':-1,'dynamic':{},'prefix':{},'pre_norm':None};handles=[]
        for index,layer in enumerate(model.model.layers):
            def pre(module,inputs,index=index):state['layer']=index
            def post(module,inputs,result,index=index):
                value=result[0] if isinstance(result,(tuple,list)) else result
                if value.dtype!=torch.float32 or not bool(torch.isfinite(value).all()):raise RuntimeError('decoder not finite FP32')
                if index<31:state['prefix'][index]=sha_array(value.detach().cpu().numpy())
                else:state['pre_norm']=value.detach().cpu().numpy().copy()
            handles.extend([layer.register_forward_pre_hook(pre),layer.register_forward_hook(post)])
        dynamic_orig={name:getattr(v5,name) for name in ['prepare_fixed_activation','_kv12_quantize']}
        for name,original in dynamic_orig.items():
            def dynamic(*pos,name=name,original=original,**kw):
                key=f"{state['layer']}:{name}";state['dynamic'][key]=state['dynamic'].get(key,0)+1
                return original(*pos,**kw)
            setattr(v5,name,dynamic)
        prior=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36';oldrows=[json.loads(x) for x in (prior/'metrics.jsonl').read_text().splitlines()];old={r['index']:r for r in oldrows if r['arm']=='baseline'}
        rows=[];parity=[];prefix_checks=[];arm_records=[]
        pair_plan=[('common_fixed','baseline_b0','output_only_reference_b4'),('common_fixed','candidate_b2','output_only_reference_b4'),('common_fixed','candidate_b4','output_only_reference_b4'),('matched_format','baseline_b0','output_only_reference_b0'),('matched_format','candidate_b2','output_only_reference_b2'),('reference_drift','output_only_reference_b0','output_only_reference_b4'),('reference_drift','output_only_reference_b2','output_only_reference_b4')]
        for index,doc in enumerate(docs):
            directory=out/'documents'/f'doc{index:03d}';directory.mkdir(parents=True);encoded={k:v.to('cuda:0') for k,v in doc['_encoded'].items()};tokens=int(encoded['input_ids'].shape[1]);data={}
            for arm in ARMS:
                reference=arm.startswith('output_only');b=int(arm[-1]);reset_audit(audit);state.update(layer=-1,dynamic={},prefix={},pre_norm=None);events=[]
                stage(out,'forward_started',document_index=index,doc_id=doc['doc_id'],arm=arm,tokens=tokens);t=time.monotonic()
                with torch.inference_mode(),(arithmetic_context(v5,OUTPUT_ONLY) if reference else nullcontext()),lastlayer_exit_context(v5,model,b,reference=reference,events=events):
                    result=model.model(**encoded,use_cache=False,return_dict=True);final=result.last_hidden_state.detach().clone();del result
                torch.cuda.synchronize();elapsed=time.monotonic()-t
                if buffer_signature(model)!=buffers or interface_signature(model)!=interfaces or any(getattr(v5,n) is not original for n,original in symbols.items()):raise RuntimeError('buffer/attribute/function restoration failed')
                expected={f'{l}:{n}':c for l in range(32) for n,c in [('prepare_fixed_activation',4),('_kv12_quantize',2)]}
                if state['dynamic']!=expected or set(state['prefix'])!=set(range(31)):raise RuntimeError('dynamic/prefix coverage failed')
                if final.dtype!=torch.float32 or not bool(torch.isfinite(final).all()):raise RuntimeError('nonfinite/nonFP32 final')
                if torch.cuda.max_memory_allocated()>24*(1<<30):raise RuntimeError('GPU allocated above24GiB')
                if b:
                    coords=[(e['kind'],e['op']) for e in events]
                    if sorted(coords)!=sorted([(k,n) for k in ['wide_projection','host_scale'] for n in ['o_proj','down_proj']]):raise RuntimeError('wide project/Host scale not exactly once per exit')
                elif events:raise RuntimeError('b0 unexpectedly scaled')
                final_cpu=final.cpu().numpy().copy();pre_cpu=state['pre_norm'];raw=None
                if arm in ['baseline_b0','output_only_reference_b0']:
                    legacy_arm='baseline' if not reference else 'reference';path=prior/'documents'/f'doc{index:03d}'/f'{legacy_arm}_hidden.npz'
                    with np.load(path,allow_pickle=False) as legacy:
                        if sha_array(legacy['final'])!=sha_array(final_cpu) or sha_array(legacy['pre_norm'])!=sha_array(pre_cpu):raise RuntimeError('legacy raw parity failed')
                    raw=dict(kind='immutable_prior_npz_link',source=identity(path),final_array='final',pre_norm_array='pre_norm',both_array_hashes_equal=True);write(directory/f'{arm}_raw_link.json',raw)
                else:
                    payload={'final':final_cpu}
                    if index in [0,4,35]:payload['pre_norm']=pre_cpu
                    np.savez_compressed(directory/f'{arm}_hidden.npz',**payload);raw=dict(kind='new_npz',path=str(directory/f'{arm}_hidden.npz'),pre_norm_saved=index in [0,4,35])
                report=audit_report(audit,reference=reference);write(directory/f'{arm}_audit.json',report)
                record=dict(index=index,doc_id=doc['doc_id'],arm=arm,b=b,reference=reference,forward_seconds=elapsed,audit=report,prefix_hashes=state['prefix'],pre_norm_identity=sha_array(pre_cpu),final_identity=sha_array(final_cpu),output_boundary_events=events,attributes_and_functions_restored=True,raw=raw)
                arm_records.append(record);write(directory/f'{arm}_record.json',record);append(out/'arm_records.jsonl',record)
                data[arm]=dict(final=final,final_cpu=final_cpu,pre=pre_cpu,prefix=state['prefix'],record=record)
                stage(out,'forward_complete',document_index=index,arm=arm,seconds=elapsed,prefix_layers=31,host_scale_count=sum(e['kind']=='host_scale' for e in events))
            prefix=dict(index=index,doc_id=doc['doc_id'],candidate_b2_equal_baseline=data['candidate_b2']['prefix']==data['baseline_b0']['prefix'],candidate_b4_equal_baseline=data['candidate_b4']['prefix']==data['baseline_b0']['prefix'],reference_b2_equal_b0=data['output_only_reference_b2']['prefix']==data['output_only_reference_b0']['prefix'],reference_b4_equal_b0=data['output_only_reference_b4']['prefix']==data['output_only_reference_b0']['prefix'])
            if not all(v for k,v in prefix.items() if k.endswith(('baseline','b0'))):raise RuntimeError('prefix changed before layer31')
            prefix_checks.append(prefix);write(directory/'prefix_parity.json',prefix)
            for relation,arm,refarm in pair_plan:
                cur=data[arm];ref=data[refarm];t=time.monotonic();lm=logit.measure_logits(cur['final'],ref['final'],head,doc);torch.cuda.synchronize();elapsed=time.monotonic()-t
                row=dict(index=index,doc_id=doc['doc_id'],partition='first4' if index<4 else 'next32',tokens=tokens,relation=relation,arm=arm,reference_arm=refarm,layer32_pre_norm=energy_metrics(cur['pre'],ref['pre']),final_hidden=energy_metrics(cur['final_cpu'],ref['final_cpu']),logits=lm,audit=cur['record']['audit'],forward_seconds=cur['record']['forward_seconds'],reference_forward_seconds=ref['record']['forward_seconds'],measurement_seconds=elapsed,also_matched_format=relation=='common_fixed' and arm=='candidate_b4')
                rows.append(row);append(out/'metrics.jsonl',row);write(directory/f'{relation}_{arm}.json',row)
                if relation=='matched_format' and arm=='baseline_b0':
                    prev=old[index];checks=dict(head_hidden_hashes=lm['final_hidden_identity']==prev['logits']['final_hidden_identity'],layer32_l2=row['layer32_pre_norm']==prev['layer32_pre_norm'],final_l2=row['final_hidden']==prev['final_hidden'],logit_l2=lm['relative_l2_percent']==prev['logits']['relative_l2_percent'],top1=lm['per_token']['top1_matches']==prev['logits']['per_token']['top1_matches'],tv=lm['softmax_tv']['tv']==prev['logits']['softmax_tv']['tv']);parity.append(dict(index=index,passed=all(checks.values()),checks=checks));write(out/'r007_legacy_parity.json',dict(passed=all(p['passed'] for p in parity),rows=parity))
                    if not all(checks.values()):raise RuntimeError('R007 baseline/ref0 comparison parity failed')
                stage(out,'comparison_complete',document_index=index,relation=relation,arm=arm,reference_arm=refarm,pre_norm_l2=row['layer32_pre_norm']['relative_l2_percent'],final_l2=row['final_hidden']['relative_l2_percent'],logit_l2=lm['relative_l2_percent'],tv=lm['softmax_tv']['document_mean'],top1_errors=tokens-lm['top1_match_count'])
            write(out/'partial_summary.json',dict(completed_documents=index+1,common_fixed=aggregate(rows,'common_fixed'),matched_format=aggregate(rows,'matched_format'),reference_drift=aggregate(rows,'reference_drift')));stage(out,'document_complete',document_index=index,doc_id=doc['doc_id']);del data,cur,ref,final,final_cpu,pre_cpu,encoded;state['pre_norm']=None
            if index==3:write(out/'first4_summary.json',dict(common_fixed=aggregate(rows,'common_fixed'),matched_format=aggregate(rows,'matched_format'),reference_drift=aggregate(rows,'reference_drift')));stage(out,'first4_complete')
        for h in handles:h.remove()
        for n,v in dynamic_orig.items():setattr(v5,n,v)
        unchanged=all(identity(r['path'])['sha256']==r['sha256'] for r in manifest['source'])
        if not unchanged:raise RuntimeError('consumed source changed')
        result=dict(schema='m005_r009_result_v1',execution_state='completed',documents=36,positions=4494,forwards=216,comparison_rows=len(rows),common_fixed=aggregate(rows,'common_fixed'),matched_format=aggregate(rows,'matched_format'),reference_drift=aggregate(rows,'reference_drift'),first4={rel:aggregate([r for r in rows if r['index']<4],rel) for rel in ['common_fixed','matched_format','reference_drift']},next32={rel:aggregate([r for r in rows if r['index']>=4],rel) for rel in ['common_fixed','matched_format','reference_drift']},all_prefix_checks_passed=all(all(v for k,v in r.items() if k.endswith(('baseline','b0'))) for r in prefix_checks),all_attribute_function_restoration_passed=True,r007_legacy_parity_passed=all(r['passed'] for r in parity),source_unchanged=unchanged,peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),gpu_wall_seconds=time.monotonic()-begin_gpu,scope=manifest['scope'])
        write(out/'result.json',result);stage(out,'completed',documents=36,forwards=216);write(out/'execution_receipt.json',dict(execution_state='completed',native_exit_code=0,pid=os.getpid(),started_at=started,ended_at=now(),gpu_wall_seconds=time.monotonic()-begin_gpu,source_unchanged=unchanged,stop_reason=None));write(out/'status.json',dict(execution_state='completed',stage='completed',at=now(),pid=os.getpid()))
    except BaseException as e:
        write(out/'execution_receipt.json',dict(execution_state='failed',native_exit_code=1,pid=os.getpid(),started_at=started,ended_at=now(),gpu_wall_seconds=time.monotonic()-begin_gpu,error=str(e),traceback=traceback.format_exc(),stop_reason='resource/time' if 'stop' in str(e) or 'limit' in str(e) else None));write(out/'status.json',dict(execution_state='failed',stage='failed',at=now(),pid=os.getpid(),error=str(e)));raise
    finally:stopped.set();signal.alarm(0)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--model-dir',type=Path);p.add_argument('--documents',type=Path);p.add_argument('--cpu-only',action='store_true');a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    if a.cpu_only:cpu(a.output_dir)
    else:run(a)

if __name__=='__main__':main()
