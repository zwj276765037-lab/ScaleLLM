"""Bounded multi-document V5 development qualification; no task scoring."""
from __future__ import annotations
from contextlib import nullcontext
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from run_numerical_fidelity import identity,write_json,energy_metrics,summarize_documents,timestamp


def select_documents(args,read_document):
    if getattr(args,'formal_batch_plan',None):
        from formal_numerical_inputs import load_batch_group
        if not getattr(args,'formal_storage_plan',None):raise ValueError('formal mode requires frozen storage addendum')
        metadata=load_batch_group(args.formal_batch_plan,args.batch_id,storage_plan=args.formal_storage_plan)
        args._formal_metadata=metadata
        return metadata['documents']
    if not 1<=args.document_count<=4:
        raise ValueError('this development stage supports one to four independent documents')
    docs=[read_document(args.documents,args.document_index+i) for i in range(args.document_count)]
    if len({d['doc_id'] for d in docs})!=len(docs) or len({d['duplicate_cluster'] for d in docs})!=len(docs):
        raise ValueError('document/cluster duplicated in development stream')
    return docs


def audit_configuration(args,formal_metadata=None):
    layers=[int(value) for value in args.raw_value_audit_layers.split(',') if value.strip()]
    if len(set(layers))!=len(layers) or any(value<0 or value>31 for value in layers):
        raise ValueError('raw value audit layers must be unique in0..31')
    if not 1<=args.witness_max_doc_mib<=64 or not args.witness_max_doc_mib<=args.witness_max_at_mib<=96:
        raise ValueError('witness budgets must stay <=64MiB/doc and <=96MiB/attempt')
    if formal_metadata is not None:
        policy=formal_metadata['storage_policy']
        if layers!=[0,15,31] or any(row['raw_dynamic_value_layers']!=layers for row in policy['records']):
            raise ValueError('formal raw value layers must match frozen storage policy')
        if (args.witness_max_doc_mib,args.witness_max_at_mib)!=(policy['witness_max_doc_mib'],policy['witness_max_at_mib']):
            raise ValueError('formal witness budgets must match frozen storage policy')
    return layers


def validate_document_coverage(doc_id,hidden_rows,local_rows,dynamic_rows):
    """Reject shared omissions and duplicate coordinates before marking a doc done."""
    if any(row['doc_id']!=doc_id for row in [*hidden_rows,*local_rows,*dynamic_rows]):
        raise ValueError('cross-document coverage contamination')
    hidden=[row['layer'] for row in hidden_rows]
    sites={('linear',op) for op in ['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']}
    sites|={('rope','query_rope'),('rope','key_rope'),('qk','qk'),('softmax','softmax'),('pv','pv')}
    local=[(row['layer'],row['node'],row['op']) for row in local_rows]
    expected_local={(layer,node,op) for layer in range(32) for node,op in sites}
    if len(hidden)!=32 or set(hidden)!=set(range(32)):raise ValueError('expected32 unique hidden layer coordinates')
    if len(local)!=384 or set(local)!=expected_local:raise ValueError('expected384 unique local coordinates')
    expected_dynamic={(arm,layer,function,ordinal) for arm in ['current','reference'] for layer in range(32)
                      for function,count in [('prepare_fixed_activation',4),('_kv12_quantize',2)] for ordinal in range(count)}
    dynamic=[(row['arm'],row['layer'],row['function'],row['ordinal']) for row in dynamic_rows]
    if len(dynamic)!=384 or set(dynamic)!=expected_dynamic:raise ValueError('expected192 dynamic coordinates per arm')
    return dict(hidden_unique_layers=32,local_unique_coordinates=384,dynamic_unique_coordinates_per_arm=192,
                per_layer_dynamic_activation_calls=4,per_layer_dynamic_kv_calls=2,complete=True)


def tensor_row(doc,layer,node,op,trajectory,current,reference,artifact=None):
    return {**{key:doc.get(key) for key in ['doc_id','source_id','domain','split','evidence_role','text_sha256','duplicate_cluster']},
            'layer':layer,'node':node,'op':op,'trajectory':trajectory,'output_shape':list(current.shape),
            'output_selection':{'tokens':'all real unpadded prefix positions','channels':'all4096'},
            'output_artifact':artifact,'metrics':{'current_vs_reference':energy_metrics(current,reference)},
            'counts':{'total_elements':int(current.size)},
            'limitation':'common host FP32 propagation; no exact-rational hidden reference'}


def stream_worker(args,helpers):
    import numpy as np
    import torch
    import torch.nn as nn
    from transformers import AutoTokenizer
    from capture_real_inputs import load_streamed_bf16_model
    from numerical_reference.model_compat import production_module,attach_v5_fullchain_compatible
    from numerical_reference.policy import OUTPUT_ONLY
    from numerical_reference.gpu_reference import arithmetic_context
    from numerical_reference.chunked_quantization import chunked_weight_context
    from numerical_reference.local_observer import local_observer_context
    from numerical_reference.node_witnesses import NodeWitnesses
    stage=helpers['stage'];code_identities=helpers['code_identities']
    torch.set_num_threads(1)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    helpers['static_check'](args)
    docs=select_documents(args,helpers['read_document'])
    formal=bool(getattr(args,'formal_batch_plan',None))
    audit_indices=([i for i,d in enumerate(docs) if d['doc_id'] in args._formal_metadata['audit_doc_ids']] if formal
                   else [int(x) for x in args.audit_document_indices.split(',') if x.strip()])
    if len(set(audit_indices))!=len(audit_indices) or any(i<0 or i>=len(docs) for i in audit_indices):
        raise ValueError('preselected audit indices must be unique within requested document batch')
    if len(audit_indices)>1 or (not formal and len(audit_indices)!=1):raise ValueError('at most one predeclared raw-audit document per formal batch')
    audit_ids=[docs[i]['doc_id'] for i in audit_indices]
    raw_value_layers=audit_configuration(args,args._formal_metadata if formal else None)
    before=code_identities()
    write_json(args.output_dir/'paired_worker_manifest.json',dict(schema='m005_v3_document_stream_model_v1',started_at=timestamp(),
        pid=os.getpid(),command=sys.argv,code=before,document_source=(args._formal_metadata['source_plan'] if formal else identity(args.documents)),
        formal_batch_id=args.batch_id if formal else None,
        formal_batch_ids=args._formal_metadata['batch_ids'] if formal else None,
        logical_batch_documents=args._formal_metadata.get('logical_batch_documents') if formal else None,
        formal_storage_source=args._formal_metadata['storage_source'] if formal else None,
        selected_documents=[{key:d[key] for key in ['doc_id','domain','split','evidence_role','text_sha256','duplicate_cluster']} for d in docs],
        maximum_tokens=args.tokens,model_loaded_once=True,formal_eval_documents=0,
        planned_formal_documents=len(docs) if formal else 0,full_formal_target=1024 if formal else None,
        audit_document_ids=audit_ids,raw_value_audit_layers=raw_value_layers,witness_samples_per_coordinate=16,witness_seed=0,
        witness_max_doc_bytes=args.witness_max_doc_mib<<20,witness_max_at_bytes=args.witness_max_at_mib<<20,
        raw_policy=args._formal_metadata['storage_policy'] if formal else 'auditdoc0 all32 hidden/meta,values0/15/31; other docs statistics only',
        scope='bounded formal batch,not full1024 completion; no ACC/PPL' if formal else 'one to four development docs; no ACC/PPL',
        versions={k:importlib.metadata.version(k) for k in ['torch','transformers','accelerate','triton','numpy']},
        cuda_visible_devices=os.environ.get('CUDA_VISIBLE_DEVICES'),checkpoint_dir=str(args.model_dir.resolve())))
    tokenizer=None if formal else AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
    write_json(args.output_dir/'tokenizer_identity.json',dict(files=args._formal_metadata['tokenizer_files'] if formal else [identity(p) for p in sorted(args.model_dir.glob('*token*')) if p.is_file()],
               tokenization_performed=not formal,document_source=args._formal_metadata['source_manifest'] if formal else identity(args.documents)))
    device=torch.device('cuda:0')
    stage(args.output_dir,'loading_model');begin=time.monotonic()
    base=load_streamed_bf16_model(args.model_dir,'cuda:0',args.output_dir)
    stage(args.output_dir,'model_loaded',seconds=time.monotonic()-begin,allocated_bytes=torch.cuda.memory_allocated())
    class Facade(nn.Module):
        def __init__(self,base):super().__init__();self.model=base;self.lm_head=nn.Identity();self.config=base.config
    model=Facade(base);v5=production_module()
    stage(args.output_dir,'attaching_v5');begin=time.monotonic()
    with chunked_weight_context(v5,128):
        metadata,audit=attach_v5_fullchain_compatible(model,checkpoint_dir=args.model_dir,device=device,
            strict_total_shift=True,software_extended=False,trace_layers=None,down_output_width=32,down_shift12_candidate=True)
    helpers['validate_attach'](metadata);metadata.update(lm_head='Identity; never loaded/called',base_forward_only=True)
    write_json(args.output_dir/'v5_attach_metadata.json',metadata);model.eval();del base;torch.cuda.empty_cache()
    stage(args.output_dir,'v5_attached',seconds=time.monotonic()-begin,allocated_bytes=torch.cuda.memory_allocated())
    frozen_buffers=helpers['buffer_signature'](model)
    witness=NodeWitnesses(args.output_dir/'node_witnesses',audit_doc_ids=audit_ids,samples_per_coordinate=16,seed=0,max_doc_bytes=args.witness_max_doc_mib<<20,max_at_bytes=args.witness_max_at_mib<<20) if audit_ids else None
    write_json(args.output_dir/'node_witness_policy.json',dict(audit_doc_ids=audit_ids,collection_enabled=bool(audit_ids),
               absent_collection_reason=None if audit_ids else 'no preselected raw-audit document in this immutable batch'))
    state={'arm':'current','layer':-1,'observer':None,'doc':None}
    current_hidden={};all_hidden=[];all_local=[];all_final=[];doc_results=[]
    handles=[]
    for index,layer in enumerate(model.model.layers):
        def pre(module,inputs,index=index):
            state['layer']=index
            if state['observer'] is not None:state['observer'].set_layer(index)
        def post(module,inputs,result,index=index):
            value=result[0] if isinstance(result,(tuple,list)) else result
            if tuple(value.shape)!=(1,state['tokens'],4096) or value.dtype!=torch.float32:
                raise ValueError('unexpected decoder hidden geometry/dtype')
            value=value.detach().to('cpu',dtype=torch.float32).numpy().copy()
            if not np.isfinite(value).all():raise ValueError('nonfinite hidden tensor')
            if state['arm']=='current':current_hidden[index]=value
            else:
                current=current_hidden.pop(index);artifact=None
                if state['audited'] and index in state['hidden_layers']:
                    target=state['directory']/f'hidden_layer{index:02d}.npz'
                    with target.open('xb') as stream:np.savez_compressed(stream,current=current,reference=value)
                    artifact=identity(target)
                row=tensor_row(state['doc'],index,'decoder_hidden','decoder_block_output','v5_continuous_paired',current,value,artifact)
                all_hidden.append(row)
                with (args.output_dir/'tensor_metrics.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps(row,allow_nan=False)+'\n')
            stage(args.output_dir,'layer_hidden',doc_id=state['doc']['doc_id'],arm=state['arm'],layer=index)
        handles.extend([layer.register_forward_pre_hook(pre),layer.register_forward_hook(post)])
    original_dynamic={name:getattr(v5,name) for name in ['prepare_fixed_activation','_kv12_quantize']}
    dynamic_current={};ordinals={};dynamic_records=[]
    def trace(name):
        def wrapped(*pos,**kw):
            result=original_dynamic[name](*pos,**kw)
            key=(state['arm'],state['layer'],name);ordinal=ordinals.get(key,0);ordinals[key]=ordinal+1
            coordinate=(state['layer'],name,ordinal)
            fields=['codes_u8','shifts_u8']+(['zero_points_u8','values_u8'] if name=='prepare_fixed_activation' else ['values_s12'])
            arrays={field:getattr(result,field).detach().cpu().numpy().copy() for field in fields}
            record=dict(doc_id=state['doc']['doc_id'],arm=state['arm'],layer=state['layer'],function=name,ordinal=ordinal,
                        identity={field:dict(shape=list(a.shape),sha256=hashlib.sha256(a.tobytes()).hexdigest()) for field,a in arrays.items()},artifact=None)
            if state['audited']:
                saved=arrays if state['layer'] in raw_value_layers else {key:value for key,value in arrays.items() if not key.startswith('values_')}
                target=state['directory']/f"dynamic_{state['arm']}_layer{state['layer']:02d}_{name}_{ordinal:02d}.npz"
                with target.open('xb') as stream:np.savez_compressed(stream,**saved)
                record['artifact']=identity(target);record['saved_fields']=list(saved)
            if state['arm']=='current':dynamic_current[coordinate]=arrays
            else:
                previous=dynamic_current.pop(coordinate)
                record['changed_elements_vs_current']={field:int(np.count_nonzero(a!=previous[field])) for field,a in arrays.items()}
            dynamic_records.append(record)
            with (args.output_dir/'dynamic_metadata.jsonl').open('a') as stream:stream.write(json.dumps(record)+'\n')
            return result
        return wrapped
    for name in original_dynamic:setattr(v5,name,trace(name))
    def local_sink(record):
        n=record['count'];E=record['sum_diff2'];S=record['sum_signal2']
        metric=dict(total_elements=record['total_shape_elements'],valid_elements=n,excluded_elements=record['total_shape_elements']-n,
                    nonfinite_elements=0,error_energy=E,signal_energy=S,signed_error_sum=record['sum_diff'],
                    relative_l2_percent=record['relative_l2_percent'],normalized_signed_bias_percent=100*record['normalized_bias'] if record['normalized_bias'] is not None else None,
                    signal_rms=(S/n)**.5 if n else None,absolute_rmse=(E/n)**.5 if n else None,absolute_max=record['max_abs'],zero_signal=record['zero_signal'],
                    empty_valid_domain=n==0,small_signal_threshold=None)
        row={**{key:state['doc'].get(key) for key in ['doc_id','domain','split','evidence_role','text_sha256','duplicate_cluster']},
             'layer':record['layer'],'node':record['node'],'op':record['op_name'],'trajectory':'v5_current_local_paired',
             'metrics':{'current_vs_reference':metric},'strict_valid_available':False,'exact_pre_output_comparison':False,
             'counts':dict(total_elements=record['total_shape_elements'],accepted_metric_elements=n,bound_not_evaluated_elements=n),
             'node_metadata':record}
        all_local.append(row)
        with (args.output_dir/'local_tensor_metrics.jsonl').open('a') as stream:stream.write(json.dumps(row,allow_nan=False)+'\n')
    try:
        for offset,doc in enumerate(docs):
            directory=args.output_dir/'documents'/f'doc{offset:04d}';directory.mkdir(parents=True)
            policy_lookup={record['doc_id']:record for record in args._formal_metadata['storage_policy']['records']} if formal else {}
            state.update(doc=doc,directory=directory,audited=doc['doc_id'] in audit_ids,layer=-1,
                         hidden_layers=policy_lookup.get(doc['doc_id'],{}).get('raw_hidden_layers',[]) if formal else list(range(32)))
            if formal:
                from formal_numerical_inputs import read_token_artifact
                token_arrays=read_token_artifact(doc)
                encoded={key:torch.from_numpy(value[None,:]) for key,value in token_arrays.items()}
            else:
                encoded=tokenizer(doc['text'],return_tensors='pt',truncation=True,max_length=args.tokens,add_special_tokens=True,padding=False)
            tokens=int(encoded['input_ids'].shape[1]);state['tokens']=tokens
            if tuple(encoded['input_ids'].shape)!=(1,tokens) or not 1<=tokens<=args.tokens:raise ValueError('document token geometry')
            write_json(directory/'input_identity.json',dict(doc_id=doc['doc_id'],text_sha256=doc['text_sha256'],tokens=tokens,
                input_ids=encoded['input_ids'].tolist(),attention_mask=encoded['attention_mask'].tolist(),maximum_tokens=args.tokens,audited=state['audited'],
                token_artifact=doc.get('token_artifact'),retokenized=not formal))
            encoded={key:value.to(device) for key,value in encoded.items()}
            ordinals.clear();dynamic_current.clear();current_hidden.clear();start_dynamic=len(dynamic_records)
            start_hidden=len(all_hidden);start_local=len(all_local);doc_begin=time.monotonic()
            for name in ('current','reference'):
                state['arm']=name;helpers['reset_audit'](audit);begin=time.monotonic()
                stage(args.output_dir,'forward_started',doc_id=doc['doc_id'],arm=name,tokens=tokens)
                with torch.inference_mode():
                    if name=='current':
                        with local_observer_context(v5,sink=local_sink,doc_id=doc['doc_id'],layer=0) as observer:
                            state['observer']=observer
                            with (witness.context(observer) if witness is not None else nullcontext()):
                                result=model.model(**encoded,use_cache=False,return_dict=True)
                            observer.flush(doc['doc_id'])
                        state['observer']=None
                    else:
                        with arithmetic_context(v5,OUTPUT_ONLY):result=model.model(**encoded,use_cache=False,return_dict=True)
                    final=result.last_hidden_state.detach().to('cpu',dtype=torch.float32).numpy().copy();del result
                if not np.isfinite(final).all():raise ValueError('nonfinite final norm')
                if state['audited']:
                    with (directory/f'final_hidden_{name}.npz').open('xb') as stream:np.savez_compressed(stream,hidden=final)
                if name=='current':current_final=final
                else:
                    row=tensor_row(doc,31,'final_norm','host_final_norm','v5_continuous_paired',current_final,final)
                    all_final.append(row);write_json(directory/'final_norm_comparison.json',row)
                    del current_final
                write_json(directory/f'audit_{name}.json',helpers['audit_report'](audit,reference=name=='reference'))
                torch.cuda.synchronize();stage(args.output_dir,'forward_completed',doc_id=doc['doc_id'],arm=name,seconds=time.monotonic()-begin)
                if helpers['buffer_signature'](model)!=frozen_buffers:raise ValueError('shared weight buffers changed')
            if current_hidden or dynamic_current:raise ValueError('incomplete document pairing')
            selected_dynamic=dynamic_records[start_dynamic:]
            coverage=validate_document_coverage(doc['doc_id'],all_hidden[start_hidden:],all_local[start_local:],selected_dynamic)
            changes={field:sum(row.get('changed_elements_vs_current',{}).get(field,0) for row in selected_dynamic)
                     for field in ['codes_u8','shifts_u8','zero_points_u8','values_u8','values_s12']}
            report=dict(doc_id=doc['doc_id'],tokens=tokens,seconds=time.monotonic()-doc_begin,audited=state['audited'],
                        dynamic_events=len(selected_dynamic),dynamic_changed_elements=changes,
                        coverage=coverage,
                        final_norm_relative_l2_percent=all_final[-1]['metrics']['current_vs_reference']['relative_l2_percent'])
            doc_results.append(report);write_json(directory/'document_result.json',report)
            stage(args.output_dir,'document_completed',**report)
            del encoded,final
    finally:
        state['observer']=None
        for name,value in original_dynamic.items():setattr(v5,name,value)
        for handle in handles:handle.remove()
    if before!=code_identities():raise ValueError('consumed source changed')
    write_json(args.output_dir/'document_summary.json',summarize_documents(all_hidden))
    write_json(args.output_dir/'local_document_summary.json',summarize_documents(all_local))
    write_json(args.output_dir/'final_norm_document_summary.json',summarize_documents(all_final))
    write_json(args.output_dir/'paired_result.json',dict(execution_state='completed',measured_documents=len(doc_results),formal_eval_documents=len(doc_results) if formal else 0,
               full_formal_target=1024 if formal else None,formal_batch_id=args.batch_id if formal else None,
               formal_batch_ids=args._formal_metadata['batch_ids'] if formal else None,
        formal_storage_source=args._formal_metadata['storage_source'] if formal else None,
               documents=doc_results,layers=32,maximum_tokens=args.tokens,model_loaded_once=True,source_unchanged=True,
               shared_weight_buffers_unchanged=True,no_task_metrics=True,local_exact_preoutput_comparison=False,
               local_tensor_cells=len(all_local),hidden_tensor_cells=len(all_hidden),audit_document_ids=audit_ids,
               uncertainty='partial bounded batch; full fixed-quota target not yet complete' if formal else 'development descriptive observations only; no formal P95/P99 inference'))
    stage(args.output_dir,'completed',documents=len(doc_results))
    return 0
