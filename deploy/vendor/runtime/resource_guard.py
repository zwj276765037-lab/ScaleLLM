"""Read-only Windows process/RAM budget, with no system policy modifications."""
import ctypes
from ctypes import wintypes
import os


class ResourceGuard:
    def __init__(self,rss_limit=6<<30,available_floor=2<<30):
        if os.name!='nt':raise RuntimeError('Actual execution requires Windows')
        self.rss_limit=rss_limit;self.available_floor=available_floor
        self.peak_rss=0;self.lowest_available=None;self.samples=0
        self.k=ctypes.WinDLL('kernel32',use_last_error=True);self.p=ctypes.WinDLL('psapi',use_last_error=True)
        self.k.GetCurrentProcess.restype=wintypes.HANDLE
        self.p.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        self.k.GlobalMemoryStatusEx.argtypes=[ctypes.c_void_p]
    def __call__(self):
        class MEM(ctypes.Structure):_fields_=[('length',wintypes.DWORD),('load',wintypes.DWORD)]+[(n,ctypes.c_ulonglong) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        class PROC(ctypes.Structure):_fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','working','peak_pool','pool','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
        m=MEM();m.length=ctypes.sizeof(m);p=PROC();p.cb=ctypes.sizeof(p)
        if not self.k.GlobalMemoryStatusEx(ctypes.byref(m)) or not self.p.GetProcessMemoryInfo(self.k.GetCurrentProcess(),ctypes.byref(p),p.cb):raise ctypes.WinError(ctypes.get_last_error())
        self.peak_rss=max(self.peak_rss,p.working,p.peak);self.lowest_available=m.available if self.lowest_available is None else min(self.lowest_available,m.available);self.samples+=1
        if p.working>self.rss_limit or m.available<self.available_floor:raise MemoryError('Budget exceeded: RSS=%d available=%d'%(p.working,m.available))
        return {'rss_bytes':p.working,'available_bytes':m.available}
    def summary(self):return {'rss_limit_bytes':self.rss_limit,'available_memory_floor_bytes':self.available_floor,'peak_rss_bytes':self.peak_rss,'available_memory_lowest_bytes':self.lowest_available,'samples':self.samples,'blas_threads':1}
