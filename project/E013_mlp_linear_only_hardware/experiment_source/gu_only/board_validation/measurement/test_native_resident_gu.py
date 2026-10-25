import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
spec=importlib.util.spec_from_file_location('resident',HERE/'native_resident_gu.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
ROOT=next(p for p in HERE.parents if (p/'project/hardware/source/mlp_linear/abi_gu_only.json').exists())
FIELDS=json.loads((ROOT/'project/hardware/source/mlp_linear/abi_gu_only.json').read_text())['descriptor']['fields']


class Device:
    def __init__(self,bad_output=False):
        self.csr={0x324:8,0x2a8:0,0x260:0x23,0x14c:6,0x144:1,0x11c:0,0x12c:0,0x130:0x1c00000,0x134:0,0x138:0,0x370:0,0x368:2}
        self.writes=[];self.events=[];self.bad_output=bad_output
    def read32(self,a):return self.csr.get(a,0)
    def write32(self,a,v):
        self.writes.append((a,v));self.csr[a]=v
        if a==0x36c:self.csr[0x368]=v
        if a==0x320:
            self.events.append('start');self.csr[0x324]=10
            mapping={0x328:0x30c,0x32c:0x318,0x330:0x31c,0x334:0x140,0x338:0x118,0x33c:0x280,0x340:0x284,0x344:0x11c,0x348:0x310,0x34c:0x314}
            for dst,src in mapping.items():self.csr[dst]=self.csr[src]
            self.csr.update({0x350:0,0x364:1792,0x354:735000,0x358:100,0x35c:735500,0x360:200})
        if a==0x2a0:self.events.append('ack');self.csr[0x324]=8
    def h2c_write_local(self,c,data,offset,chunk):self.events.append('h2c');return len(data)
    def c2h_read_local(self,c,size,offset,chunk):self.events.append('c2h');return (b'B' if self.bad_output else b'A')*size


class OwnerTests(unittest.TestCase):
    def owner(self,device,path):return n.ResidentOwner(device,FIELDS,Path(path),1,0,0)
    def test_resident_rebind_and_pair_release(self):
        with tempfile.TemporaryDirectory() as path:
            d=Device();owner=self.owner(d,path)
            try:
                owner.bind(100);self.assertRaises(RuntimeError,owner.release)
                for cohort in (0,1):owner.execute(1000+cohort,1,cohort,1,b'x'*73728,b'A'*1376256,'measured')
                owner.release();self.assertIsNone(owner.lease);self.assertEqual(d.events,['h2c','start','c2h','ack']*2)
                self.assertRaises(RuntimeError,owner.bind,100)
                owner.bind(101);self.assertEqual(owner.lease,101)
                self.assertFalse(any(a in (0x150,0x154,0x158) for a,v in d.writes))
                self.assertEqual(len(list(Path(path).glob('output_*.bin'))),1)
            finally:owner.stream.close()
    def test_generation_change_stops_before_any_epoch_write(self):
        with tempfile.TemporaryDirectory() as path:
            d=Device();d.csr[0x144]=2;owner=self.owner(d,path)
            try:self.assertRaises(RuntimeError,owner.bind,100);self.assertEqual(d.writes,[])
            finally:owner.stream.close()
    def test_numerical_failure_retains_done_without_ack(self):
        with tempfile.TemporaryDirectory() as path:
            d=Device(True);owner=self.owner(d,path)
            try:
                owner.bind(100);self.assertRaises(AssertionError,owner.execute,1000,1,0,1,b'x'*73728,b'A'*1376256,'measured')
                self.assertEqual(owner.pending,1000);self.assertEqual(owner.lease,100);self.assertNotIn('ack',d.events)
                self.assertRaises(RuntimeError,owner.execute,1001,1,1,1,b'x'*73728,b'A'*1376256,'measured')
                self.assertEqual(len(list(Path(path).glob('output_*.bin'))),1)
            finally:owner.stream.close()


if __name__=='__main__':unittest.main()
