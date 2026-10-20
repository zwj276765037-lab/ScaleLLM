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
    paths=[Path(__file__),HERE/'run_numerical_fidelity.py',HERE/'numerical_model_stream.py',HERE/'formal_numerical_inputs.py',HERE/'formal_storage_plan.py',HERE/'capture_real_inputs.py',
           HERE/'prepare_replay_data.py',HERE/'run_local_experiment.py',
           *[HERE/'numerical_reference'/name for name in ['policy.py','current_nodes.py','exact_reductions.py','model_compat.py','gpu_reference.py','chunked_quantization.py','local_observer.py','node_witnesses.py']],
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
    if not getattr(args,'formal_batch_plan',None) and not 1<=args.document_count<=4:
        raise ValueError('development qualification supports one to four documents')
    if not 1<=args.tokens<=128:
        raise ValueError('current production sequence limit is 128')
    from numerical_model_stream import select_documents,audit_configuration
    selected=select_documents(args,read_document)
    audit_configuration(args,args._formal_metadata if getattr(args,'formal_batch_plan',None) else None)
    doc=selected[0]
    if getattr(args,'formal_batch_plan',None) and any(d['tokens']>args.tokens for d in selected):
        raise ValueError('cannot truncate frozen formal token artifacts to a smaller CLI limit')
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
    from numerical_model_stream import stream_worker
    return stream_worker(args,{name:globals()[name] for name in ['stage','code_identities','read_document','static_check',
                          'validate_attach','reset_audit','audit_report','buffer_signature']})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--documents',type=Path)
    parser.add_argument('--formal-batch-plan',type=Path)
    parser.add_argument('--formal-storage-plan',type=Path)
    parser.add_argument('--batch-id','--batch-ids',dest='batch_id',help='one logical ID, or consecutive CSV IDs; max80docs and one audit')
    parser.add_argument('--document-index',type=int,default=0)
    parser.add_argument('--document-count',type=int,default=1)
    parser.add_argument('--audit-document-indices',default='0')
    parser.add_argument('--raw-audit-layers','--raw-value-audit-layers',dest='raw_value_audit_layers',default='0,15,31')
    parser.add_argument('--witness-max-doc-mib',type=int,default=64)
    parser.add_argument('--witness-max-at-mib',type=int,default=96)
    parser.add_argument('--tokens',type=int,default=32)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--cpu-check',action='store_true')
    args=parser.parse_args()
    try:
        if args.cpu_check:
            doc=static_check(args)
            from numerical_model_stream import select_documents
            selected=select_documents(args,read_document)
            import torch
            from numerical_reference.model_compat import production_module
            production_module()
            if args.formal_batch_plan:
                lengths=[row['tokens'] for row in selected]
            else:
                from transformers import AutoTokenizer
                tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
                lengths=[len(tokenizer(row['text'],truncation=True,max_length=args.tokens,padding=False,add_special_tokens=True)['input_ids']) for row in selected]
            print(json.dumps(dict(cpu_check='passed',doc_id=doc['doc_id'],document_count=len(selected),document_ids=[row['doc_id'] for row in selected],tokens=args.tokens,actual_token_lengths=lengths,
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
