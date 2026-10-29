"""Local Windows XDMA overlapped transport. No operation is retried."""
import ctypes as C
import datetime
import hashlib
import json
import os
import struct
import threading
import time
import uuid

DWORD=C.c_uint32
WORD=C.c_uint16
ULONG_PTR=C.c_size_t
HANDLE=C.c_void_p
INVALID_HANDLE=C.c_void_p(-1).value
GUID_TEXT='74c7e4a9-6d5d-4a70-bc0d-20691dff9e9d'


class GUID(C.Structure):
    _fields_=[('Data1',DWORD),('Data2',WORD),('Data3',WORD),('Data4',C.c_ubyte*8)]


class DEVICE_INTERFACE(C.Structure):
    _fields_=[('cbSize',DWORD),('InterfaceClassGuid',GUID),('Flags',DWORD),('Reserved',ULONG_PTR)]


class OVERLAPPED(C.Structure):
    _fields_=[('Internal',ULONG_PTR),('InternalHigh',ULONG_PTR),('Offset',DWORD),('OffsetHigh',DWORD),('hEvent',HANDLE)]


def host_address(channel, local, size):
    if type(channel) is not int or channel not in (0,1): raise ValueError('DDR channel must be 0 or 1')
    if type(local) is not int or type(size) is not int or local<0 or size<0 or local+size>0x80000000: raise ValueError('DDR-local span outside 2GiB aperture')
    return (channel<<31)+local


def log_event(path, event):
    if path:
        event=dict(event)
        event['utc']=datetime.datetime.utcnow().isoformat()+'Z'
        with open(path,'a',encoding='utf-8') as handle:
            handle.write(json.dumps(event,sort_keys=True)+'\n')


class WindowsXdmaSession:
    def __init__(self, timeout_ms=5000, open_dma=True, log_path=None):
        if os.name!='nt': raise RuntimeError('WindowsXdmaSession requires Windows')
        self.timeout_ms=int(timeout_ms)
        if not 0<self.timeout_ms<=5000: raise ValueError('I/O timeout must be within 1..5000 ms')
        self.open_dma=open_dma
        self.log_path=log_path
        self.handles={}
        self.paths={}
        self.lock=threading.RLock()
        self.poisoned=False
        self.quarantine=[]
        self.kernel=C.WinDLL('kernel32',use_last_error=True)
        self.setup=C.WinDLL('setupapi',use_last_error=True)
        self._bind()

    def _bind(self):
        k=self.kernel;s=self.setup
        k.CreateFileW.argtypes=[C.c_wchar_p,DWORD,DWORD,C.c_void_p,DWORD,DWORD,HANDLE];k.CreateFileW.restype=HANDLE
        k.CloseHandle.argtypes=[HANDLE];k.CloseHandle.restype=C.c_int
        k.CreateEventW.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_wchar_p];k.CreateEventW.restype=HANDLE
        k.ReadFile.argtypes=[HANDLE,C.c_void_p,DWORD,C.POINTER(DWORD),C.POINTER(OVERLAPPED)];k.ReadFile.restype=C.c_int
        k.WriteFile.argtypes=k.ReadFile.argtypes;k.WriteFile.restype=C.c_int
        k.GetOverlappedResult.argtypes=[HANDLE,C.POINTER(OVERLAPPED),C.POINTER(DWORD),C.c_int];k.GetOverlappedResult.restype=C.c_int
        k.WaitForSingleObject.argtypes=[HANDLE,DWORD];k.WaitForSingleObject.restype=DWORD
        k.CancelIoEx.argtypes=[HANDLE,C.POINTER(OVERLAPPED)];k.CancelIoEx.restype=C.c_int
        k.VirtualAlloc.argtypes=[C.c_void_p,C.c_size_t,DWORD,DWORD];k.VirtualAlloc.restype=C.c_void_p
        k.VirtualFree.argtypes=[C.c_void_p,C.c_size_t,DWORD];k.VirtualFree.restype=C.c_int
        s.SetupDiGetClassDevsW.argtypes=[C.POINTER(GUID),C.c_wchar_p,HANDLE,DWORD];s.SetupDiGetClassDevsW.restype=HANDLE
        s.SetupDiEnumDeviceInterfaces.argtypes=[HANDLE,C.c_void_p,C.POINTER(GUID),DWORD,C.POINTER(DEVICE_INTERFACE)];s.SetupDiEnumDeviceInterfaces.restype=C.c_int
        s.SetupDiGetDeviceInterfaceDetailW.argtypes=[HANDLE,C.POINTER(DEVICE_INTERFACE),C.c_void_p,DWORD,C.POINTER(DWORD),C.c_void_p];s.SetupDiGetDeviceInterfaceDetailW.restype=C.c_int
        s.SetupDiDestroyDeviceInfoList.argtypes=[HANDLE];s.SetupDiDestroyDeviceInfoList.restype=C.c_int

    def enumerate(self):
        guid=GUID.from_buffer_copy(uuid.UUID(GUID_TEXT).bytes_le)
        group=self.setup.SetupDiGetClassDevsW(C.byref(guid),None,None,0x12)
        if group==INVALID_HANDLE: raise C.WinError(C.get_last_error())
        paths=[]
        try:
            index=0
            while True:
                interface=DEVICE_INTERFACE();interface.cbSize=C.sizeof(interface)
                if not self.setup.SetupDiEnumDeviceInterfaces(group,None,C.byref(guid),index,C.byref(interface)):
                    error=C.get_last_error()
                    if error==259: break
                    raise C.WinError(error)
                needed=DWORD()
                self.setup.SetupDiGetDeviceInterfaceDetailW(group,C.byref(interface),None,0,C.byref(needed),None)
                if not needed.value: raise C.WinError(C.get_last_error())
                buffer=C.create_string_buffer(needed.value)
                C.cast(buffer,C.POINTER(DWORD))[0]=8 if C.sizeof(C.c_void_p)==8 else 6
                if not self.setup.SetupDiGetDeviceInterfaceDetailW(group,C.byref(interface),buffer,needed.value,C.byref(needed),None): raise C.WinError(C.get_last_error())
                paths.append(C.wstring_at(C.addressof(buffer)+4))
                index+=1
        finally:self.setup.SetupDiDestroyDeviceInfoList(group)
        return paths

    def __enter__(self):
        if self.handles: raise RuntimeError('Session already open')
        candidates=[p for p in self.enumerate() if 'ven_10ee&dev_9018' in p.lower()]
        if len(candidates)!=1: raise RuntimeError('Expected one active VEN10EE DEV9018 interface, found: '+repr(candidates))
        self.base=candidates[0]
        names=['user','h2c_0','c2h_0'] if self.open_dma else ['user']
        try:
            for name in names:
                path=self.base+'\\'+name
                access=0x80000000 if name=='c2h_0' else 0x40000000 if name=='h2c_0' else 0xC0000000
                handle=self.kernel.CreateFileW(path,access,0,None,3,0x40000000,None)
                if handle==INVALID_HANDLE: raise C.WinError(C.get_last_error())
                self.handles[name]=handle;self.paths[name]=path
            log_event(self.log_path,{'operation':'open','paths':self.paths,'share_mode':0,'overlapped':True,'timeout_ms':self.timeout_ms})
            return self
        except BaseException:self.close();raise

    def close(self):
        for name,handle in list(self.handles.items()):
            self.kernel.CancelIoEx(handle,None)
            self.kernel.CloseHandle(handle)
        self.handles.clear()
        log_event(self.log_path,{'operation':'close','quarantined_requests':len(self.quarantine)})

    def __exit__(self,*args):self.close()

    def _io(self,name,offset,size,data=None):
        if self.poisoned: raise RuntimeError('Transport poisoned; no further operation permitted')
        if not 0<=offset<=0xffffffffffffffff or not 0<size<=0xffffffff: raise ValueError('Invalid 64-bit offset / DWORD length')
        handle=self.handles[name]
        buffer=self.kernel.VirtualAlloc(None,size,0x3000,0x04)
        if not buffer: raise C.WinError(C.get_last_error())
        event=self.kernel.CreateEventW(None,True,False,None)
        if not event:self.kernel.VirtualFree(buffer,0,0x8000);raise C.WinError(C.get_last_error())
        ov=OVERLAPPED();ov.Offset=offset&0xffffffff;ov.OffsetHigh=(offset>>32)&0xffffffff;ov.hEvent=event
        done=DWORD();pending=False;quarantined=False
        started=time.monotonic()
        try:
            if data is not None:C.memmove(buffer,data,size)
            operation=self.kernel.WriteFile if data is not None else self.kernel.ReadFile
            ok=operation(handle,buffer,size,C.byref(done),C.byref(ov))
            if not ok:
                error=C.get_last_error()
                if error!=997: raise C.WinError(error)
                pending=True
                wait=self.kernel.WaitForSingleObject(event,self.timeout_ms)
                if wait==258:
                    cancelled=self.kernel.CancelIoEx(handle,C.byref(ov));cancel_error=0 if cancelled else C.get_last_error()
                    drain=self.kernel.WaitForSingleObject(event,1000)
                    if drain!=0:
                        self.quarantine.append((buffer,ov,event));quarantined=True
                    else:self.kernel.GetOverlappedResult(handle,C.byref(ov),C.byref(done),False)
                    self.poisoned=True
                    log_event(self.log_path,{'operation':'timeout','node':name,'offset':offset,'size':size,'cancel_requested':bool(cancelled),'cancel_error':cancel_error,'cancel_drain_wait':int(drain),'elapsed_s':time.monotonic()-started})
                    raise TimeoutError('XDMA operation exceeded5s; cancel requested; transport poisoned')
                if wait!=0:raise C.WinError(C.get_last_error())
            if not self.kernel.GetOverlappedResult(handle,C.byref(ov),C.byref(done),False):raise C.WinError(C.get_last_error())
            pending=False
            if done.value!=size:
                self.poisoned=True
                raise IOError('Short XDMA I/O: requested %d, completed %d at0x%x'%(size,done.value,offset))
            result=None if data is not None else C.string_at(buffer,size)
            log_event(self.log_path,{'operation':'write' if data is not None else 'read','node':name,'offset':offset,'offset_hex':hex(offset),'size':size,'completed':done.value,'sha256':hashlib.sha256(data if data is not None else result).hexdigest(),'elapsed_s':time.monotonic()-started})
            return size if data is not None else result
        except BaseException:
            self.poisoned=True
            if pending and not quarantined:
                self.kernel.CancelIoEx(handle,C.byref(ov))
                if self.kernel.WaitForSingleObject(event,1000)!=0:self.quarantine.append((buffer,ov,event));quarantined=True
            raise
        finally:
            if not quarantined:self.kernel.CloseHandle(event);self.kernel.VirtualFree(buffer,0,0x8000)

    def read32(self,offset):
        if type(offset) is not int or offset<0 or offset&3:raise ValueError('CSR offset must be nonnegative and4-byte aligned')
        with self.lock:return struct.unpack('<I',self._io('user',offset,4))[0]

    def write32(self,offset,value):
        if type(offset) is not int or offset<0 or offset&3 or type(value) is not int or not 0<=value<=0xffffffff:raise ValueError('Invalid CSR offset/U32 value')
        with self.lock:self._io('user',offset,4,struct.pack('<I',value))

    def h2c_write_local(self,channel,data,local_offset,chunk_bytes):
        view=memoryview(data).cast('B');address=host_address(channel,local_offset,len(view))
        if chunk_bytes<=0:raise ValueError('Chunk must be positive')
        with self.lock:
            for start in range(0,len(view),chunk_bytes):
                block=bytes(view[start:start+chunk_bytes]);self._io('h2c_0',address+start,len(block),block)
        return len(view)

    def c2h_read_local(self,channel,size,local_offset,chunk_bytes):
        address=host_address(channel,local_offset,size)
        if chunk_bytes<=0:raise ValueError('Chunk must be positive')
        with self.lock:return b''.join(self._io('c2h_0',address+start,min(chunk_bytes,size-start)) for start in range(0,size,chunk_bytes))
