from pathlib import Path
import json
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from metric_uncertainty import binomial_ranks,quantile_interval,planned_rank_table,rank_interval,order_statistic_interval


class QuantileIntervalTests(unittest.TestCase):
    def test_frozen_rank_table_matches_independent_contract(self):
        expected={(256,'0.95'):(236,251),(256,'0.99'):(250,257),
                  (512,'0.95'):(476,497),(512,'0.99'):(502,512),
                  (1024,'0.95'):(959,987),(1024,'0.99'):(1007,1020)}
        for (n,p),(lower,upper) in expected.items():
            result=binomial_ranks(n,p)
            self.assertEqual((result['lower_rank'],result['upper_rank']),(lower,upper))
            self.assertGreaterEqual(result['binomial_coverage'],.95)

    def test_p99_256_upper_unbounded_not_samplemax(self):
        result=quantile_interval(range(256),iid_documents=True)
        self.assertIsNone(result['interval']['upper'])
        self.assertTrue(result['interval']['upper_unbounded'])
        json.dumps(result,allow_nan=False)

    def test_null_not_zero_and_nearest_rank_no_interpolation(self):
        result=quantile_interval([None]+list(range(1024)),iid_documents=True,estimator="nearest_rank")
        self.assertEqual(result['defined_document_count'],1024)
        self.assertEqual(result['undefined_metric_documents'],1)
        self.assertEqual(result['nearest_rank'],1014)
        self.assertEqual(result['estimate'],1013)

    def test_fixed_quota_pool_not_promoted_to_iid(self):
        result=quantile_interval(range(1024),iid_documents=True,fixed_quota_pool=True)
        self.assertIsNone(result['interval'])
        self.assertFalse(result['iid_assumption_declared'])

    def test_family_correction_expands_interval_not_implicit_32layer_claim(self):
        one=binomial_ranks(512,'0.95');family=binomial_ranks(512,'0.95',family_size=32)
        self.assertLessEqual(family['lower_rank'],one['lower_rank'])
        self.assertGreaterEqual(family['upper_rank'],one['upper_rank'])
        result=quantile_interval(range(512),p='0.95',iid_documents=True)
        self.assertIn('not simultaneous',result['layer_coverage'])

    def test_small_n_known_support_only_if_predeclared(self):
        unspecified=quantile_interval([1.],p='0.5',iid_documents=True)
        supported=quantile_interval([1.],p='0.5',iid_documents=True,known_support=(0,None))
        self.assertTrue(unspecified['interval']['lower_unbounded'])
        self.assertEqual(supported['interval']['lower'],0)
        self.assertTrue(supported['interval']['upper_unbounded'])

    def test_predeclared32layer_ranks_and_public_alias(self):
        expected={(256,'0.95'):(231,254),(256,'0.99'):(247,257),
                  (512,'0.95'):(470,502),(512,'0.99'):(498,513),
                  (1024,'0.95'):(949,994),(1024,'0.99'):(1002,1023)}
        for (n,p),ranks in expected.items():
            result=rank_interval(n,p,family_size=32)
            self.assertEqual((result['lower_rank'],result['upper_rank']),ranks)

    def test_explicit_documents_zero_signal_and_duplicate_guard(self):
        records=[{'doc_id':'zero','value':None,'zero_signal':True},
                 {'doc_id':'a','value':1.},{'doc_id':'b','value':2.}]
        result=order_statistic_interval(records,p='.5',sampling_model='single_domain_iid_assumed')
        self.assertEqual(result['defined_document_count'],2)
        self.assertEqual(result['zero_signal_documents'],1)
        self.assertEqual(result['estimate'],1.5)
        with self.assertRaises(ValueError):order_statistic_interval(records+[records[1]])
        with self.assertRaises(ValueError):order_statistic_interval([{'doc_id':'x','value':0,'zero_signal':True}])

    def test_empty_ties_and_failures_do_not_become_extra_samples(self):
        empty=order_statistic_interval([],sampling_model='single_domain_iid_assumed')
        self.assertEqual(empty['interval_status'],'not_estimable')
        self.assertEqual(empty['n_defined'],0)
        ties=order_statistic_interval([{'doc_id':str(i),'value':2.} for i in range(512)],p='.95',sampling_model='single_domain_iid_assumed')
        self.assertEqual(ties['interval']['lower'],2.)
        self.assertEqual(ties['interval']['upper'],2.)
        failure=order_statistic_interval([{'doc_id':'ok','value':2.},{'doc_id':'lost','value':None,'status':'failed'}],sampling_model='single_domain_iid_assumed')
        self.assertIsNone(failure['interval'])
        self.assertEqual(failure['undefined_reason_counts'],{'failed':1})
        with self.assertRaises(ValueError):order_statistic_interval([{'doc_id':'mystery','value':None}])

    def test_finite_equal_tail_upper_threshold_and64family(self):
        self.assertTrue(rank_interval(367,'.99')['upper_unbounded'])
        self.assertFalse(rank_interval(368,'.99')['upper_unbounded'])
        one=rank_interval(512,'.95',family_size=32);two=rank_interval(512,'.95',family_size=64)
        self.assertLessEqual(two['lower_rank'],one['lower_rank'])
        self.assertGreaterEqual(two['upper_rank'],one['upper_rank'])
        self.assertGreaterEqual(two['family_coverage_lower_bound_under_iid'],.95)

    def test_declared_iid_not_verified_and_partial_failures_suppress_ci(self):
        result=order_statistic_interval([{'doc_id':'partial','value':1.,'status':'failed'}],sampling_model='single_domain_iid_assumed')
        self.assertTrue(result['iid_assumption_declared'])
        self.assertFalse(result['assumptions_verified'])
        self.assertIsNone(result['interval'])
        with self.assertRaises(ValueError):order_statistic_interval([{'doc_id':'x','value':0.,'empty_valid_domain':True}])
        with self.assertRaises(ValueError):quantile_interval([2.],known_support=(0,1))
        with self.assertRaises(ValueError):quantile_interval([2.],known_support=(2,1))

    def test_invalid_values_not_silently_filtered(self):
        for values in ([float('nan')],[float('inf')],[True]):
            with self.assertRaises(ValueError):quantile_interval(values)


if __name__=='__main__':unittest.main()
