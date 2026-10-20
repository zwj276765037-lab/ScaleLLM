"""Freeze/replay formal input batches without reselecting or retokenizing documents."""
from __future__ import annotations
import argparse
from collections import deque,Counter
import hashlib
import json
from pathlib import Path
import traceback
from run_numerical_fidelity import cpu_supervise,identity,write_json

DOMAIN_COUNTS={'web':512,'news':256,'reviews':256}
TOKEN_KEYS={'input_ids','attention_mask','position_ids'}


def read_token_artifact(doc):
    import numpy as np
    source=doc['token_artifact'];path=Path(source['path'])
    if identity(path)['sha256']!=source['sha256']:raise ValueError('frozen token artifact hash mismatch')
    with np.load(path,allow_pickle=False) as archive:
        if set(archive.files)!=TOKEN_KEYS:raise ValueError('token artifact array set mismatch')
        arrays={key:archive[key].copy() for key in archive.files}
    size=doc['tokens']
    if type(size) is not int or not 1<=size<=128:raise ValueError('actual token count outside production domain')
    if any(a.dtype!=np.int64 or a.shape!=(size,) for a in arrays.values()):raise ValueError('frozen token array dtype/shape mismatch')
    if not np.all(arrays['attention_mask']==1) or not np.array_equal(arrays['position_ids'],np.arange(size)):
        raise ValueError('formal inputs require original unpadded prefix positions')
    if np.any(arrays['input_ids']<0) or np.any(arrays['input_ids']>=128256):raise ValueError('token ID outside fixed checkpoint vocabulary')
    return arrays


def build_plan(stream_manifest,max_documents=16,expected_counts=None):
    expected_counts=DOMAIN_COUNTS if expected_counts is None else dict(expected_counts)
    if type(max_documents) is not int or not 1<=max_documents<=16:raise ValueError('first formal stage batch limit is16')
    source=Path(stream_manifest);stream=json.loads(source.read_text());docs=stream['documents']
    if stream.get('schema')!='m005_numerical_document_stream_v1':raise ValueError('frozen token stream schema mismatch')
    if set(expected_counts)!=set(DOMAIN_COUNTS):raise ValueError('unexpected data-domain frame')
    if Counter(d['domain'] for d in docs)!=Counter(expected_counts):raise ValueError('frozen domain quotas differ')
    if len({d['doc_id'] for d in docs})!=len(docs) or len({d['duplicate_cluster'] for d in docs})!=len(docs):
        raise ValueError('duplicate source document/cluster in formal target')
    if any(d['split']!='eval' or d['evidence_role']!='formal_eval' for d in docs):raise ValueError('formal target role mismatch')
    prefixes=set()
    for doc in docs:
        arrays=read_token_artifact(doc);key=hashlib.sha256(arrays['input_ids'].tobytes()).hexdigest()
        if key in prefixes:raise ValueError('identical frozen model input prefixes in formal target')
        prefixes.add(key)
    queues={domain:deque(i for i,d in enumerate(docs) if d['domain']==domain) for domain in expected_counts}
    order=[]
    while any(queues.values()):
        for domain,count in [('web',2),('news',1),('reviews',1)]:
            for _ in range(count):
                if queues.get(domain):order.append(queues[domain].popleft())
    if len(order)!=len(docs):raise ValueError('weighted order lost frozen documents')
    batches=[];current=[];audits=0
    def flush():
        nonlocal current,audits
        if not current:return
        selected=[docs[i] for i in current]
        batches.append(dict(batch_id=f'B{len(batches)+1:03d}',source_indices=current,
            doc_ids=[d['doc_id'] for d in selected],domain_counts=dict(Counter(d['domain'] for d in selected)),
            audit_doc_ids=[d['doc_id'] for d in selected if d['raw_tensor_audit_selected']],
            actual_token_lengths=[d['tokens'] for d in selected],selected_documents=len(selected)))
        current=[];audits=0
    for index in order:
        audit=int(docs[index]['raw_tensor_audit_selected'])
        if len(current)>=max_documents or (audit and audits):flush()
        current.append(index);audits+=audit
    flush()
    return dict(schema='m005_formal_numerical_batch_plan_v1',phase='formal_numerical_evaluation',
        input_stream_manifest=identity(source),full_target_documents=len(docs),domain_counts=expected_counts,
        fixed_order='repeat2web1news1reviews; preserve original frozen order within each domain',ordered_source_indices=order,
        maximum_documents_per_batch=max_documents,maximum_raw_audit_documents_per_batch=1,
        batch_boundary='split at size limit or before second preselected raw-audit document',
        audit_selection=stream['audit_selection'],audit_candidate_doc_ids=[d['doc_id'] for d in docs if d['raw_tensor_audit_selected']],
        batches=batches,numerical_measured_documents=0,input_selection_changed=False,tokenization_performed=False,
        publication='bounded batch completion is not full1024 completion; operational clusters do not certify iid')


def load_batch(plan_path,batch_id,expected_counts=None,storage_plan=None):
    path=Path(plan_path);plan=json.loads(path.read_text())
    if plan.get('schema')!='m005_formal_numerical_batch_plan_v1' or plan.get('phase')!='formal_numerical_evaluation':
        raise ValueError('wrong formal plan schema/phase')
    source=plan['input_stream_manifest']
    if identity(source['path'])['sha256']!=source['sha256']:raise ValueError('frozen input manifest hash mismatch')
    stream=json.loads(Path(source['path']).read_text());all_docs=stream['documents']
    rebuilt=build_plan(source['path'],plan['maximum_documents_per_batch'],expected_counts=expected_counts)
    for key in ['full_target_documents','domain_counts','ordered_source_indices','batches','audit_candidate_doc_ids']:
        if plan[key]!=rebuilt[key]:raise ValueError('immutable plan structure or ordering mismatch: '+key)
    matches=[batch for batch in plan['batches'] if batch['batch_id']==batch_id]
    if len(matches)!=1:raise ValueError('batch absent or duplicated')
    batch=matches[0];docs=[all_docs[index] for index in batch['source_indices']]
    if not 1<=len(docs)<=16:raise ValueError('formal stage batch size outside1..16')
    if [d['doc_id'] for d in docs]!=batch['doc_ids'] or len(docs)!=batch['selected_documents']:
        raise ValueError('batch document identities differ from frozen plan')
    if len({d['duplicate_cluster'] for d in docs})!=len(docs):raise ValueError('cluster reuse in batch')
    audit_ids=[d['doc_id'] for d in docs if d['raw_tensor_audit_selected']]
    if audit_ids!=batch['audit_doc_ids'] or len(audit_ids)>1:raise ValueError('audit plan differs')
    for doc in docs:
        if doc['split']!='eval' or doc['evidence_role']!='formal_eval':raise ValueError('formal document role mismatch')
        read_token_artifact(doc)
    policy=None
    if storage_plan is not None:
        from formal_storage_plan import load_storage_policy
        policy=load_storage_policy(path,storage_plan)
    return dict(documents=docs,audit_doc_ids=audit_ids,batch_id=batch_id,batch_ids=[batch_id],source_plan=identity(path),
                storage_policy=policy,storage_source=identity(storage_plan) if storage_plan is not None else None,
                source_manifest=source,tokenizer_files=stream['tokenizer_files'],full_target_documents=plan['full_target_documents'])


def load_batch_group(plan_path,batch_ids,expected_counts=None,storage_plan=None):
    """Reuse one model for consecutive immutable logical batches; never resample."""
    if isinstance(batch_ids,str):batch_ids=batch_ids.split(',')
    if not batch_ids or any(not isinstance(value,str) or not value or value!=value.strip() for value in batch_ids):
        raise ValueError('explicit logical batch IDs required')
    if len(set(batch_ids))!=len(batch_ids):raise ValueError('duplicate logical batch ID')
    plan=json.loads(Path(plan_path).read_text());order=[row['batch_id'] for row in plan['batches']]
    if any(value not in order for value in batch_ids):raise ValueError('logical batch absent')
    indices=[order.index(value) for value in batch_ids]
    if indices!=list(range(indices[0],indices[0]+len(indices))):
        raise ValueError('merged logical batches must be consecutive and in frozen order')
    selected=[load_batch(plan_path,value,expected_counts,storage_plan) for value in batch_ids]
    docs=[doc for batch in selected for doc in batch['documents']]
    audits=[value for batch in selected for value in batch['audit_doc_ids']]
    if len(docs)>80:raise ValueError('single worker may consume at most80 frozen documents')
    if len(audits)>1:raise ValueError('single worker may contain at most one preselected raw audit')
    if len({doc['doc_id'] for doc in docs})!=len(docs) or len({doc['duplicate_cluster'] for doc in docs})!=len(docs):
        raise ValueError('document or cluster repeated across logical batches')
    return {**selected[0], 'documents':docs,'audit_doc_ids':audits,'batch_ids':list(batch_ids),
            'batch_id':','.join(batch_ids),'logical_batch_documents':[
                dict(batch_id=row['batch_id'],doc_ids=[doc['doc_id'] for doc in row['documents']]) for row in selected]}


def worker(args):
    plan=build_plan(args.input_stream,args.maximum_documents_per_batch)
    write_json(args.output_dir/'formal_batch_plan.json',plan)
    write_json(args.output_dir/'plan_summary.json',dict(full_target_documents=plan['full_target_documents'],batches=len(plan['batches']),
        first_batch=plan['batches'][0],audit_candidate_documents=len(plan['audit_candidate_doc_ids']),
        input_stream=plan['input_stream_manifest'],numerical_measured_documents=0,tokenization_performed=False))
    print(json.dumps(dict(documents=plan['full_target_documents'],batches=len(plan['batches']),first_batch_documents=plan['batches'][0]['selected_documents'])))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-stream',type=Path,required=True)
    parser.add_argument('--maximum-documents-per-batch',type=int,default=16)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--wall-seconds',type=int,default=300)
    parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    try:code=worker(args) if args.worker else cpu_supervise(args,__file__,'formal_plan')
    except Exception:traceback.print_exc();code=1
    raise SystemExit(code)


if __name__=='__main__':main()
