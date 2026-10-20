"""Bounded CPU checks; no final figure or fabricated final dataset is rendered."""
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from aggregate_final import relative, maximum, quantile, value, coverage_and_top1, KEYS, session_binding, identity, describe
from render_final import draw


class FinalAnalysisTests(unittest.TestCase):
    def test_extended_zero_infinity_invalid_and_no_subset_quantile(self):
        def metric(e, s, r):
            return dict(error_energy=e, signal_energy=s, relative_l2_percent=r, valid_elements=3, nonfinite_elements=0)
        zero = relative(metric(0, 0, None))
        self.assertEqual(zero['state'], 'exact_zero_match')
        self.assertIsNone(zero['original_relative_l2_percent'])
        self.assertEqual(relative(metric(1, 0, None))['state'], 'unbounded')
        self.assertEqual(relative(metric(None, 1, None))['state'], 'unestimable')
        sites = [dict(coordinate=(i, 'x'), bound=zero) for i in range(2)]
        result = maximum(sites, 2)
        self.assertEqual(result['value'], 0)
        self.assertTrue(result['all_zero_exact'])
        finite, infinity, invalid = value('finite', Decimal(1)), value('unbounded'), value('unestimable')
        self.assertEqual(quantile([finite, infinity], '0')['value'], 1)
        self.assertEqual(quantile([finite, infinity], '.5')['state'], 'unbounded')
        self.assertEqual(quantile([finite, invalid], '0')['state'], 'unestimable')
        with self.assertRaises(ValueError):
            maximum(sites[:1], 2)

    def test_max_tie_numeric_layer_order(self):
        sites = [dict(coordinate=(i, 'linear', 'gate_proj'), bound=value('finite', Decimal(2))) for i in (10, 2)]
        result = maximum(sites, 2)
        self.assertEqual(result['max_coordinate'][0], 2)
        self.assertEqual(result['tie_count'], 2)

    def test_exact_coverage_denominators_and_top1_macro_micro_all(self):
        docs = [dict(logits=dict(score_thresholds=[.1, .5], score_pairs=3, score_within_threshold_counts=[2, 3],
                                max_abs_logit_delta=.3, top1_match_count=1, top1_total_count=1, all_positions_top1_match=True)),
                dict(logits=dict(score_thresholds=[.1, .5], score_pairs=9, score_within_threshold_counts=[9, 9],
                                max_abs_logit_delta=.05, top1_match_count=1, top1_total_count=3, all_positions_top1_match=False))]
        coverage, top1 = coverage_and_top1(docs)
        self.assertEqual((coverage[0]['score_within_count'], coverage[0]['score_total_count']), (11, 12))
        self.assertEqual((coverage[0]['document_within_count'], coverage[0]['document_total_count']), (1, 2))
        self.assertAlmostEqual(top1['document_equal_weight_mean'], 2/3)
        self.assertEqual(top1['token_weighted_agreement'], .5)
        self.assertEqual(top1['all_positions_match_document_fraction'], .5)
        self.assertEqual(top1['token_weighted_match_count'], 2)
        self.assertEqual(len(KEYS), 13)

    def test_final_renderer_rejects_development_without_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'partial.json'
            source.write_text(json.dumps(dict(schema='m005_r005_final_precision_aggregate_v1', execution_state='completed',
                                              target_complete=False, measured_documents=16, planned_documents=1024, missing_documents=1008)))
            target = Path(directory) / 'no_figure'
            with self.assertRaisesRegex(ValueError, 'development or partial'):
                draw(source, target)
            self.assertFalse(target.exists())

    def test_group_completion_cannot_hide_failed_global_session(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            shared = dict(pid=123, ppid=1, pgid=123, starttime=99, argv=['test fixture'])
            receipt = base / 'session_gpu_receipt.json'
            receipt.write_text(json.dumps(dict(execution_state='cost_stop', native_exit_code=-15, exit_code=124,
                worker_reaped=True, source_unchanged=True, shared_worker_identity=shared, stop_reason='fixture budget')))
            launch = base / 'session_launch_manifest.json'
            launch.write_text(json.dumps(dict(shared_worker_identity=shared, source_identity=[])))
            ids = [f'unit_fixture:{i}' for i in range(1024)]
            session = base / 'analysis_manifest.json'
            session.write_text(json.dumps(dict(schema='m005_r005_analysis_manifest_v1', model_execution_complete=True,
                expected_documents=1024, completed_documents=1024, missing_doc_ids=[], actual_doc_ids=ids,
                expected_doc_ids=ids, session_gpu_receipt=identity(receipt), session_launch_manifest=identity(launch),
                shared_worker_identity=shared)))
            with self.assertRaisesRegex(ValueError, 'global worker must complete'):
                session_binding(identity(session), ids, 'unused_fixture_sha')

    def test_domain_conditional_p99_infinite_tail_is_not_capped(self):
        points = [value('finite', Decimal(i + 1)) for i in range(256)]
        domain = describe(points, domain_conditional=True)
        tail = domain['conditional_intervals']['p99']
        self.assertEqual(tail['upper']['state'], 'unbounded')
        self.assertTrue(tail['upper_rank_outside_sample'])
        self.assertFalse(domain['iid_verified'])
        self.assertEqual(describe(points)['conditional_intervals'], {})


if __name__ == '__main__':
    unittest.main()
