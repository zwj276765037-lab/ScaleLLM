"""Real new adapter paths against explicit fake CSR/DMA state; no hardware."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'deploy'))
import scalellm
scalellm.vendor_check();scalellm.bootstrap()
from optimized.backends import ResidentAttention,ResidentGu
from evidence import Evidence
from host.scalellm_mlp_gu_only_runtime import GuDescriptor


class FakeSession:
    def __init__(self):
        self.r={0x10c:0x7b,0x260:0x23,0x324:8,0x14c:2,0x144:1,0x00c:0x18};self.writes=[];self.short=False;self.output=bytes(196608);self.meta_busy_reads=0
    def read32(self,a):
        if a==0x178 and self.meta_busy_reads:
            self.meta_busy_reads-=1
            if self.meta_busy_reads==0:self.r[0x324]|=8
            return 4
        return self.r.get(a,0)
    def write32(self,a,v):
        self.writes.append((a,v));self.r[a]=v
        if a==0x008:
            if v&1:self.r[0x00c]=0x19
            if v==2:self.r[0x00c]=0x18
        if a==0x154 and v==1:
            b=self.r[0x150];self.r[0x14c]|=8<<b;self.r[0x160 if b else 0x15c]=229376;self.r[0x250]=229376;self.r[0x258]=7340032;self.r[0x324]&=~8;self.meta_busy_reads=2
    def h2c_write_local(self,c,data,a,chunk):return len(data)-1 if self.short else len(data)
    def c2h_read_local(self,c,size,a,chunk):return self.output[:-1] if self.short else self.output
    def complete_attention(self,command=1,request=2,cohort=0,layer=0):
        self.r.update({0x00c:0x1a,0x038:8,0x03c:81920,0x040:640,0x044:512,0x048:256,0x078:request,0x07c:command,0x080:((cohort*3)<<16)|cohort,0x084:layer,0x088:cohort*3})
        for a in range(0x050,0x070,4):self.r[a]=1


class Catalog:
    mode='audited_baseline'
    def expected(self,*args):return hashlib.sha256(bytes(196608)).hexdigest()
    def check(self,*args):
        if args[-2]!=bytes(196608):raise AssertionError('wrong full output')


class Artifacts:
    original=None
    def __init__(self):self.original=self;self.rope=type('Record',(),{'sha256':'rope'})()
    def layer_artifact(self,layer,name):return type('Record',(),{'sha256':name})()


class OptimizedProtocolTests(unittest.TestCase):
    def test_attention_copy_guard_durable_before_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            s=FakeSession();e=Evidence(Path(folder)/'out');a=ResidentAttention(s,Artifacts(),type('S',(),{'require':lambda self:None})(),e,Catalog(),lambda:None)
            a.start(0,0,0,bytes(196608),1,2,'a');s.complete_attention();actual,r=a.collect()
            self.assertTrue(r['copied'] and r['sticky_cleared']);self.assertEqual(s.writes[-1],(8,2));self.assertIsNone(a.pending)
            with self.assertRaises(ValueError):a.start(0,0,0,bytes(196608),1,2,'b')
    def test_attention_faults_do_not_clear(self):
        for failure in ('identity','short','gold','durable','timeout','future'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as folder:
                s=FakeSession();e=Evidence(Path(folder)/'out');state={'failed':False}
                def check():
                    if state['failed']:raise RuntimeError('CPU future poisoned owner')
                a=ResidentAttention(s,Artifacts(),type('S',(),{'require':lambda self:None})(),e,Catalog(),check);a.start(0,0,0,bytes(196608),1,2,'a');s.complete_attention()
                if failure=='identity':s.r[0x07c]=999
                if failure=='short':s.short=True
                if failure=='gold':s.output=bytes([1])+bytes(196607)
                if failure=='durable':
                    old=e.write_bytes
                    def write(path,data):
                        if path.endswith('output_s24.bin'):raise OSError('durable disk failure')
                        return old(path,data)
                    e.write_bytes=write
                if failure=='future':state['failed']=True
                if failure=='timeout':
                    s.r[0x00c]=0x19
                    with mock.patch('optimized.backends.time.perf_counter',side_effect=[0,11]):
                        with self.assertRaises(TimeoutError):a.collect()
                else:
                    with self.assertRaises(Exception):a.collect()
                self.assertNotIn((8,2),s.writes);self.assertIsNotNone(a.pending);self.assertTrue(a.failed)
    def test_metadata_requires_both_copies_acked_and_no_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            s=FakeSession();e=Evidence(Path(folder)/'out');g=ResidentGu(s,Artifacts(),None,e,None,lambda:None)
            g.lease=(0,1,1);g.acked_cohorts={0};g.pending=GuDescriptor(2,2,1,0,3,1,1,1);g.current_record={};s.r[0x324]=1
            g._write(0x320,1)
            self.assertNotIn((0x154,1),s.writes)
            with self.assertRaises(RuntimeError):g.prefetch_after_pair(1)
            with self.assertRaises(RuntimeError):g.load_metadata(1,after_last_start=True)
            g.pending=None;s.r[0x324]=8
            with self.assertRaises(RuntimeError):g.prefetch_after_pair(1)
            with self.assertRaises(RuntimeError):g.load_metadata(1)
            self.assertNotIn((0x154,1),s.writes)
            g.acked_cohorts={0,1};g.prefetch_after_pair(1)
            self.assertEqual(s.meta_busy_reads,0);self.assertEqual(g.loading['count'],229376)
            self.assertEqual(g.loading['boundary'],'after both cohort full copies and ACKs')
            self.assertEqual(g.loading['dma_physical_bytes'],7340032);self.assertEqual(g.loading['dma_gate_records'],229376)
            self.assertEqual(s.r[0x14c]&0x18,0x10);self.assertTrue(s.r[0x324]&8)
            self.assertNotIn((0x154,2),s.writes)
    def test_global_other_engine_error_blocks_new_start(self):
        with tempfile.TemporaryDirectory() as folder:
            s=FakeSession();s.r[0x324]=12;e=Evidence(Path(folder)/'out');a=ResidentAttention(s,Artifacts(),type('S',(),{'require':lambda self:None})(),e,Catalog(),lambda:None)
            with self.assertRaises(RuntimeError):a.start(0,0,0,bytes(196608),1,2,'a')
            self.assertEqual(s.writes,[])


if __name__=='__main__':unittest.main()
