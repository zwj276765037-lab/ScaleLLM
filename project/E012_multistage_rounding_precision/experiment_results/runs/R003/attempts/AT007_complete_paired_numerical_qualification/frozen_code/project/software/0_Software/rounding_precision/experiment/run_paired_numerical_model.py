"""Bounded worker for paired current/output-only V5 continuous numerical paths.

Launch only through Root's bounded GPU supervisor after resource admission.
No LM head, labels, ACC, loss, perplexity, or benchmark task is evaluated.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import traceback
from run_numerical_fidelity import identity,write_json,energy_metrics,summarize_documents,timestamp


HERE=Path(__file__).resolve().parent
SOFTWARE=HERE.parents[2]


def stage(directory,name,**details):
    with (Path(directory)/'paired_stages.jsonl').open('a',encoding='utf8') as stream:
        stream.write(json.dumps(dict(at=timestamp(),stage=name,**details),ensure_ascii=False)+'\n')


def read_document(path,index):
    if not 0<=index<64:
        raise ValueError('pilot index must select one of the 64 frozen development documents')
    with Path(path).open(encoding='utf8') as stream:
        for number,line in enumerate(stream):
            if number==index:
                row=json.loads(line)
                if row.get('split')!='dev' or row.get('evidence_role')!='development':
                    raise ValueError('cost pilot requires frozen development role, never test selection')
                actual=hashlib.sha256(row['text'].encode()).hexdigest()
                if actual!=row['text_sha256']:
                    raise ValueError('document text identity mismatch')
                return row
    raise ValueError('selected document absent')


def code_identities():
    paths=[Path(__file__),HERE/'run_numerical_fidelity.py',HERE/'capture_real_inputs.py',
           HERE/'prepare_replay_data.py',HERE/'run_local_experiment.py',
           *[HERE/'numerical_reference'/name for name in ['policy.py','current_nodes.py','exact_reductions.py','model_compat.py','gpu_reference.py','chunked_quantization.py','local_observer.py']],
           HERE/'production_replay.py',SOFTWARE/'model/export_scalellm_llama31_artifacts.py',
           SOFTWARE/'model/fixbit_v2.py',SOFTWARE/'0_Software/FPtoQ/experiment/v5_fullchain.py']
    for package,relative in [('transformers','transformers/models/llama/modeling_llama.py'),
                             ('accelerate','accelerate/utils/modeling.py')]:
        paths.append(Path(importlib.metadata.distribution(package).locate_file(relative)))
    return [identity(path) for path in paths]


def validate_attach(metadata):
    expected={'layers':32,'strict_total_shift':True,'software_reference_not_hardware':False,
              'attention_format_id':'0x48384103','mlp_full_format_id':'0x48384605',
              'mlp_group_guard_compute_width':45,'mlp_down_accumulator_compute_width':54,
              'mlp_down_output_width':32}
    for key,value in expected.items():
        if metadata.get(key)!=value:
            raise ValueError(f'attach contract mismatch {key}: {metadata.get(key)!r} != {value!r}')


def static_check(args):
    if args.document_count!=1:
        raise ValueError('this bounded qualification supports exactly one streamed document per launch')
    if not 1<=args.tokens<=128:
        raise ValueError('current production sequence limit is 128')
    doc=read_document(args.documents,args.document_index)
    config=json.loads((args.model_dir/'config.json').read_text())
    expected={'num_hidden_layers':32,'hidden_size':4096,'num_attention_heads':32,
              'num_key_value_heads':8,'intermediate_size':14336}
    for key,value in expected.items():
        if config.get(key)!=value:
            raise ValueError('unsupported checkpoint geometry: '+key)
    return doc


def reset_audit(audit):
    for value in audit.values.values():value.zero_()
    audit.activation_elements.zero_()
    for counters in audit.linear_values.values():
        for name,value in counters.items():
            value.fill_(127 if name=='linear_total_shift_min' else -1 if name=='linear_total_shift_max' else 0)



def audit_report(audit,reference=False):
    counters=audit.collect();linear=audit.collect_linear()
    unsupported=('linear_group_guard_overflow_s37','linear_software_group_guard_overflow',
                 'linear_accumulator_overflow','linear_software_accumulator_overflow')
    if reference:
        for name in unsupported:counters[name]=None
        for per_module in linear.values():
            for name in unsupported:
                if name in per_module:per_module[name]=None
    return dict(counters=counters,linear=linear,
                finite_guard_accumulator_audit='not_applicable_wider_arithmetic' if reference else 'production_counters',
                caveat='reference finite guard/accumulator counters are unpopulated; null is not zero events' if reference else None)

def buffer_signature(model):
    """Object/storage/version guard for weights reused sequentially, not a content hash."""
    return [(name,tuple(buf.shape),str(buf.dtype),buf.data_ptr(),buf._version)
            for name,buf in model.named_buffers()]


def worker(args):
    import numpy as np
    import torch
    import torch.nn as nn
    from transformers import AutoTokenizer
    from capture_real_inputs import load_streamed_bf16_model
    from numerical_reference.model_compat import production_module,attach_v5_fullchain_compatible
    from numerical_reference.policy import CURRENT,OUTPUT_ONLY
    from numerical_reference.gpu_reference import arithmetic_context
    from numerical_reference.chunked_quantization import chunked_weight_context
    from numerical_reference.local_observer import local_observer_context
    torch.set_num_threads(1)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    doc=static_check(args)
    before=code_identities()
    write_json(args.output_dir/'paired_worker_manifest.json',dict(schema='m005_v3_paired_model_v1',
               started_at=timestamp(),pid=os.getpid(),command=sys.argv,code=before,
               document_source=identity(args.documents),doc_id=doc['doc_id'],domain=doc['domain'],
               split=doc['split'],evidence_role=doc['evidence_role'],tokens=args.tokens,
               text_sha256=doc['text_sha256'],duplicate_cluster=doc['duplicate_cluster'],
               scope='continuous V5 current vs output-only; no ACC/PPL or BF16 comparison',
               versions={key:importlib.metadata.version(key) for key in ['torch','transformers','accelerate','triton','numpy']},
               cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),checkpoint_dir=str(args.model_dir.resolve())))
    device=torch.device('cuda:0')
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
    encoded=tokenizer(doc['text'],return_tensors='pt',truncation=True,max_length=args.tokens,
                      add_special_tokens=True,padding=False)
    if tuple(encoded['input_ids'].shape)!=(1,args.tokens):
        raise ValueError('pilot document does not provide requested token length')
    write_json(args.output_dir/'input_identity.json',dict(doc_id=doc['doc_id'],text_sha256=doc['text_sha256'],
               input_ids=encoded['input_ids'].tolist(),attention_mask=encoded.get('attention_mask').tolist(),
               tokenizer_files=[identity(path) for path in sorted(args.model_dir.glob('*token*')) if path.is_file()],
               token_selection='complete prefix; all positions included',selection_after_tokenization=False))
    stage(args.output_dir,'loading_model')
    started=time.monotonic()
    base=load_streamed_bf16_model(args.model_dir,'cuda:0',args.output_dir)
    stage(args.output_dir,'model_loaded',seconds=time.monotonic()-started,allocated_bytes=torch.cuda.memory_allocated())
    class Facade(nn.Module):
        def __init__(self,base):
            super().__init__();self.model=base;self.lm_head=nn.Identity();self.config=base.config
    model=Facade(base)
    v5=production_module()
    stage(args.output_dir,'attaching_v5')
    started=time.monotonic()
    with chunked_weight_context(v5,128):
        metadata,audit=attach_v5_fullchain_compatible(model,checkpoint_dir=args.model_dir,device=device,
                      strict_total_shift=True,software_extended=False,trace_layers=None,
                      down_output_width=32,down_shift12_candidate=True)
    validate_attach(metadata)
    metadata.update(lm_head='Identity; never loaded or called',base_forward_only=True)
    write_json(args.output_dir/'v5_attach_metadata.json',metadata)
    model.eval();del base
    torch.cuda.empty_cache()
    stage(args.output_dir,'v5_attached',seconds=time.monotonic()-started,
          allocated_bytes=torch.cuda.memory_allocated(),reserved_bytes=torch.cuda.memory_reserved())
    frozen_buffers=buffer_signature(model)
    encoded={key:value.to(device) for key,value in encoded.items()}
    current_hidden={};rows=[];handles=[];arm={'name':'current','layer':-1}
    observer_state={'active':None};local_rows=[]
    def local_sink(record):
        count=record['count'];E=record['sum_diff2'];S=record['sum_signal2']
        metric=dict(total_elements=record['total_shape_elements'],valid_elements=count,
                    excluded_elements=record['total_shape_elements']-count,nonfinite_elements=0,
                    error_energy=E,signal_energy=S,signed_error_sum=record['sum_diff'],
                    relative_l2_percent=record['relative_l2_percent'],
                    normalized_signed_bias_percent=100*record['normalized_bias'] if record['normalized_bias'] is not None else None,
                    signal_rms=(S/count)**.5 if count else None,absolute_rmse=(E/count)**.5 if count else None,
                    absolute_max=record['max_abs'],zero_signal=record['zero_signal'],
                    empty_valid_domain=count==0,small_signal_threshold=None,small_signal_status='not_frozen')
        row={**{key:doc.get(key) for key in ['doc_id','domain','split','evidence_role','text_sha256','duplicate_cluster']},
             'layer':record['layer'],'node':record['node'],'op':record['op_name'],
             'trajectory':'v5_current_local_paired','metrics':{'current_vs_reference':metric},
             'strict_valid_available':False,'exact_pre_output_comparison':False,
             'counts':dict(total_elements=record['total_shape_elements'],accepted_metric_elements=count,
                           bound_applicable_elements=0,bound_not_evaluated_elements=count),
             'node_metadata':record}
        local_rows.append(row)
        with (args.output_dir/'local_tensor_metrics.jsonl').open('a',encoding='utf8') as stream:
            stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    dynamic_output=args.output_dir/'dynamic_arrays';dynamic_output.mkdir()
    dynamic_current={};dynamic_ordinals={};dynamic_rows=[]
    originals={name:getattr(v5,name) for name in ['prepare_fixed_activation','_kv12_quantize']}
    def trace_dynamic(name):
        def traced(*pos,**kw):
            result=originals[name](*pos,**kw)
            key=(arm['name'],arm['layer'],name)
            ordinal=dynamic_ordinals.get(key,0);dynamic_ordinals[key]=ordinal+1
            coordinate=(arm['layer'],name,ordinal)
            fields=['codes_u8','shifts_u8']+(['zero_points_u8','values_u8'] if name=='prepare_fixed_activation' else ['values_s12'])
            arrays={field:getattr(result,field).detach().cpu().numpy().copy() for field in fields}
            artifact=dynamic_output/f"{arm['name']}_layer{arm['layer']:02d}_{name}_{ordinal:02d}.npz"
            with artifact.open('xb') as stream:np.savez_compressed(stream,**arrays)
            record=dict(arm=arm['name'],layer=arm['layer'],function=name,ordinal=ordinal,artifact=identity(artifact),
                        identity={field:dict(shape=list(array.shape),sha256=hashlib.sha256(array.tobytes()).hexdigest()) for field,array in arrays.items()})
            if arm['name']=='current':dynamic_current[coordinate]=arrays
            else:
                previous=dynamic_current.pop(coordinate)
                record['changed_elements_vs_current']={field:int(np.count_nonzero(array!=previous[field])) for field,array in arrays.items()}
            with (args.output_dir/'dynamic_metadata.jsonl').open('a',encoding='utf8') as stream:
                stream.write(json.dumps(record)+'\n')
            dynamic_rows.append(record)
            return result
        return traced
    for name in originals:setattr(v5,name,trace_dynamic(name))
    output=args.output_dir/'hidden_arrays';output.mkdir()
    def hook(index):
        def callback(module,inputs,result):
            hidden=result[0] if isinstance(result,(tuple,list)) else result
            if tuple(hidden.shape)!=(1,args.tokens,4096) or hidden.dtype!=torch.float32:
                raise ValueError('unexpected hidden shape/dtype at layer '+str(index))
            value=hidden.detach().to('cpu',dtype=torch.float32).numpy().copy()
            if not np.isfinite(value).all():
                raise ValueError('nonfinite hidden tensor at layer '+str(index))
            if arm['name']=='current':
                if index in current_hidden:raise ValueError('decoder layer called more than once')
                current_hidden[index]=value
            else:
                current=current_hidden.pop(index)
                target=output/f'layer{index:02d}.npz'
                with target.open('xb') as stream:np.savez_compressed(stream,current=current,reference=value)
                row={**{key:doc.get(key) for key in ['doc_id','source_id','domain','split','evidence_role','text_sha256','duplicate_cluster']},
                     'layer':index,'node':'decoder_hidden','op':'decoder_block_output','trajectory':'v5_continuous_paired',
                     'target_format':'attention03/mlp05','output_shape':list(value.shape),
                     'output_selection':{'tokens':'all prefix positions','channels':'all 4096'},
                     'output_artifact':identity(target),
                     'metrics':{'current_vs_reference':energy_metrics(current,value)},
                     'counts':{'total_elements':int(value.size)},
                     'limitation':'host FP32 hidden tensor propagation; no exact-rational hidden reference or local node attribution'}
                rows.append(row)
                with (args.output_dir/'tensor_metrics.jsonl').open('a',encoding='utf8') as stream:
                    stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
            stage(args.output_dir,'layer_hidden',arm=arm['name'],layer=index)
        return callback
    def before_layer(index):
        def callback(module,inputs):
            arm['layer']=index
            if observer_state['active'] is not None:observer_state['active'].set_layer(index)
        return callback
    for index,layer in enumerate(model.model.layers):
        handles.append(layer.register_forward_pre_hook(before_layer(index)))
        handles.append(layer.register_forward_hook(hook(index)))
    try:
        for name,policy in [('current',CURRENT),('reference',OUTPUT_ONLY)]:
            arm['name']=name;reset_audit(audit)
            stage(args.output_dir,'forward_started',arm=name)
            started=time.monotonic()
            with torch.inference_mode():
                if name=='current':
                    with local_observer_context(v5,sink=local_sink,doc_id=doc['doc_id'],layer=0) as observer:
                        observer_state['active']=observer
                        result=model.model(**encoded,use_cache=False,return_dict=True)
                        observer.flush(doc['doc_id'])
                    observer_state['active']=None
                else:
                    with arithmetic_context(v5,policy):
                        result=model.model(**encoded,use_cache=False,return_dict=True)
                final=result.last_hidden_state.detach().to('cpu',dtype=torch.float32).numpy()
                with (args.output_dir/f'final_hidden_{name}.npz').open('xb') as stream:np.savez_compressed(stream,hidden=final)
                del result,final
            torch.cuda.synchronize()
            write_json(args.output_dir/f'audit_{name}.json',audit_report(audit,reference=name=='reference'))
            stage(args.output_dir,'forward_completed',arm=name,seconds=time.monotonic()-started)
            if buffer_signature(model)!=frozen_buffers:
                raise AssertionError('shared frozen buffers changed across paired forward')
    finally:
        for name,value in originals.items():setattr(v5,name,value)
        for handle in handles:handle.remove()
    if dynamic_current:raise ValueError('incomplete paired dynamic metadata call geometry')
    if current_hidden or len(rows)!=32:raise ValueError('incomplete 32-layer pairing')
    if before!=code_identities():raise ValueError('consumed source code changed')
    write_json(args.output_dir/'document_summary.json',summarize_documents(rows))
    write_json(args.output_dir/'local_document_summary.json',summarize_documents(local_rows))
    write_json(args.output_dir/'dynamic_metadata_summary.json',dict(events=len(dynamic_rows),
               paired_reference_events=sum(row['arm']=='reference' for row in dynamic_rows),
               changed_elements={field:sum(row.get('changed_elements_vs_current',{}).get(field,0) for row in dynamic_rows)
                                 for field in ['codes_u8','shifts_u8','zero_points_u8','values_u8','values_s12']},
               note='each arm recomputes dynamic codes/shifts/zero points; no frozen activation metadata reused'))
    write_json(args.output_dir/'paired_result.json',dict(execution_state='completed',measured_documents=1,
               formal_eval_documents=0,layers=32,tokens=args.tokens,channels=4096,
               source_unchanged=True,shared_weight_buffers_unchanged=True,
               current_and_reference_dynamic_metadata='recomputed independently by each sequential production forward',
               wall_cost='see supervisor receipt and per-stage timings; not extrapolated to 1024 documents',
               no_task_metrics=True,local_node_comparison=True,local_exact_preoutput_comparison=False,
               local_nodes=sorted({row['node'] for row in local_rows}),local_tensor_cells=len(local_rows),trajectory='v5_continuous_paired'))
    stage(args.output_dir,'completed')
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--documents',type=Path,required=True)
    parser.add_argument('--document-index',type=int,default=0)
    parser.add_argument('--document-count',type=int,default=1)
    parser.add_argument('--tokens',type=int,default=32)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--cpu-check',action='store_true')
    args=parser.parse_args()
    try:
        if args.cpu_check:
            doc=static_check(args)
            import torch
            from numerical_reference.model_compat import production_module
            production_module()
            print(json.dumps(dict(cpu_check='passed',doc_id=doc['doc_id'],tokens=args.tokens,
                                  cuda_initialized=torch.cuda.is_initialized(),gpu_execution_performed=False)))
            code=0
        elif args.worker:
            code=worker(args)
        else:
            raise ValueError('GPU execution requires Root bounded supervisor and explicit --worker')
    except Exception:
        traceback.print_exc();code=1
    raise SystemExit(code)


if __name__=='__main__':main()
