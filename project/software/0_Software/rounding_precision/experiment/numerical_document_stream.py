"""Prepare immutable per-document token arrays for later numerical streaming.

This CPU utility performs no model inference or metric evaluation. Documents
remain independent source units; no packing across documents or padding into
fake tokens. The production 128-position restriction remains explicit.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import traceback
from run_numerical_fidelity import cpu_supervise,identity,write_json


ROLE={'train':'calibration','dev':'development','eval':'formal_eval'}


def documents(path,split):
    """Read a frozen role; reject ID/cluster reuse and changed original text."""
    if split not in ROLE:raise ValueError('unknown role')
    ids=set();clusters=set()
    with Path(path).open(encoding='utf8') as stream:
        for index,line in enumerate(stream):
            row=json.loads(line)
            if row.get('split')!=split or row.get('evidence_role')!=ROLE[split]:
                raise ValueError('frozen document role mismatch')
            if row['doc_id'] in ids or row['duplicate_cluster'] in clusters:
                raise ValueError('duplicate source document or cluster in streaming role')
            if hashlib.sha256(row['text'].encode()).hexdigest()!=row['text_sha256']:
                raise ValueError('frozen text identity changed')
            ids.add(row['doc_id']);clusters.add(row['duplicate_cluster'])
            yield index,row


def tokenize_document(tokenizer,text,max_tokens):
    import numpy as np
    if not 1<=max_tokens<=128:raise ValueError('production token limit is128')
    encoded=tokenizer(text,add_special_tokens=True,truncation=True,max_length=max_tokens,
                      padding=False,return_attention_mask=True)
    ids=np.asarray(encoded['input_ids'],dtype=np.int64)
    mask=np.asarray(encoded.get('attention_mask',np.ones(ids.shape,dtype=np.int64)),dtype=np.int64)
    if ids.ndim!=1 or not 1<=len(ids)<=max_tokens or mask.shape!=ids.shape or not np.all(mask==1):
        raise ValueError('one unpadded nonempty document prefix required')
    return dict(input_ids=ids,attention_mask=mask,position_ids=np.arange(len(ids),dtype=np.int64))


def prepare_worker(args):
    import numpy as np
    from transformers import AutoTokenizer
    if args.maximum_documents<1:raise ValueError('positive document bound required')
    tokenizer=AutoTokenizer.from_pretrained(str(args.model_dir),local_files_only=True,trust_remote_code=False)
    array_dir=args.output_dir/'token_arrays';array_dir.mkdir()
    cases=[];token_total=0;domain_counts={};lengths=[]
    # Audit selection uses source IDs only, before any numerical outputs exist.
    for index,doc in documents(args.documents,args.split):
        if index>=args.maximum_documents:break
        arrays=tokenize_document(tokenizer,doc['text'],args.max_tokens)
        target=array_dir/f'document_{index:06d}.npz'
        with target.open('xb') as stream:np.savez_compressed(stream,**arrays)
        count=len(arrays['input_ids']);token_total+=count;lengths.append(count)
        domain_counts[doc['domain']]=domain_counts.get(doc['domain'],0)+1
        audited=int(hashlib.sha256(f"{args.audit_seed}:{doc['doc_id']}".encode()).hexdigest(),16)%args.audit_modulus==0
        cases.append({**{key:doc[key] for key in ['doc_id','source_id','source_asset','domain','split','evidence_role','text_sha256','normalized_text_sha256','duplicate_cluster']},
                      'source_index':index,'token_artifact':identity(target),'tokens':count,
                      'selection':{'positions':'all unpadded prefix positions','maximum_positions':args.max_tokens,
                                   'source_document_truncated':None,'note':'full original token length not computed; this is a bounded prefix'},
                      'raw_tensor_audit_selected':audited})
    if not cases:raise ValueError('no actual prepared documents')
    manifest=dict(schema='m005_numerical_document_stream_v1',documents=cases,prepared_documents=len(cases),
                  numerical_measured_documents=0,model_inference_performed=False,domain_counts=domain_counts,
                  input_source=identity(args.documents),max_tokens=args.max_tokens,total_real_prefix_tokens=token_total,
                  token_length_summary={'minimum':min(lengths),'maximum':max(lengths),'mean':sum(lengths)/len(lengths)},
                  tokenizer_files=[identity(p) for p in sorted(args.model_dir.glob('*token*')) if p.is_file()],
                  audit_selection={'method':'sha256(seed:doc_id) modulo modulus ==0; fixed before numerical results',
                                   'seed':args.audit_seed,'modulus':args.audit_modulus,
                                   'selected_documents':sum(c['raw_tensor_audit_selected'] for c in cases),
                                   'scope':'candidate document audit membership; node/token/channel audit positions still require frozen design'},
                  streaming_contract={'model_weights':'load once per bounded job; same immutable quantized objects for both arms',
                                      'order':'complete one current/reference document pair before releasing its tensors',
                                      'statistics':'local tensors and continuous hidden outputs remain separate; document-cluster quantiles',
                                      'raw_storage':'full hidden/node arrays only for preselected audit subset; other documents keep reduced energy/bias/max/counter statistics',
                                      'sampling_units':'documents are operational source clusters; tokens/tensors/scalars are coverage only',
                                      'long_sequences':'more than128 positions unsupported by this production path; no extrapolated long-context result'},
                  historical_exposure='inherits frozen input limitation; text/URL clusters do not certify semantic independence or all-history holdout')
    write_json(args.output_dir/'frozen_document_stream.json',manifest)
    print(json.dumps({key:manifest[key] for key in ['prepared_documents','numerical_measured_documents','domain_counts','total_real_prefix_tokens','token_length_summary']}))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--documents',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--split',choices=list(ROLE),required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--max-tokens',type=int,default=128)
    parser.add_argument('--maximum-documents',type=int,default=1024)
    parser.add_argument('--audit-seed',type=int,default=2026101903)
    parser.add_argument('--audit-modulus',type=int,default=64)
    parser.add_argument('--wall-seconds',type=int,default=300)
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    try:
        if args.audit_modulus<1:raise ValueError('audit modulus must be positive')
        code=prepare_worker(args) if args.worker else cpu_supervise(args,__file__,'document_stream')
    except Exception:
        traceback.print_exc();code=1
    raise SystemExit(code)


if __name__=='__main__':main()
