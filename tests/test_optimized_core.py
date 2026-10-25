"""No device accesses; exact math, cache identities and resident boundaries."""
from pathlib import Path
import sys
import unittest
import concurrent.futures
import gc
import threading
import types
import weakref
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'deploy'))
import scalellm
scalellm.vendor_check();scalellm.bootstrap()
from optimized import layout
from optimized.down import DownContext,DownMemo,exact_down_rows
from host.scalellm_mlp_gu_only import DownWeights,down_blocked_int64
from optimized.run import Run,next_metadata_layer


class OptimizedCoreTests(unittest.TestCase):
    def fixture(self,extreme=False):
        rng=np.random.default_rng(109)
        w=np.full((448,16,32),-8,dtype=np.int8) if extreme else rng.integers(-8,8,(448,16,32),dtype=np.int8)
        code=np.full((448,16),255 if extreme else 64,dtype=np.uint8);shift=np.full((448,16),6 if extreme else 18,dtype=np.uint8)
        weights=DownWeights(w,code,shift,('a','b','meta'),0)
        q=np.full((16,14336),255,dtype=np.uint8) if extreme else rng.integers(0,256,(16,14336),dtype=np.uint8)
        meta=np.full((16,448),((6 if extreme else 18)<<16)|((255 if extreme else 64)<<8)|(0 if extreme else 128),dtype=np.uint32)
        return q,meta,weights
    def test_layout_full_residency_and_canonical_gu(self):
        spans=layout.static_spans();self.assertEqual(len(spans),155)
        self.assertEqual(layout.layer_spans(31)['attention_c1'].address+layout.ATTENTION_HALF,0x50000000)
        self.assertEqual(layout.layer_spans(31)['attention_meta'].address+layout.ATTENTION_META,0x55000000)
        self.assertEqual(layout.layer_spans(31)['mlp_gate_meta'].address+layout.GU_META,0x2e000000)
        self.assertEqual(layout.attention_bases(31,1)['input'],0x56300000)
        with self.assertRaises(ValueError):layout.layer_spans(32)
        with self.assertRaises(ValueError):layout.Span('cross aperture',1,0x7fffffe0,64)
    def test_float_dot_full_exact_random_and_extreme(self):
        for extreme in (False,True):
            q,m,w=self.fixture(extreme);want=down_blocked_int64(q,m,w,require_production_shape=False);ctx=DownContext(w)
            actual=exact_down_rows(q,m,ctx)
            np.testing.assert_array_equal(actual,want)
            np.testing.assert_array_equal(exact_down_rows(q,m,ctx,(1,10,15)),want[[1,10,15]])
    def test_row_memo_actual_wire_and_source_identity(self):
        q,m,w=self.fixture();ctx=DownContext(w);memo=DownMemo();payload=bytes(1376256)
        first,a=memo.compute(0,0,payload,q,m,ctx);self.assertEqual(a['computed_rows'],list(range(16)))
        second,a=memo.compute(0,0,payload,q,m,ctx,range(11));self.assertEqual(a['reused_rows'],list(range(11)));np.testing.assert_array_equal(second,first)
        changed=bytearray(payload);changed[3]=1
        _,a=memo.compute(0,0,changed,q,m,ctx,range(11));self.assertEqual(a['reused_rows'],list(range(1,11)))
        other=DownWeights(w.values,w.codes,w.shifts,('different','b','meta'),0)
        _,a=memo.compute(0,0,changed,q,m,DownContext(other),range(11));self.assertEqual(a['reused_rows'],[])
    def test_future_result_not_retained_and_first_error_poison(self):
        r=object.__new__(Run);r.failed=None;r.cpu_lock=threading.RLock();r.guard=lambda:None;r.a=types.SimpleNamespace(failed=None,pending={'accepted':True});r.gu=types.SimpleNamespace(poisoned=None)
        class Sentinel:pass
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            r.pool=pool;f=r.submit(Sentinel);item=f.result();ref=weakref.ref(item);del item,f
            pool.submit(lambda:None).result();gc.collect();self.assertIsNone(ref())
            def bad():raise ValueError('CPU future first error')
            f=r.submit(bad)
            with self.assertRaises(ValueError):f.result()
        with self.assertRaises(RuntimeError):r.check()
        self.assertEqual(r.a.pending,{'accepted':True})
    def test_terminal_layer_does_not_prefetch_before_eos(self):
        self.assertEqual(next_metadata_layer(30,32),31)
        self.assertIsNone(next_metadata_layer(31,32));self.assertIsNone(next_metadata_layer(0,1))


if __name__=='__main__':unittest.main()
