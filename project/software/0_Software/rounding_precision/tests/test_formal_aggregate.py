import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'experiment'))
from aggregate_formal_numerical import (AggregateValidationError, CONSUMED_SOURCES, DYNAMIC_KEYS,
    LOCAL_KEYS, aggregate_formal, classify_metric, constraint_bound, descriptive_distribution, identity,
    position_bound, position_metric)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, allow_nan=True))


def write_rows(path, rows):
    Path(path).write_text(''.join(json.dumps(row, allow_nan=True) + '\n' for row in rows))


def metric(signal=100, error=1, ratio=10, *, count=8, total=None):
    return dict(signal_energy=signal, error_energy=error, relative_l2_percent=ratio,
                valid_elements=count, total_elements=count if total is None else total, nonfinite_elements=0)


def fixture(root):
    """Explicitly synthetic schema; no model inference or measured formal result."""
    docs = []
    for index in range(1024):
        domain = 'web' if index < 512 else 'news' if index < 768 else 'reviews'
        docs.append(dict(doc_id=f'synthetic:{index}', domain=domain, split='eval', evidence_role='formal_eval',
                         text_sha256=f'{index+1000:064x}', duplicate_cluster=f'cluster:{index}', tokens=2,
                         token_artifact=dict(path=str(root / f'unmeasured_{index}.npz'), bytes=0, sha256=f'{index:064x}')))
    order = []
    for index in range(256):
        order.extend((2*index, 2*index+1, 512+index, 768+index))
    for index in order[:4]:
        path = root / f'tokens_{index}.npz'
        np.savez(path, input_ids=np.array([index+1, 9], dtype=np.int64), attention_mask=np.ones(2, dtype=np.int64), position_ids=np.arange(2, dtype=np.int64))
        docs[index]['token_artifact'] = identity(path)
    stream_path, plan_path = root / 'stream.json', root / 'plan.json'
    write_json(stream_path, dict(schema='m005_numerical_document_stream_v1', documents=docs))
    batches = []
    for start in range(0, 1024, 4):
        indices = order[start:start+4]
        batches.append(dict(batch_id=f'B{start//4+1:03}', source_indices=indices,
                            doc_ids=[docs[i]['doc_id'] for i in indices], selected_documents=4,
                            actual_token_lengths=[2]*4, domain_counts=dict(web=2, news=1, reviews=1)))
    write_json(plan_path, dict(schema='m005_formal_numerical_batch_plan_v1', phase='formal_numerical_evaluation',
                              input_stream_manifest=identity(stream_path), full_target_documents=1024,
                              domain_counts=dict(web=512, news=256, reviews=256), batches=batches, ordered_source_indices=order))
    attempt = root / 'attempt'; attempt.mkdir()
    selected = [docs[i] for i in order[:4]]
    source = [dict(path=str(root / name), sha256=hashlib.sha256(name.encode()).hexdigest()) for name in sorted(CONSUMED_SOURCES)]
    selected_identity = [{key: row[key] for key in ('doc_id', 'domain', 'split', 'evidence_role', 'text_sha256', 'duplicate_cluster')} for row in selected]
    write_json(attempt / 'gpu_receipt.json', dict(execution_state='completed', exit_code=0, native_exit_code=0,
                                                 source_unchanged=True, stop_reason=None,worker_reaped=True))
    write_json(attempt / 'gpu_launch_manifest.json', dict(source_identity=source))
    write_json(attempt / 'paired_worker_manifest.json', dict(document_source=identity(plan_path), full_formal_target=1024,
               formal_batch_ids=['B001'], selected_documents=selected_identity, code=source))
    write_json(attempt / 'paired_result.json', dict(execution_state='completed', source_unchanged=True,
               shared_weight_buffers_unchanged=True, full_formal_target=1024, formal_batch_ids=['B001'],
               measured_documents=4, formal_eval_documents=4, layers=32,
               documents=[dict(doc_id=row['doc_id'], tokens=2) for row in selected]))
    write_json(attempt / 'stream_loader_validation.json', dict(all_keys_loaded=True, no_meta_parameters_or_buffers=True,
               source_model_keys_match_exactly=True, consumed_base_model_identity_sha256='a'*64))
    write_json(attempt / 'tokenizer_identity.json', dict(tokenization_performed=False, document_source=identity(stream_path)))
    hidden, local, dynamic = [], [], []
    for offset, (doc, fields) in enumerate(zip(selected, selected_identity)):
        for layer in range(32):
            hidden.append(dict(fields, layer=layer, node='decoder_hidden', op='decoder_block_output', trajectory='v5_continuous_paired',
                               output_shape=[1,2,4096], metrics=dict(current_vs_reference=metric(count=8192))))
        for layer, node, op in sorted(LOCAL_KEYS):
            if node=='linear':total=2*(1024 if op in ('k_proj','v_proj') else 14336 if op in ('gate_proj','up_proj') else 4096)
            elif node=='rope':total=2*(1024 if op=='key_rope' else 4096)
            elif node in ('qk','softmax'):total=128
            else:total=8192
            local.append(dict(fields, layer=layer, node=node, op=op, trajectory='v5_current_local_paired', metrics=dict(current_vs_reference=metric(count=96 if node=='softmax' else total,total=total))))
        for arm, layer, function, ordinal in sorted(DYNAMIC_KEYS):
            names = ('codes_u8','shifts_u8','zero_points_u8','values_u8') if function == 'prepare_fixed_activation' else ('codes_u8','shifts_u8','values_s12')
            groups=448 if ordinal==3 else 128
            shapes={name:([2,groups,32] if name=='values_u8' else [2,groups]) for name in names} if function=='prepare_fixed_activation' else {name:([1,2,8,4,32] if name=='values_s12' else [1,2,8,4]) for name in names}
            dynamic.append(dict(doc_id=doc['doc_id'], arm=arm, layer=layer, function=function, ordinal=ordinal,
                                identity={name:dict(shape=shapes[name],sha256='b'*64) for name in names}))
        directory = attempt / 'documents' / f'doc{offset:04d}'; directory.mkdir(parents=True)
        with np.load(doc['token_artifact']['path']) as arrays:
            inputs = dict(input_ids=arrays['input_ids'][None,:].tolist(), attention_mask=arrays['attention_mask'][None,:].tolist())
        write_json(directory / 'input_identity.json', dict(doc_id=doc['doc_id'], text_sha256=doc['text_sha256'], tokens=2,
                   retokenized=False, token_artifact=doc['token_artifact'], **inputs))
        write_json(directory / 'final_norm_comparison.json', dict(fields, layer=31, node='final_norm', op='host_final_norm',
                   trajectory='v5_continuous_paired', output_shape=[1,2,4096], metrics=dict(current_vs_reference=metric(count=8192))))
    write_rows(attempt / 'tensor_metrics.jsonl', hidden)
    write_rows(attempt / 'local_tensor_metrics.jsonl', local)
    write_rows(attempt / 'dynamic_metadata.jsonl', dynamic)
    return plan_path, stream_path, attempt


class ExtendedMetricTests(unittest.TestCase):
    def test_argmax_ties_use_fixed_coordinate_order_and_context(self):
        positions=[]
        for layer,node,op in ((1,'linear','q_proj'),(0,'rope','key_rope'),(0,'linear','v_proj')):
            m=metric();m.update(signed_error_sum=-4,absolute_max=2)
            positions.append(position_metric(dict(layer=layer,node=node,op=op,metrics=dict(current_vs_reference=m))))
        bound=position_bound(positions)
        self.assertEqual(bound['tie_count'],3)
        self.assertEqual(bound['max_coordinate'],dict(layer=0,node='linear',op='v_proj'))
        self.assertEqual(bound['argmax_position_context']['signed_bias'],-.5)
        self.assertEqual(bound['argmax_position_context']['absolute_max'],2)
        self.assertEqual(bound,position_bound(reversed(positions)))

    def test_zero_ratio_remains_null_but_all_zero_bound_is_zero(self):
        zero = classify_metric(metric(0, 0, None))
        self.assertEqual(zero['state'], 'exact_zero_match'); self.assertIsNone(zero['value'])
        bound = constraint_bound([zero]*224)
        self.assertEqual(bound['value'], 0); self.assertTrue(bound['all_zero_exact'])
        self.assertEqual(bound['exact_zero_match_count'], 224)
        self.assertEqual(classify_metric(metric(0, 0, 0))['state'], 'unestimable')

    def test_unbounded_and_invalid_precedence(self):
        infinity = classify_metric(metric(0, 1, None))
        finite = classify_metric(metric())
        self.assertEqual(infinity['state'], 'unbounded')
        bound = constraint_bound([finite, infinity])
        self.assertIsNone(bound['value']); self.assertTrue(bound['unbounded'])
        invalid = classify_metric(metric(float('nan'), 1, None))
        bound = constraint_bound([infinity, invalid])
        self.assertEqual(bound['state'], 'unestimable'); self.assertTrue(bound['observed_unbounded'])
        json.dumps(bound, allow_nan=False)

    def test_illegal_energy_ratio_and_domain_are_not_filtered(self):
        for bad in (float('nan'), float('inf'), -1, True, None):
            self.assertEqual(classify_metric(metric(bad,1,None))['state'],'unestimable')
        self.assertEqual(classify_metric(metric(100,1,11))['state'],'unestimable')
        value=metric();value['valid_elements']=0
        self.assertEqual(classify_metric(value)['state'],'unestimable')

    def test_extended_linear_quantile_keeps_infinity_and_integer_rank(self):
        finite = constraint_bound([classify_metric(metric())])
        infinity = constraint_bound([classify_metric(metric(0,1,None))])
        result=descriptive_distribution([finite,infinity],complete_target=False,fixed_quota_pool=False)
        self.assertEqual(result['document_count'],2);self.assertEqual(result['unbounded_documents'],1)
        self.assertTrue(result['quantiles']['p50']['unbounded'])
        single=descriptive_distribution([infinity],complete_target=True,fixed_quota_pool=True)
        self.assertTrue(single['quantiles']['p50']['unbounded'])
        self.assertIsNone(single['quantiles']['p99']['interval'])
        zero=constraint_bound([classify_metric(metric(0,0,None))])
        result=descriptive_distribution([zero,finite],complete_target=False,fixed_quota_pool=True)
        self.assertEqual(result['quantiles']['p50']['value'],5)
        self.assertEqual(result['all_zero_exact_documents'],1)

    def test_unestimable_collection_has_no_successful_subset_quantile(self):
        good=constraint_bound([classify_metric(metric())])
        bad=constraint_bound([classify_metric(None)])
        result=descriptive_distribution([good,bad],complete_target=True,fixed_quota_pool=False)
        self.assertEqual(result['state'],'unestimable');self.assertEqual(result['quantiles'],{})

    def test_conditional_rank_interval_only_for_full_domain_and_not_pool(self):
        finite=constraint_bound([classify_metric(metric())])
        infinity=constraint_bound([classify_metric(metric(0,1,None))])
        values=[finite]*255+[infinity]
        partial=descriptive_distribution(values,complete_target=False,fixed_quota_pool=False)
        self.assertIsNone(partial['quantiles']['p99']['interval'])
        full=descriptive_distribution(values,complete_target=True,fixed_quota_pool=False)
        interval=full['quantiles']['p99']['interval']
        self.assertEqual(interval['family_size'],1)
        self.assertTrue(interval['upper']['unbounded'])
        self.assertEqual(full['document_count'],256)
        pool=descriptive_distribution(values,complete_target=True,fixed_quota_pool=True)
        self.assertIsNone(pool['quantiles']['p95']['interval'])


class FormalAggregateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.plan,self.stream,self.attempt=fixture(self.root)
    def tearDown(self):self.temp.cleanup()
    def aggregate(self,**kwargs):
        return aggregate_formal(self.plan,self.stream,[self.attempt],allow_partial=True,**kwargs)

    def test_partial_counts_sources_maxima_and_no_ci(self):
        report=self.aggregate()
        self.assertEqual(report['completed_documents'],4);self.assertEqual(report['missing_documents'],1020)
        self.assertFalse(report['full_target_achieved']);self.assertEqual(report['target_state'],'partial')
        self.assertEqual(report['domain_counts_completed'],dict(web=2,news=1,reviews=1))
        for doc in report['documents']:
            self.assertEqual(len(doc['local_family_bounds']),5);self.assertEqual(len(doc['propagation']),32)
            self.assertEqual(doc['local_five_family_bound']['required_positions'],384)
            self.assertEqual(doc['local_five_family_bound']['value'],10)
        self.assertEqual(report['documents'][0]['local_family_bounds']['linear']['required_positions'],224)
        self.assertEqual(report['distributions']['web']['local_linear']['interval_status'],'not_reported_for_partial_target')
        self.assertTrue(report['evidence_files']);json.dumps(report,allow_nan=False)
        with self.assertRaises(AggregateValidationError):aggregate_formal(self.plan,self.stream,[self.attempt])

    def test_failed_changed_receipts_and_worker_source_mismatch_rejected(self):
        path=self.attempt/'gpu_receipt.json';original=json.loads(path.read_text())
        for changes in ({'exit_code':1},{'execution_state':'running'},{'source_unchanged':False},{'stop_reason':'budget'},{'worker_reaped':False}):
            write_json(path,{**original,**changes})
            with self.assertRaises(AggregateValidationError):self.aggregate()
        write_json(path,original)
        launch=self.attempt/'gpu_launch_manifest.json';value=json.loads(launch.read_text());value['source_identity'][0]['sha256']='c'*64;write_json(launch,value)
        with self.assertRaisesRegex(AggregateValidationError,'source identity'):self.aggregate()

    def test_required_hidden_local_and_dynamic_coverage_rejected(self):
        for name in ('tensor_metrics.jsonl','local_tensor_metrics.jsonl','dynamic_metadata.jsonl'):
            path=self.attempt/name;original=path.read_text();lines=original.splitlines(True);path.write_text(''.join(lines[:-1]))
            with self.assertRaisesRegex(AggregateValidationError,'coordinates'):self.aggregate()
            path.write_text(original)

    def test_wrong_document_identity_and_actual_token_ids_rejected(self):
        path=self.attempt/'tensor_metrics.jsonl';rows=[json.loads(x) for x in path.read_text().splitlines()];rows[0]['text_sha256']='d'*64;write_rows(path,rows)
        with self.assertRaisesRegex(AggregateValidationError,'identity'):self.aggregate()
        rows[0]['text_sha256']=f'{1000:064x}';write_rows(path,rows)
        path=self.attempt/'documents/doc0000/input_identity.json';row=json.loads(path.read_text());row['input_ids'][0][0]+=1;write_json(path,row)
        with self.assertRaisesRegex(AggregateValidationError,'actual model input'):self.aggregate()

    def test_duplicate_attempt_batch_and_incompatible_core_rejected(self):
        with self.assertRaises(AggregateValidationError):aggregate_formal(self.plan,self.stream,[self.attempt,self.attempt],allow_partial=True)
        second=self.root/'second';shutil.copytree(self.attempt,second)
        with self.assertRaisesRegex(AggregateValidationError,'batch repeated'):aggregate_formal(self.plan,self.stream,[self.attempt,second],allow_partial=True)
        for name,key in (('paired_worker_manifest.json','code'),('gpu_launch_manifest.json','source_identity')):
            path=second/name;row=json.loads(path.read_text());row[key][0]['sha256']='e'*64;write_json(path,row)
        with self.assertRaisesRegex(AggregateValidationError,'incompatible consumed-source'):aggregate_formal(self.plan,self.stream,[self.attempt,second],allow_partial=True)

    def test_invalid_numerical_cell_retains_document_and_poisoned_max(self):
        path=self.attempt/'local_tensor_metrics.jsonl';rows=[json.loads(x) for x in path.read_text().splitlines()]
        old=rows[0]['metrics']['current_vs_reference'];rows[0]['metrics']['current_vs_reference']=metric(float('inf'),1,None,count=old['valid_elements'],total=old['total_elements']);write_rows(path,rows)
        report=self.aggregate();doc=report['documents'][0]
        self.assertEqual(report['completed_documents'],4)
        self.assertEqual(doc['local_five_family_bound']['state'],'unestimable')
        self.assertEqual(report['distributions']['fixed_quota_pool']['local_five_family_bound']['quantiles'],{})
        json.dumps(report,allow_nan=False)

    def test_plan_stream_tamper_and_retokenization_rejected(self):
        path=self.attempt/'documents/doc0000/input_identity.json';original=json.loads(path.read_text());write_json(path,{**original,'retokenized':True})
        with self.assertRaisesRegex(AggregateValidationError,'retokenized'):self.aggregate()
        write_json(path,original)
        with self.stream.open('a') as handle:handle.write(' ')
        with self.assertRaisesRegex(AggregateValidationError,'SHA'):self.aggregate()

    def test_wrong_metric_denominator_and_dynamic_geometry_rejected(self):
        path=self.attempt/'tensor_metrics.jsonl';original=path.read_text();rows=[json.loads(x) for x in original.splitlines()]
        rows[0]['metrics']['current_vs_reference']['valid_elements']-=1;write_rows(path,rows)
        with self.assertRaisesRegex(AggregateValidationError,'element count'):self.aggregate()
        path.write_text(original)
        path=self.attempt/'dynamic_metadata.jsonl';rows=[json.loads(x) for x in path.read_text().splitlines()]
        rows[0]['identity']['codes_u8']['shape']=[1];write_rows(path,rows)
        with self.assertRaisesRegex(AggregateValidationError,'dynamic input geometry'):self.aggregate()


if __name__=='__main__':unittest.main()
