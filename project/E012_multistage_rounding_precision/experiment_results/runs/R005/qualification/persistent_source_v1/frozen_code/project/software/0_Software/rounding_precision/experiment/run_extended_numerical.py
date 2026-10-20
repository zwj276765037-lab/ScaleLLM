"""R005 MLP/full-vocabulary capture. Root's bounded supervisor launches --worker.

CPU qualification imports production interfaces without initializing CUDA.
Formal token artifacts and audit selection retain their R004 frozen identities.
"""
from __future__ import annotations
import argparse
import importlib
import json
from pathlib import Path
import traceback
from run_numerical_fidelity import identity,write_json
import run_paired_numerical_model as prior

HERE=Path(__file__).resolve().parent


def source_identities(args):
    paths=[Path(row['path']) for row in prior.code_identities()]
    paths.extend([Path(__file__),HERE/'extended_numerical_stream.py'])
    for name in (args.mlp_module,args.logit_module):
        module=importlib.import_module(name)
        paths.append(Path(module.__file__).resolve())
    return [identity(path) for path in dict.fromkeys(paths)]


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir',type=Path,required=True)
    p.add_argument('--documents',type=Path)
    p.add_argument('--formal-batch-plan',type=Path)
    p.add_argument('--formal-storage-plan',type=Path)
    p.add_argument('--batch-id','--batch-ids',dest='batch_id')
    p.add_argument('--document-index',type=int,default=0)
    p.add_argument('--document-count',type=int,default=1)
    p.add_argument('--audit-document-indices',default='0')
    p.add_argument('--raw-audit-layers','--raw-value-audit-layers',dest='raw_value_audit_layers',default='0,15,31')
    p.add_argument('--witness-max-doc-mib',type=int,default=64)
    p.add_argument('--witness-max-at-mib',type=int,default=96)
    p.add_argument('--tokens',type=int,default=128)
    p.add_argument('--mlp-module',default='mlp_numerical_extension')
    p.add_argument('--logit-module',default='logit_numerical_extension')
    p.add_argument('--qualify-logit-chunks',action='store_true',help='development pilot first document only')
    p.add_argument('--readonly-baseline',type=Path,help='development pilot only; compare saved decoder outputs to prior immutable capture')
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--worker',action='store_true')
    p.add_argument('--cpu-check',action='store_true')
    return p


def static_check(args):
    if args.qualify_logit_chunks and args.formal_batch_plan:
        raise ValueError('all-score chunk qualification belongs only to development pilot')
    if args.readonly_baseline and args.formal_batch_plan:
        raise ValueError('read-only baseline qualification belongs only to development pilot')
    doc=prior.static_check(args)
    # Import/API qualification is CPU-only and does not claim 8B GPU validation.
    mlp=importlib.import_module(args.mlp_module)
    logit=importlib.import_module(args.logit_module)
    for name in ['MLPNumericalObserver','row_coordinate','expected_coordinates']:
        if not callable(getattr(mlp,name,None)):raise ValueError('MLP interface missing '+name)
    if len(set(mlp.expected_coordinates(layers=32)))!=416:raise ValueError('MLP contract requires416coordinates')
    for name in ['load_output_head','measure_logits','qualify_chunks']:
        if not callable(getattr(logit,name,None)):raise ValueError('logit interface missing '+name)
    return doc


def worker(args):
    from extended_numerical_stream import extended_worker
    helpers={name:getattr(prior,name) for name in ['stage','read_document','validate_attach','reset_audit','audit_report','buffer_signature']}
    helpers.update(static_check=static_check,code_identities=lambda:source_identities(args))
    return extended_worker(args,helpers)


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.cpu_check:
            static_check(args)
            from numerical_model_stream import select_documents
            selected=select_documents(args,prior.read_document)
            import torch
            from numerical_reference.model_compat import production_module
            production_module()
            if args.formal_batch_plan:lengths=[doc['tokens'] for doc in selected]
            else:
                from transformers import AutoTokenizer
                tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
                lengths=[len(tokenizer(doc['text'],truncation=True,max_length=args.tokens,padding=False,add_special_tokens=True)['input_ids']) for doc in selected]
            result=dict(cpu_check='passed',schema='m005_r005_extended_cpu_check_v1',document_ids=[d['doc_id'] for d in selected],
                        document_count=len(selected),actual_token_lengths=lengths,mlp_rows_per_document=416,
                        full_vocab_size=128256,code=source_identities(args),cuda_initialized=torch.cuda.is_initialized(),gpu_execution_performed=False)
            if result['cuda_initialized']:raise ValueError('CPU check initialized CUDA')
            args.output_dir.mkdir(parents=True,exist_ok=True)
            write_json(args.output_dir/'extended_cpu_check.json',result)
            print(json.dumps(result));return 0
        if args.worker:return worker(args)
        raise ValueError('GPU execution requires Root supervisor and explicit --worker')
    except Exception:
        traceback.print_exc();return 1


if __name__=='__main__':raise SystemExit(main())
