from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from run_numerical_fidelity import energy_metrics,node_metrics,summarize_documents,mask_counts,replay_worker,identity
from numerical_model_stream import select_documents,tensor_row,audit_configuration,validate_document_coverage
from run_paired_numerical_model import validate_attach,read_document,audit_report
import tempfile
import hashlib
import json
from types import SimpleNamespace


class FormalExecutionTests(unittest.TestCase):
    def test_frozen_storage_overrides_cannot_change_collection(self):
        policy=dict(records=[dict(raw_dynamic_value_layers=[0,15,31])],witness_max_doc_mib=64,witness_max_at_mib=96)
        args=SimpleNamespace(raw_value_audit_layers='0,15,31',witness_max_doc_mib=64,witness_max_at_mib=96)
        self.assertEqual(audit_configuration(args,dict(storage_policy=policy)),[0,15,31])
        for key,value in [('raw_value_audit_layers','0,15'),('raw_value_audit_layers','0,15,15,31'),
                          ('witness_max_doc_mib',32),('witness_max_at_mib',64)]:
            altered=SimpleNamespace(**{**vars(args),key:value})
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                audit_configuration(altered,dict(storage_policy=policy))

    def test_shared_coordinate_omissions_and_duplicates_fail_completion(self):
        doc='fixed';hidden=[dict(doc_id=doc,layer=layer) for layer in range(32)]
        sites=[('linear',op) for op in ['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']]
        sites += [('rope','query_rope'),('rope','key_rope'),('qk','qk'),('softmax','softmax'),('pv','pv')]
        local=[dict(doc_id=doc,layer=layer,node=node,op=op) for layer in range(32) for node,op in sites]
        dynamic=[dict(doc_id=doc,arm=arm,layer=layer,function=function,ordinal=ordinal)
                 for arm in ['current','reference'] for layer in range(32)
                 for function,count in [('prepare_fixed_activation',4),('_kv12_quantize',2)] for ordinal in range(count)]
        self.assertTrue(validate_document_coverage(doc,hidden,local,dynamic)['complete'])
        for field,rows in [('hidden',hidden[:-1]),('local',local[:-1]),('local',local[:-1]+[local[0]]),
                           ('dynamic',[row for row in dynamic if row['layer']!=31])]:
            selected=dict(hidden=hidden,local=local,dynamic=dynamic);selected[field]=rows
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_document_coverage(doc,selected['hidden'],selected['local'],selected['dynamic'])


class MetricsTests(unittest.TestCase):
    def test_known_relative_error_and_scale_invariance(self):
        a=energy_metrics(np.array([2.,4.]),np.array([1.,2.]))
        b=energy_metrics(np.array([2.,4.])*1e-5,np.array([1.,2.])*1e-5)
        self.assertAlmostEqual(a['relative_l2_percent'],100.)
        self.assertAlmostEqual(a['relative_l2_percent'],b['relative_l2_percent'])
        self.assertAlmostEqual(a['normalized_signed_bias_percent'],100*3/np.sqrt(10))

    def test_zero_and_empty_signal_not_epsilon_ratio(self):
        a=energy_metrics(np.array([1.]),np.array([0.]))
        self.assertIsNone(a['relative_l2_percent'])
        self.assertTrue(a['zero_signal'])
        b=energy_metrics(np.array([1.]),np.array([2.]),np.array([False]))
        self.assertTrue(b['empty_valid_domain'])
        self.assertFalse(b['zero_signal'])

    def test_exact_small_fraction_not_cancelled_by_large_quotient(self):
        q=1<<31
        result={'current_code':np.array([q]),'reference_code':np.array([q]),'valid_mask':np.array([True]),
                'exact':dict(quotient_floor=np.array([q]),remainder=np.array([1]),denominator=np.array([1<<40]),fractional_bits=16)}
        metrics=node_metrics(result)
        self.assertEqual(metrics['current_vs_reference']['absolute_max'],0)
        self.assertEqual(metrics['current_vs_exact']['absolute_max'],2.**-56)

    def test_document_parts_merge_but_ops_and_trajectories_do_not(self):
        metric=energy_metrics(np.array([2.]),np.array([1.]))
        base=dict(doc_id='doc1',layer=0,node='linear',op='q_proj',trajectory='v5_local',domain='web',split='eval',evidence_role='formal_eval',metrics={'current_vs_reference':metric})
        rows=[base,{**base},{**base,'op':'k_proj'},{**base,'trajectory':'bf16'}]
        out=summarize_documents(rows,bootstrap_replicates=0)
        self.assertEqual(out['document_count'],1)
        self.assertEqual(out['formal_eval_document_count'],1)
        self.assertEqual(len(out['document_metrics']),3)
        self.assertEqual(out['document_metrics'][0]['valid_elements'],2)
        self.assertEqual(out['document_metrics'][0]['relative_l2_percent'],100)
        self.assertIsNone(out['cells'][0]['relative_l2_percent']['bootstrap95'])

    def test_bootstrap_resamples_docs_and_keeps_scope(self):
        rows=[]
        for i in range(20):
            rows.append(dict(doc_id=str(i),layer=0,node='host',op=None,trajectory='v5_local',domain='web',split='dev',evidence_role='development',metrics={'current_vs_exact':energy_metrics(np.array([2.]),np.array([1.]))}))
        out=summarize_documents(rows,bootstrap_replicates=10)
        self.assertEqual(out['formal_eval_document_count'],0)
        self.assertEqual(out['cells'][0]['relative_l2_percent']['bootstrap95']['p99'],[100.,100.])

    def test_actual_api_replay_serializes_diagnostic_vectors(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);artifact=root/'input.npz';output=root/'output';output.mkdir()
            np.savez(artifact,dot=np.array([[1,2],[3,4]],np.int64),act_code=np.array(1),weight_code=np.array(1),
                     act_shift=np.array(14),weight_shift=np.array(14))
            case=dict(doc_id='engineering',layer=0,node='linear',op='q_proj',domain='smoke',split='engineering',
                      trajectory='bf16',evidence_role='engineering_smoke',input_npz=str(artifact),
                      sha256=identity(artifact)['sha256'],config={'profile':'attention'})
            manifest=root/'manifest.json';manifest.write_text(json.dumps({'cases':[case]}))
            self.assertEqual(replay_worker(SimpleNamespace(input_manifest=manifest,output_dir=output)),0)
            summary=json.loads((output/'document_summary.json').read_text())
            self.assertEqual(summary['formal_eval_document_count'],0)
            self.assertEqual(summary['tensor_count'],1)
            self.assertTrue((output/'strict_valid_document_summary.json').is_file())
            raw=np.load(output/'arrays/tensor_000000.npz')
            self.assertIn('current_error_counts_guard_overflow',raw.files)

    def test_primary_accepted_and_strict_domains_are_distinct(self):
        result=dict(current_code=np.array([2,8,0]),reference_code=np.array([1,4,0]),
                    metric_mask=np.array([True,True,True]),accepted_mask=np.array([True,True,False]),
                    valid_mask=np.array([True,False,False]),
                    exact=dict(quotient_floor=np.array([1,4,0]),remainder=np.zeros(3,dtype=int),denominator=np.ones(3,dtype=int),fractional_bits=16))
        primary=node_metrics(result);strict=node_metrics(result,strict=True)
        self.assertEqual(primary['current_vs_reference']['valid_elements'],2)
        self.assertEqual(strict['current_vs_reference']['valid_elements'],1)
        counts=mask_counts(result)
        self.assertEqual(counts['rejected_metric_elements'],1)
        self.assertEqual(counts['accepted_metric_elements'],2)

    def test_bound_coverage_is_not_inferred_from_zero_violations(self):
        counts=mask_counts({'current_code':np.ones((2,3),np.int64),'valid_mask':np.ones((2,3),bool),
                            'bound_applicable_mask':np.zeros((2,3),bool),'bound_violation_mask':np.zeros((2,3),bool)})
        self.assertEqual(counts['bound_not_applicable_elements'],6)
        self.assertEqual(counts['bound_violation_mask'],0)


class PairedPreparationTests(unittest.TestCase):
    def test_four_document_selection_rejects_cluster_reuse(self):
        from types import SimpleNamespace
        args=SimpleNamespace(document_count=4,documents=None,document_index=0)
        docs=select_documents(args,lambda path,i:dict(doc_id=str(i),duplicate_cluster='c'+str(i)))
        self.assertEqual(len(docs),4)
        with self.assertRaises(ValueError):select_documents(args,lambda path,i:dict(doc_id=str(i),duplicate_cluster='same'))

    def test_final_norm_row_keeps_real_shape_and_document_identity(self):
        row=tensor_row(dict(doc_id='doc',domain='wiki',split='dev',evidence_role='development'),31,'final_norm',
                       'host_final_norm','v5_continuous_paired',np.ones((1,3,4096)),np.ones((1,3,4096))*2)
        self.assertEqual(row['doc_id'],'doc')
        self.assertEqual(row['output_shape'],[1,3,4096])
        self.assertEqual(row['metrics']['current_vs_reference']['relative_l2_percent'],50.)
        self.assertIsNone(row['output_artifact'])

    def test_format05_fields_checked_individually(self):
        metadata=dict(layers=32,strict_total_shift=True,software_reference_not_hardware=False,
                      attention_format_id='0x48384103',mlp_full_format_id='0x48384605',
                      mlp_group_guard_compute_width=45,mlp_down_accumulator_compute_width=54,mlp_down_output_width=32)
        validate_attach(metadata)
        for key,value in [('mlp_full_format_id','0x48384603'),('mlp_down_output_width',24),('strict_total_shift',False)]:
            with self.assertRaises(ValueError):validate_attach({**metadata,key:value})

    def test_wider_reference_unpopulated_audits_are_null_not_zero_claims(self):
        class FakeAudit:
            def collect(self):return {'linear_accumulator_overflow':0,'linear_output_saturation':2}
            def collect_linear(self):return {'a':{'linear_accumulator_overflow':0,'linear_total_shift_min':12}}
        result=audit_report(FakeAudit(),reference=True)
        self.assertIsNone(result['counters']['linear_accumulator_overflow'])
        self.assertIsNone(result['linear']['a']['linear_accumulator_overflow'])
        self.assertEqual(result['counters']['linear_output_saturation'],2)
        self.assertEqual(result['linear']['a']['linear_total_shift_min'],12)

    def test_cost_pilot_rejects_eval_or_mutated_text(self):
        text='development document'
        row=dict(text=text,text_sha256=hashlib.sha256(text.encode()).hexdigest(),split='dev',evidence_role='development')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'docs.jsonl';path.write_text(json.dumps(row)+'\n')
            self.assertEqual(read_document(path,0)['text'],text)
            path.write_text(json.dumps({**row,'split':'eval','evidence_role':'formal_eval'})+'\n')
            with self.assertRaises(ValueError):read_document(path,0)
            path.write_text(json.dumps({**row,'text':'changed'})+'\n')
            with self.assertRaises(ValueError):read_document(path,0)


if __name__=='__main__':unittest.main()
