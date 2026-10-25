import ctypes as C
import unittest

import scalellm_windows_xdma as x


class FakeKernel:
    def __init__(self,wait=0,completed=4):
        self.wait=wait;self.completed=completed;self.cancelled=0;self.freed=0;self.buffers=[];self.offset=None
    def VirtualAlloc(self,*args):
        buffer=C.create_string_buffer(args[1]);self.buffers.append(buffer);return C.addressof(buffer)
    def CreateEventW(self,*args):return 123
    def ReadFile(self,handle,buffer,size,done,ov):
        self.offset=(ov._obj.OffsetHigh<<32)|ov._obj.Offset
        C.memmove(buffer,b'\x05\x46\x38\x48',min(size,4));return self.wait!=258
    def WriteFile(self,*args):return self.ReadFile(*args)
    def GetOverlappedResult(self,handle,ov,done,wait):done._obj.value=self.completed;return True
    def WaitForSingleObject(self,*args):return self.wait
    def CancelIoEx(self,*args):self.cancelled+=1;return True
    def CloseHandle(self,*args):return True
    def VirtualFree(self,*args):self.freed+=1;return True


def session(kernel):
    s=x.WindowsXdmaSession.__new__(x.WindowsXdmaSession)
    s.kernel=kernel;s.handles={'user':1};s.poisoned=False;s.quarantine=[];s.timeout_ms=5000;s.log_path=None
    return s


class TransportTests(unittest.TestCase):
    def test_unsigned_apertures(self):
        self.assertEqual(x.host_address(0,0x7fff0000,4096),0x7fff0000)
        self.assertEqual(x.host_address(1,0x7fff0000,4096),0xffff0000)
        self.assertRaises(ValueError,x.host_address,1,0x7fffffff,2)
        self.assertRaises(ValueError,x.host_address,2,0,4)
    def test_exact_count_and_64bit_overlapped_offset(self):
        k=FakeKernel();s=session(k)
        self.assertEqual(s._io('user',0x123ffff0000,4),b'\x05\x46\x38\x48')
        self.assertEqual(k.offset,0x123ffff0000);self.assertEqual(k.freed,1)
    def test_short_read_poisoned(self):
        s=session(FakeKernel(completed=3))
        self.assertRaises(IOError,s._io,'user',0,4);self.assertTrue(s.poisoned)
    def test_timeout_requests_cancel_and_retains_pending_buffer(self):
        k=FakeKernel(wait=258);s=session(k)
        original=getattr(C,'get_last_error',None)
        C.get_last_error=lambda:997
        try:self.assertRaises(TimeoutError,s._io,'user',0,4)
        finally:
            if original is None:del C.get_last_error
            else:C.get_last_error=original
        self.assertTrue(s.poisoned);self.assertEqual(k.cancelled,1)
        self.assertEqual(k.freed,0);self.assertEqual(len(s.quarantine),1)


if __name__=='__main__':unittest.main()
