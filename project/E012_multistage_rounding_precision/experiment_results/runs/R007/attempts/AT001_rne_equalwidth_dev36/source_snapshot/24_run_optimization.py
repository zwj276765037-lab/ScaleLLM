"""R007 one-resident-model bounded paired rounding optimization experiment."""
from __future__ import annotations
import argparse
from contextlib import nullcontext
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback

HERE=Path(__file__).resolve().parent
S=HERE.parent
ROOT=S.parents[4]
sys.path.insert(0,str(S));sys.path.insert(0,str(HERE))
GPU='GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6'
ARMS=['baseline','linear_last1','linear_all32','linear_pv_all32','reference']


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

def cpu(out):
    from primitive_tests import cpu_tests
    started=now();begin=time.monotonic();result=cpu_tests()
    write(out/'cpu_qualification.json',dict(**result,started_at=started,ended_at=now(),wall_seconds=time.monotonic()-begin,gpu_initialized=False,source=[identity(HERE/'candidate.py'),identity(HERE/'primitive_tests.py')]))


def freeze(out,args):
    from transformers import AutoTokenizer
    from run_paired_numerical_model import read_document,code_identities
    docs=[read_document(args.documents,i) for i in range(36)]
    if len({d['duplicate_cluster'] for d in docs})!=36:raise ValueError('duplicate document cluster')
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
    entries=[]
    for i,d in enumerate(docs):
        token=tokenizer(d['text'],return_tensors='pt',truncation=True,max_length=128,add_special_tokens=True,padding=False)
        d['_encoded']={k:v for k,v in token.items()};d['_index']=i
        entry={k:d[k] for k in ['doc_id','domain','split','evidence_role','text_sha256','duplicate_cluster']}
        entry.update(index=i,partition='selection4' if i<4 else 'validation32',tokens=int(token['input_ids'].shape[1]),input_ids=token['input_ids'].tolist(),attention_mask=token['attention_mask'].tolist())
        entries.append(entry)
    sources=code_identities()+[identity(p) for p in [HERE/'candidate.py',HERE/'primitive_tests.py',Path(__file__),S/'logit_numerical_extension.py',S/'softmax_tv_extension_v2.py']]
    manifest=dict(schema='m005_r007_optimization_manifest_v1',created_at=now(),pid=os.getpid(),runtime_id=f"pid:{os.getpid()} startticks:{Path('/proc/self/stat').read_text().split()[21]}",command=sys.argv,checkpoint_dir=str(args.model_dir),checkpoint_config=identity(args.model_dir/'config.json'),checkpoint_index=identity(args.model_dir/'model.safetensors.index.json'),document_source=identity(args.documents),documents=entries,source=sources,candidate_arms=ARMS,selection_rule='Among candidates with median finalhidden L2 <= baseline, median fullvocab logit L2 <= baseline, total top1 errors <= baseline, choose minimum pooled per-position mean TV; ties follow roster. No eligible candidate means no winner and no validation.',reference='Unmodified independent OUTPUT_ONLY arithmetic_context',resource_limits=dict(gpu_uuid=GPU,cpu_threads=1,max_rss_gib=8,max_gpu_gib=24,launch_free_gpu_gib=30,runtime_free_gpu_gib=8,minimum_available_ram_gib=32,total_gpu_wall_seconds=2400,max_evidence_mib=512),tokens=128,model_loaded_once=True,each_arm_recomputes_activation_and_kv=True,scope='Development selection first4 plus separate next32 validation; no heldout/task ACC/PPL claim')
    write(out/'manifest.json',manifest)
    snapshot=out/'source_snapshot';snapshot.mkdir()
    for i,row in enumerate(sources):
        p=Path(row['path']);(snapshot/f'{i:02d}_{p.name}').write_bytes(p.read_bytes())
    return docs,manifest


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


def choose(summary):
    base=summary['baseline'];eligible=[];decisions=[]
    for arm in ARMS[1:-1]:
        x=summary[arm]
        checks=dict(finalhidden_median=x['final_hidden']['document_median_percent']<=base['final_hidden']['document_median_percent'],logit_median=x['logits']['document_median_percent']<=base['logits']['document_median_percent'],top1_errors=x['top1_errors']<=base['top1_errors'])
        passed=all(checks.values());decisions.append(dict(arm=arm,eligible=passed,checks=checks,pooled_mean_tv=x['tv']['pooled_mean']))
        if passed:eligible.append(arm)
    winner=min(eligible,key=lambda a:summary[a]['tv']['pooled_mean']) if eligible else None
    return dict(winner=winner,decisions=decisions,rule='minimum pooled mean TV subject to median finalhidden/logit L2 no regression and total top1 errors no increase',baseline_mean_tv=base['tv']['pooled_mean'])


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
    from candidate import candidate_context
    import softmax_tv_extension_v2 as logit
    from primitive_tests import gpu_tests
    out=args.output_dir;torch.set_num_threads(1);torch.manual_seed(2026102007)
    if os.environ.get('CUDA_VISIBLE_DEVICES')!=GPU:raise RuntimeError('must bind only exact GPU0 UUID')
    if not json.loads((out/'cpu_qualification.json').read_text())['passed']:raise RuntimeError('CPU gate absent')
    docs,manifest=freeze(out,args)
    if gpu_free()<30*(1<<30) or ram_available()<32*(1<<30):raise RuntimeError('launch resource threshold unmet')
    begin_gpu=time.monotonic();stopped=threading.Event()
    def monitor():
        while not stopped.is_set():
            try:
                import psutil
                rss=psutil.Process().memory_info().rss;free=gpu_free();ram=ram_available()
                size=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
                row=dict(at=now(),elapsed_gpu_seconds=time.monotonic()-begin_gpu,rss_bytes=rss,gpu_free_bytes=free,ram_available_bytes=ram,evidence_bytes=size)
                append(out/'resources.jsonl',row)
                violation= rss>8*(1<<30) or free<8*(1<<30) or ram<32*(1<<30) or size>512*(1<<20) or row['elapsed_gpu_seconds']>2400
                if violation:
                    write(out/'resource_violation.json',row);os.kill(os.getpid(),signal.SIGTERM);return
            except Exception as e:append(out/'monitor_errors.jsonl',dict(at=now(),error=str(e)))
            stopped.wait(15)
    signal.signal(signal.SIGTERM,lambda n,f:(_ for _ in ()).throw(RuntimeError('owned resource/time stop')))
    signal.signal(signal.SIGALRM,lambda n,f:(_ for _ in ()).throw(RuntimeError('2400s GPU wall limit')))
    signal.alarm(2400);thread=threading.Thread(target=monitor,daemon=True);thread.start()
    started=now()
    try:
        stage(out,'gpu_primitive_started');r=gpu_tests();write(out/'gpu_qualification.json',dict(**r,ended_at=now()));stage(out,'gpu_primitive_passed',**r)
        stage(out,'loading_model');load_begin=time.monotonic();base=load_streamed_bf16_model(args.model_dir,'cuda:0',out)
        class Facade(nn.Module):
            def __init__(self,base):super().__init__();self.model=base;self.lm_head=nn.Identity();self.config=base.config
        model=Facade(base);v5=production_module();stage(out,'model_loaded',seconds=time.monotonic()-load_begin)
        stage(out,'attaching_v5');attach_begin=time.monotonic()
        with chunked_weight_context(v5,128):metadata,audit=attach_v5_fullchain_compatible(model,checkpoint_dir=args.model_dir,device=torch.device('cuda:0'),strict_total_shift=True,software_extended=False,trace_layers=None,down_output_width=32,down_shift12_candidate=True)
        validate_attach(metadata);write(out/'attach_metadata.json',metadata);model.eval();del base;torch.cuda.empty_cache();stage(out,'v5_attached',seconds=time.monotonic()-attach_begin,allocated_bytes=torch.cuda.memory_allocated())
        stage(out,'loading_shared_output_head');head=logit.load_output_head(args.model_dir,torch.device('cuda:0'),out/'output_head');signature=buffer_signature(model)
        state={'layer':-1,'dynamic':{},'pre_norm':None};handles=[]
        for index,layer in enumerate(model.model.layers):
            def pre(module,inputs,index=index):state['layer']=index
            handles.append(layer.register_forward_pre_hook(pre))
        def capture(module,inputs,result):
            value=result[0] if isinstance(result,(tuple,list)) else result
            state['pre_norm']=value.detach().clone()
        handles.append(model.model.layers[31].register_forward_hook(capture))
        dynamic_orig={name:getattr(v5,name) for name in ['prepare_fixed_activation','_kv12_quantize']}
        for name,original in dynamic_orig.items():
            def wrapper(*pos,name=name,original=original,**kw):
                key=f"{state['layer']}:{name}";state['dynamic'][key]=state['dynamic'].get(key,0)+1
                return original(*pos,**kw)
            setattr(v5,name,wrapper)
        old_dir=ROOT/'project/E012_multistage_rounding_precision/experiment_results/runs/R006/attempts/AT001_softmax_tv_dev_qualification'
        old_logits={r['doc_id']:r for r in map(json.loads,(old_dir/'logit_metrics.jsonl').read_text().splitlines())}
        old_hidden={r['doc_id']:r for r in map(json.loads,(old_dir/'tensor_metrics.jsonl').read_text().splitlines()) if r['layer']==31}
        rows=[];parity=[];winner=None;references=[]
        for index,doc in enumerate(docs):
            if index==4:
                summary=summarize([r for r in rows if r['partition']=='selection4']);write(out/'selection_summary.json',summary)
                selection=choose(summary);write(out/'selection_decision.json',selection);winner=selection['winner'];stage(out,'selection_complete',**selection)
                if winner is None:break
            partition='selection4' if index<4 else 'validation32'
            arms=ARMS if index<4 else ['baseline',winner,'reference']
            directory=out/'documents'/f'doc{index:03d}';directory.mkdir(parents=True)
            encoded={k:v.to('cuda:0') for k,v in doc['_encoded'].items()};tokens=int(encoded['input_ids'].shape[1]);arm_data={}
            for arm in arms:
                state.update(layer=-1,dynamic={},pre_norm=None);reset_audit(audit)
                stage(out,'forward_started',document_index=index,doc_id=doc['doc_id'],arm=arm,tokens=tokens);t=time.monotonic()
                context=arithmetic_context(v5,OUTPUT_ONLY) if arm=='reference' else candidate_context(v5,state,arm) if arm!='baseline' else nullcontext()
                with torch.inference_mode(),context:
                    result=model.model(**encoded,use_cache=False,return_dict=True)
                    final=result.last_hidden_state.detach().clone();pre_norm=state['pre_norm'];del result
                torch.cuda.synchronize();elapsed=time.monotonic()-t
                expected={f'{layer}:{name}':count for layer in range(32) for name,count in [('prepare_fixed_activation',4),('_kv12_quantize',2)]}
                if state['dynamic']!=expected:raise RuntimeError(f'dynamic code coverage differs: {arm}')
                if final.dtype!=torch.float32 or not bool(torch.isfinite(final).all() and torch.isfinite(pre_norm).all()):raise RuntimeError('nonfinite/incorrect hidden dtype')
                if torch.cuda.max_memory_allocated()>24*(1<<30):raise RuntimeError('GPU allocated peak above24GiB')
                if buffer_signature(model)!=signature:raise RuntimeError('shared model buffers changed')
                pre_cpu=pre_norm.cpu().numpy().copy();final_cpu=final.cpu().numpy().copy()
                np.savez_compressed(directory/f'{arm}_hidden.npz',pre_norm=pre_cpu,final=final_cpu)
                report=audit_report(audit,reference=arm=='reference');write(directory/f'{arm}_audit.json',report)
                arm_data[arm]=dict(pre=pre_cpu,final_cpu=final_cpu,final=final,seconds=elapsed,audit=report)
                stage(out,'forward_complete',document_index=index,arm=arm,seconds=elapsed,dynamic_coordinates=192,allocated_bytes=torch.cuda.memory_allocated())
            ref=arm_data['reference'];references.append(dict(index=index,doc_id=doc['doc_id'],forward_seconds=ref['seconds'],audit=ref['audit'],final_identity=sha_array(ref['final_cpu']),pre_norm_identity=sha_array(ref['pre'])))
            for arm in arms:
                if arm=='reference':continue
                data=arm_data[arm];t=time.monotonic();measure=logit.measure_logits(data['final'],ref['final'],head,doc);torch.cuda.synchronize();elapsed=time.monotonic()-t
                row=dict(index=index,doc_id=doc['doc_id'],partition=partition,tokens=tokens,arm=arm,layer32_pre_norm=energy_metrics(data['pre'],ref['pre']),final_hidden=energy_metrics(data['final_cpu'],ref['final_cpu']),logits=measure,audit=data['audit'],forward_seconds=data['seconds'],reference_forward_seconds=ref['seconds'],measurement_seconds=elapsed,pre_norm_identity=sha_array(data['pre']),final_hidden_identity=sha_array(data['final_cpu']),dynamic_coordinates_per_arm=192)
                rows.append(row);write(directory/f'{arm}_comparison.json',row);append(out/'metrics.jsonl',row)
                if index<4 and arm=='baseline':
                    old=old_logits[doc['doc_id']];current_ids=measure['final_hidden_identity']
                    checks=dict(final_hidden_hashes=current_ids==old['final_hidden_identity'],logit_l2=measure['relative_l2_percent']==old['relative_l2_percent'],top1=measure['per_token']['top1_matches']==old['per_token']['top1_matches'],tv=measure['softmax_tv']['tv']==old['softmax_tv']['tv'],layer32_l2=row['layer32_pre_norm']['relative_l2_percent']==old_hidden[doc['doc_id']]['metrics']['current_vs_reference']['relative_l2_percent'])
                    parity.append(dict(index=index,doc_id=doc['doc_id'],checks=checks,passed=all(checks.values())))
                    write(out/'r006_baseline_parity.json',dict(rows=parity,passed=all(x['passed'] for x in parity),old_directory=str(old_dir)))
                    if not all(checks.values()):raise RuntimeError('R006 baseline numerical parity failed')
                stage(out,'comparison_complete',document_index=index,arm=arm,pre_norm_l2=row['layer32_pre_norm']['relative_l2_percent'],final_l2=row['final_hidden']['relative_l2_percent'],logit_l2=measure['relative_l2_percent'],tv=measure['softmax_tv']['document_mean'],top1_errors=tokens-measure['top1_match_count'])
            del arm_data,ref,data,final,pre_norm,encoded
            write(out/'partial_summary.json',dict(selection=summarize([r for r in rows if r['partition']=='selection4']),validation=summarize([r for r in rows if r['partition']=='validation32']),completed_documents=index+1))
            stage(out,'document_complete',document_index=index,doc_id=doc['doc_id'])
        for h in handles:h.remove()
        for name,value in dynamic_orig.items():setattr(v5,name,value)
        unchanged=all(identity(row['path'])['sha256']==row['sha256'] for row in manifest['source'])
        if not unchanged:raise RuntimeError('consumed source changed')
        result=dict(schema='m005_r007_result_v1',execution_state='completed',winner=winner,selection=summarize([r for r in rows if r['partition']=='selection4']),validation=summarize([r for r in rows if r['partition']=='validation32']),measured_selection_documents=len({r['index'] for r in rows if r['partition']=='selection4'}),measured_validation_documents=len({r['index'] for r in rows if r['partition']=='validation32'}),source_unchanged=unchanged,common_reference_forward_records=references,r006_first4_baseline_parity=parity,peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),gpu_wall_seconds=time.monotonic()-begin_gpu,scope='Development first4 selection and separate next32 validation only; no implementation timing/task-quality result')
        write(out/'result.json',result);stage(out,'completed',winner=winner,measured_selection_documents=result['measured_selection_documents'],measured_validation_documents=result['measured_validation_documents'])
        write(out/'execution_receipt.json',dict(execution_state='completed',native_exit_code=0,pid=os.getpid(),started_at=started,ended_at=now(),gpu_wall_seconds=time.monotonic()-begin_gpu,source_unchanged=unchanged,stop_reason=None))
        write(out/'status.json',dict(execution_state='completed',stage='completed',at=now(),pid=os.getpid(),winner=winner))
    except BaseException as e:
        write(out/'execution_receipt.json',dict(execution_state='failed',native_exit_code=1,pid=os.getpid(),started_at=started,ended_at=now(),gpu_wall_seconds=time.monotonic()-begin_gpu,error=str(e),traceback=traceback.format_exc(),stop_reason='resource/time bound' if 'stop' in str(e) or 'limit' in str(e) else None))
        write(out/'status.json',dict(execution_state='failed',stage='failed',at=now(),pid=os.getpid(),error=str(e)));raise
    finally:stopped.set();signal.alarm(0)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--model-dir',type=Path);p.add_argument('--documents',type=Path);p.add_argument('--cpu-only',action='store_true');a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    if a.cpu_only:cpu(a.output_dir)
    else:run(a)

if __name__=='__main__':main()
