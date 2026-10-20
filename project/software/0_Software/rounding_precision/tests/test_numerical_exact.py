import math
from fractions import Fraction
from pathlib import Path
import random
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiment'))
from numerical_reference.policy import evaluate_node,CURRENT,OUTPUT_ONLY,ArithmeticPolicy
from numerical_reference.exact_reductions import binary_sum


def rounded(value):
    magnitude=abs(value)
    q=magnitude.numerator//magnitude.denominator
    if magnitude-q>=Fraction(1,2): q+=1
    return -q if value<0 else q


def exact_at(result,index):
    e=result['exact']
    return Fraction(int(e['quotient_floor'][index]))+Fraction(int(e['remainder'][index]),int(e['denominator'][index]))


def exp_lut():
    return np.array([math.floor(math.exp(-i/16)*65536+.5) for i in range(257)],dtype=np.int64)


def silu_lut():
    result=[]
    for i in range(8193):
        x=-16+i/256
        value=x/(1+math.exp(-x))*65536
        result.append(math.floor(value+.5) if value>=0 else -math.floor(-value+.5))
    return np.array(result,dtype=np.int64)


class NumericalExactTests(unittest.TestCase):
    def test_binary_reduction_independent_fraction_and_signed_ties(self):
        rng=random.Random(20261019)
        for _ in range(80):
            n=np.array([[rng.randrange(-(1<<36),1<<36) for _ in range(32)]],dtype=np.int64)
            k=np.array([[rng.randrange(-4,32) for _ in range(32)]],dtype=np.int64)
            q,r,d=binary_sum(n,k)
            expected=sum((Fraction(int(x),1<<int(y)) if y>=0 else Fraction(int(x)*(1<<int(-y))) for x,y in zip(n[0],k[0])),Fraction())
            self.assertEqual(Fraction(int(q[0]))+Fraction(int(r[0]),int(d[0])),expected)
            self.assertTrue(0<=r[0]<d[0])

    def test_linear_profiles_spots_and_inactive_maximum_shift(self):
        rng=random.Random(15)
        for profile,min_shift in (('attention',26),('mlp_gate_up',20),('mlp_down',12)):
            dots=np.array([[rng.randrange(-200,201) for _ in range(16)] for _ in range(20)],dtype=np.int64)
            total=np.array([[rng.randrange(min_shift,45) for _ in range(16)] for _ in range(20)],dtype=np.int64)
            a=dict(dot=dots,act_code=np.array(7,dtype=np.uint8),weight_code=np.array(13,dtype=np.uint8),
                   act_shift=total//2,weight_shift=total-total//2)
            r=evaluate_node('linear',a,dict(profile=profile))
            for row in range(20):
                e=sum((Fraction(int(dots[row,g])*91,1<<int(total[row,g]))*(1<<16) for g in range(16)),Fraction())
                self.assertEqual(exact_at(r,(row,)),e)
                self.assertEqual(r['reference_code'][row],rounded(e))
            self.assertFalse(np.any(r['bound_violation_mask']))
            self.assertFalse(np.any(r['reference_bound_violation_mask']))
        a=dict(dot=np.array([[100]]),act_code=np.array(0),weight_code=np.array(255),act_shift=np.array(63),weight_shift=np.array(63))
        r=evaluate_node('linear',a,dict(profile='mlp_down'))
        self.assertTrue(r['valid_mask'][0]);self.assertEqual(exact_at(r,(0,)),0)
        self.assertEqual(r['exact']['denominator'][0],1)

    def test_rope_signed_pair_exact_and_policy(self):
        a=dict(raw_pair=np.array([[1,1],[-1,-1],[127,-129]]),cos_q16=np.array([32768,32768,65536]),sin_q16=np.array([32768,32768,-1]))
        r=evaluate_node('rope',a,{})
        for i,(x,y) in enumerate(a['raw_pair']):
            c,s=int(a['cos_q16'][i]),int(a['sin_q16'][i])
            for j,e in enumerate((Fraction(int(x)*c-int(y)*s,65536),Fraction(int(x)*s+int(y)*c,65536))):
                self.assertEqual(exact_at(r,(i,j)),e)
                self.assertEqual(r['reference_code'][i,j],rounded(e))
        self.assertEqual(r['current_code'][0,1],2)
        self.assertEqual(r['reference_code'][0,1],1)
        selected=evaluate_node('rope',a,{'policy':CURRENT})
        np.testing.assert_array_equal(selected['selected_code'],selected['current_code'])

    def test_qk_s61_remainders_clip_and_lane_evidence(self):
        rng=random.Random(23)
        dots=np.array([[rng.randrange(-(1<<34),1<<34) for _ in range(4)] for _ in range(12)],dtype=np.int64)
        codes=np.array([[rng.randrange(1,256) for _ in range(4)] for _ in range(12)],dtype=np.int64)
        shifts=np.array([[rng.randrange(8,33) for _ in range(4)] for _ in range(12)],dtype=np.int64)
        a=dict(dot=dots,kv_code=codes,kv_shift=shifts)
        r=evaluate_node('qk',a,{})
        for i in range(12):
            e=sum((Fraction(int(dots[i,j])*int(codes[i,j])*5793,1<<(int(shifts[i,j])+18)) for j in range(4)),Fraction())
            e=min(Fraction(16<<14),max(Fraction(-(16<<14)),e))
            self.assertEqual(exact_at(r,(i,)),e)
            self.assertEqual(r['reference_code'][i],e.numerator//e.denominator)
        self.assertFalse(np.any(r['bound_violation_mask']))
        self.assertTrue(np.all(r['valid_mask']))
        q=np.ones((1,4,32),dtype=np.int64);k=q.copy()
        bad=dict(dot=np.full((1,4),31),kv_code=np.array(1),kv_shift=np.array(16),query_s24=q,key_s12=k)
        self.assertFalse(evaluate_node('qk',bad,{})['domain_valid_mask'][0])

    def test_pv_fraction_random_and_signed_floor(self):
        rng=np.random.default_rng(44)
        a=dict(probability_u16=rng.integers(0,65536,size=(20,32),dtype=np.int64),value_s12=rng.integers(-80,81,size=(20,32),dtype=np.int64),
               kv_code=rng.integers(1,256,size=(20,32),dtype=np.int64),kv_shift=rng.integers(12,33,size=(20,32),dtype=np.int64))
        r=evaluate_node('pv',a,{})
        for i in range(20):
            e=sum((Fraction(int(a['probability_u16'][i,j])*int(a['value_s12'][i,j])*int(a['kv_code'][i,j]),1<<int(a['kv_shift'][i,j])) for j in range(32)),Fraction())
            self.assertEqual(exact_at(r,(i,)),e)
            self.assertEqual(r['reference_code'][i],rounded(e))
        self.assertFalse(np.any(r['bound_violation_mask']))

    def test_softmax_exact_same_lut_all_policy_combinations_padding_endpoint(self):
        a=dict(score_q14=np.array([[0,-513,-1025],[0,0,0],[0,0,0]],dtype=np.int64),
               valid_mask=np.array([[True,True,True],[False,False,False],[True,False,False]]),lut_u17=exp_lut())
        r=evaluate_node('softmax',a,{})
        for row in (0,2):
            high=int(np.max(a['score_q14'][row,a['valid_mask'][row]]))
            terms=[]
            for score,valid in zip(a['score_q14'][row],a['valid_mask'][row]):
                m=min(16<<14,max(0,high-int(score)));index,frac=divmod(m,1024)
                e=Fraction(int(a['lut_u17'][index]))-Fraction((int(a['lut_u17'][index])-int(a['lut_u17'][min(index+1,256)]))*frac,1024)
                terms.append(e if valid else Fraction())
            for col,e in enumerate(terms):
                expected=e*65536/sum(terms)
                self.assertEqual(exact_at(r,(row,col)),expected)
                self.assertEqual(r['reference_code'][row,col],min(65535,rounded(expected)))
        self.assertTrue(np.all(r['software_padding_mask'][1]));self.assertFalse(np.any(r['metric_mask'][1]))
        self.assertEqual(r['reference_code'][2,0],65535)
        self.assertEqual(exact_at(r,(2,0)),65536)
        self.assertTrue(r['clip_mask'][2,0]);self.assertTrue(r['valid_mask'][2,0])
        for i in (False,True):
            for inv in (False,True):
                policy=ArithmeticPolicy(softmax_interpolation_round=i,softmax_reciprocal_round=inv)
                x=evaluate_node('softmax',a,{'policy':policy})
                if i and inv: np.testing.assert_array_equal(x['selected_code'],x['current_code'])
                if not i and not inv: np.testing.assert_array_equal(x['selected_code'],x['reference_code'])
        self.assertFalse(np.any(r['bound_violation_mask']))

    def test_common_swiglu_and_host_diagnostics_do_not_hide_error(self):
        table=silu_lut()
        a=dict(gate_s24=np.array([65536,-1,0xffffff,16<<16]),up_s24=np.array([1,100,100,-65535]),lut_s24=table)
        r=evaluate_node('swiglu',a,{})
        np.testing.assert_array_equal(r['current_code'],r['reference_code'])
        self.assertTrue(np.all(r['valid_mask']))
        self.assertTrue(any(exact_at(r,(i,))!=r['current_code'][i] for i in range(4)))
        h=evaluate_node('host',dict(raw_s32=np.array([(1<<24)+1,(1<<31)-1,-(1<<31),17])),{})
        np.testing.assert_array_equal(h['current_code'],h['reference_code'])
        self.assertEqual(h['current_code'][0],1<<24)
        self.assertEqual(h['current_code'][1],1<<31)
        self.assertEqual(exact_at(h,(1,)),(1<<31)-1)
        self.assertFalse(np.any(h['bound_violation_mask']))
        h24=evaluate_node('host',dict(raw_s32=np.array([17,(1<<23)-1])),{'input_width':24})
        self.assertTrue(np.all(h24['valid_mask']));self.assertTrue(np.all(h24['bound_numerator']==0))
        invalid=evaluate_node('host',dict(raw_s32=np.array([1<<23])),{'input_width':24})
        self.assertFalse(invalid['valid_mask'][0]);self.assertTrue(invalid['metric_mask'][0])

    def test_validation_optional_linear_lanes_and_overflow_cancellation(self):
        a=dict(dot=np.array([[32]]),act_code=np.array(1),weight_code=np.array(1),act_shift=np.array(12),weight_shift=np.array(13),
               q_a=np.ones((1,1,32),dtype=np.uint8),q_w=np.ones((1,1,32),dtype=np.int8),zero_point=np.array(0))
        self.assertTrue(evaluate_node('linear',a,{'profile':'mlp_gate_up'})['valid_mask'][0])
        a['dot'][0,0]=31
        self.assertFalse(evaluate_node('linear',a,{'profile':'mlp_gate_up'})['valid_mask'][0])
        a=dict(dot=np.array([[65280]*130+[-65280]*130]),act_code=np.array(255),weight_code=np.array(255),act_shift=np.array(10),weight_shift=np.array(10))
        r=evaluate_node('linear',a,{'profile':'mlp_gate_up'})
        self.assertEqual(r['current_code'][0],0);self.assertEqual(r['reference_code'][0],0)
        self.assertTrue(r['overflow_mask'][0]);self.assertFalse(r['valid_mask'][0])
        self.assertTrue(r['metric_mask'][0]);self.assertTrue(r['accepted_mask'][0])
        self.assertEqual(r['current_error_counts']['accumulator_overflow'][0],2)
        for value in (np.array([[1.0]]),np.array([[True]])):
            a['dot']=value
            with self.assertRaises(TypeError): evaluate_node('linear',a,{'profile':'mlp_gate_up'})


if __name__=='__main__':unittest.main()
