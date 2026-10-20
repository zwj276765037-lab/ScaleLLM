"""R005 completion and observer integrity qualification, no CUDA initialization."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from extended_numerical_stream import validate_mlp_coverage,validate_logit_coverage,validate_readonly_baseline
import mlp_numerical_extension as mlp


def logit_row():
    return dict(schema='m005_r005_full_vocab_v1',doc_id='d',tokens=2,vocab_size=128256,hidden_size=4096,
        score_pairs=256512,nonfinite=0,missing_positions=0,vocab_chunks=[[0,4096],[4096,128256]],
        per_token=dict(current_top1_ids=[4,5],reference_top1_ids=[4,6],top1_matches=[True,False],
                       max_abs_logit_delta=[.1,.2],reference_top1_margin=[.3,.1],current_top1_tie_counts=[1,1],reference_top1_tie_counts=[1,1]),
        top1_match_count=1,top1_total_count=2,top1_agreement=.5,error_energy=4.,reference_signal_energy=400.,relative_l2_percent=10.)


class ExtendedCoverageTests(unittest.TestCase):
    def test_mlp_full_and_duplicate_rejected(self):
        rows=[dict(doc_id='d',node='mlp_extension',layer=i,op=op,arm=arm,
                   metrics=dict(nonfinite_elements=0,valid_elements=2,error_energy=0.,signal_energy=1.,signed_error_sum=0.,absolute_max=0.))
              for i,op,arm in mlp.expected_coordinates()]
        self.assertTrue(validate_mlp_coverage('d',rows,mlp)['complete'])
        broken=rows[:-1]+[rows[0]]
        with self.assertRaisesRegex(ValueError,'416'):validate_mlp_coverage('d',broken,mlp)
        rows[0]['doc_id']='other'
        with self.assertRaisesRegex(ValueError,'contamination'):validate_mlp_coverage('d',rows,mlp)

    def test_full_vocabulary_success_and_missing_suffix(self):
        row=logit_row();self.assertEqual(validate_logit_coverage('d',2,row)['score_pairs'],256512)
        row['vocab_chunks'][-1][-1]-=1
        with self.assertRaisesRegex(ValueError,'suffix'):validate_logit_coverage('d',2,row)

    def test_no_tminusone_or_inconsistent_prediction_count(self):
        row=logit_row();row['per_token']['top1_matches']=[True]
        with self.assertRaisesRegex(ValueError,'positions'):validate_logit_coverage('d',2,row)
        row=logit_row();row['top1_match_count']=2
        with self.assertRaisesRegex(ValueError,'Top1'):validate_logit_coverage('d',2,row)

    def test_head_ratio_uses_signal_energy_and_percent_once(self):
        row=logit_row();row['relative_l2_percent']=1000.
        with self.assertRaisesRegex(ValueError,'relativeL2'):validate_logit_coverage('d',2,row)

    def test_readonly_baseline_raw_and_dynamic_identity(self):
        with tempfile.TemporaryDirectory() as t:
            current=Path(t)/'new';old=Path(t)/'old'
            for base in [current,old]:
                (base/'documents/doc0000').mkdir(parents=True)
                row=dict(doc_id='d',layer=0,node='n',op='o',metrics={'a':1.})
                for name in ['tensor_metrics.jsonl','local_tensor_metrics.jsonl']:
                    (base/name).write_text(json.dumps(row)+'\n')
                dynamic=dict(doc_id='d',arm='current',layer=0,function='f',ordinal=0,identity={'sha256':'a'})
                (base/'dynamic_metadata.jsonl').write_text(json.dumps(dynamic)+'\n')
                np.savez(base/'documents/doc0000/hidden_layer00.npz',current=np.ones(3,dtype=np.float32),reference=np.ones(3,dtype=np.float32))
            self.assertTrue(validate_readonly_baseline(current,old)['passed'])
            path=current/'dynamic_metadata.jsonl';row=json.loads(path.read_text());row['identity']={'sha256':'b'};path.write_text(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError,'dynamic'):validate_readonly_baseline(current,old)
            path.write_text((old/'dynamic_metadata.jsonl').read_text())
            np.savez(current/'documents/doc0000/hidden_layer00.npz',current=np.zeros(3,dtype=np.float32),reference=np.ones(3,dtype=np.float32))
            with self.assertRaisesRegex(ValueError,'saved tensor'):validate_readonly_baseline(current,old)


if __name__=='__main__':unittest.main()
