"""Immutable pre-result raw-audit storage addendum; no sample reselection."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import traceback
from run_numerical_fidelity import identity,write_json,cpu_supervise


def create_storage_policy(input_plan):
    plan_path=Path(input_plan);plan=json.loads(plan_path.read_text())
    source=plan['input_stream_manifest']
    if identity(source['path'])['sha256']!=source['sha256']:raise ValueError('input-stream hash changed')
    stream=json.loads(Path(source['path']).read_text());docs=stream['documents'];first={};audit=[]
    for index in plan['ordered_source_indices']:
        doc=docs[index]
        if doc['raw_tensor_audit_selected']:
            audit.append(doc)
            first.setdefault(doc['domain'],doc['doc_id'])
    if set(first)!={'web','news','reviews'}:raise ValueError('preselected audit candidates must cover all3 domains')
    if [doc['doc_id'] for doc in audit]!=[doc for batch in plan['batches'] for doc in batch['audit_doc_ids']]:
        raise ValueError('audit ordering or membership differs from frozen input plan')
    records=[]
    for doc in audit:
        records.append(dict(doc_id=doc['doc_id'],domain=doc['domain'],
            raw_hidden_layers=list(range(32)) if doc['doc_id']==first[doc['domain']] else [0,15,31],
            raw_final_norm=True,raw_dynamic_metadata_layers=list(range(32)),raw_dynamic_value_layers=[0,15,31],
            witness_layers=list(range(32)),witness_points_per_coordinate=16))
    return dict(schema='m005_formal_storage_addendum_v1',input_plan=identity(plan_path),
        selection_changed=False,numerical_outputs_used=False,full_hidden_audit_doc_ids=list(first.values()),
        records=records,non_audit_raw_hidden=False,non_audit_raw_dynamic=False,
        full_statistics_all_documents_layers=True,witness_max_doc_mib=64,witness_max_at_mib=96,total_attempt_mib=256,
        semantics='first preselected audit per domain according only to frozen input order; other12audit hidden0/15/31+norm')


def load_storage_policy(input_plan,storage_file):
    policy=json.loads(Path(storage_file).read_text())
    if policy!=create_storage_policy(input_plan):raise ValueError('storage addendum differs from immutable pre-result policy')
    return policy


def worker(args):
    policy=create_storage_policy(args.formal_batch_plan)
    write_json(args.output_dir/'formal_storage_plan.json',policy)
    print(json.dumps(dict(full_hidden_audit_doc_ids=policy['full_hidden_audit_doc_ids'],audit_documents=len(policy['records']),numerical_measured_documents=0)))
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--formal-batch-plan',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--wall-seconds',type=int,default=300)
    p.add_argument('--worker',action='store_true')
    args=p.parse_args()
    try:code=worker(args) if args.worker else cpu_supervise(args,__file__,'storage')
    except Exception:traceback.print_exc();code=1
    raise SystemExit(code)


if __name__=='__main__':main()
