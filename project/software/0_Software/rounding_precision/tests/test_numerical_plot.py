from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from plot_numerical_fidelity import plot_rows


class PlotScopeTests(unittest.TestCase):
    def test_no_matching_evidence_does_not_make_empty_success_plot(self):
        with self.assertRaises(ValueError):
            plot_rows({'document_metrics':[]},'current_vs_reference','v5_continuous','formal_eval')

    def test_legacy_and_formal_separate(self):
        smoke=dict(series='current_vs_reference',trajectory='bf16',evidence_role='engineering_smoke',domain='legacy',split='engineering')
        formal=dict(series='current_vs_reference',trajectory='v5_local',evidence_role='formal_eval',domain='web',split='eval')
        result=plot_rows({'document_metrics':[smoke,formal]},'current_vs_reference','v5_local','formal_eval')
        self.assertEqual(result,[formal])

    def test_mixed_roles_refused_even_if_labels_corrupt(self):
        base=dict(series='x',trajectory='v5',evidence_role='x',domain='web')
        with self.assertRaises(ValueError):
            plot_rows({'document_metrics':[{**base,'split':'dev'},{**base,'split':'eval'}]},'x','v5','x')


if __name__=='__main__':unittest.main()
