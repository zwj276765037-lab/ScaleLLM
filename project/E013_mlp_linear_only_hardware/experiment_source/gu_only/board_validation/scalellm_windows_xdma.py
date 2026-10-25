"""Windows XDMA overlapped transport and an SSH stdio bridge.

Windows side supports the installed Python 3.6 and uses only the standard
library. Linux-side backend and gold run in the existing modern interpreter.
No operation is retried. stdout in --rpc mode contains JSON protocol only.
"""
import argparse
import base64
import ctypes as C
import datetime
import hashlib
import json
import os
import queue
import struct
import subprocess
import sys
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


class SshWindowsSession:
    def __init__(self):
        self.process=None;self.lock=threading.RLock();self.responses=queue.Queue();self.sequence=0;self.poisoned=False
        self.log_path=os.environ.get('SCALELLM_WINDOWS_XDMA_LOG')

    def __enter__(self):
        if self.process:raise RuntimeError('RPC already open')
        script=os.environ['SCALELLM_WINDOWS_BRIDGE_PATH']
        ps="& 'D:/software/Anaconda3/python.exe' -u '"+script.replace("'","''")+"' --rpc"
        encoded=base64.b64encode(ps.encode('utf-16le')).decode()
        argv=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','hap-dell','powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',encoded]
        self.process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
        self.stderr=[]
        def reader():
            try:
                for line in self.process.stdout:self.responses.put(line)
            finally:self.responses.put(None)
        def errors():
            for line in self.process.stderr:self.stderr.append(line.decode('utf-8',errors='replace'))
        threading.Thread(target=reader,daemon=True).start();threading.Thread(target=errors,daemon=True).start()
        self._request('open')
        return self

    def _request(self,method,**args):
        if not self.process:raise RuntimeError('RPC is not open')
        if self.poisoned and method!='close':raise RuntimeError('Windows RPC transport poisoned; no further I/O permitted')
        with self.lock:
            self.sequence+=1;ident=self.sequence
            event={'id':ident,'method':method,'args':{k:(hashlib.sha256(base64.b64decode(v)).hexdigest() if k=='data' else v) for k,v in args.items()}}
            log_event(self.log_path,dict(event,event='request'))
            message=(json.dumps(dict(id=ident,method=method,**args))+'\n').encode()
            sent=0
            while sent<len(message):
                count=self.process.stdin.write(message[sent:])
                if not count:raise IOError('Windows RPC stdin made no progress; no request retry issued')
                sent+=count
            self.process.stdin.flush()
            try:line=self.responses.get(timeout=8.0)
            except queue.Empty:self.poisoned=True;self.close(force=True);raise TimeoutError('Windows RPC did not return within8s; no retry issued')
            if line is None:self.poisoned=True;raise IOError('Windows RPC ended: '+''.join(self.stderr)[-2000:])
            result=json.loads(line.decode('utf-8'))
            if result.get('id')!=ident:raise IOError('RPC response identity mismatch')
            log_event(self.log_path,{'event':'response','id':ident,'method':method,'ok':result.get('ok'),'error':result.get('error'),'value':result.get('value') if method in ('read32','open','write32') else None})
            if not result.get('ok'):
                self.poisoned=True
                raise IOError('Windows '+result.get('error','unknown error'))
            return result.get('value')

    def read32(self,offset):return self._request('read32',offset=offset)
    def write32(self,offset,value):return self._request('write32',offset=offset,value=value)
    def h2c_write_local(self,channel,data,local_offset,chunk_bytes):
        view=memoryview(data).cast('B');host_address(channel,local_offset,len(view));total=0
        if chunk_bytes<=0:raise ValueError('Chunk must be positive')
        for start in range(0,len(view),min(chunk_bytes,1<<20)):
            block=bytes(view[start:start+min(chunk_bytes,1<<20)])
            count=self._request('h2c',channel=channel,offset=local_offset+start,data=base64.b64encode(block).decode(),size=len(block))
            if count!=len(block):raise IOError('Short remote H2C')
            total+=count
        return total
    def c2h_read_local(self,channel,size,local_offset,chunk_bytes):
        host_address(channel,local_offset,size);parts=[]
        if chunk_bytes<=0:raise ValueError('Chunk must be positive')
        for start in range(0,size,min(chunk_bytes,1<<20)):
            n=min(chunk_bytes,1<<20,size-start)
            block=base64.b64decode(self._request('c2h',channel=channel,offset=local_offset+start,size=n),validate=True)
            if len(block)!=n:raise IOError('Short remote C2H')
            parts.append(block)
        return b''.join(parts)
    def close(self,force=False):
        if not self.process:return
        process=self.process
        try:
            if process.poll() is None and not force:
                try:self._request('close')
                except Exception:pass
            if process.stdin:process.stdin.close()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=2)
        finally:
            for pipe in (process.stdout,process.stderr):
                if pipe:pipe.close()
            self.process=None
            log_event(self.log_path,{'operation':'rpc_close','exit_code':process.returncode,'stderr':''.join(self.stderr)[-4000:]})
    def __exit__(self,*args):self.close()


def create_session():
    return WindowsXdmaSession() if os.name=='nt' else SshWindowsSession()


def rpc_main():
    session=None
    try:
        for line in sys.stdin:
            request=json.loads(line);method=request['method'];ident=request['id']
            try:
                if method=='open':
                    if session is not None:raise RuntimeError('Session already open')
                    session=WindowsXdmaSession();session.__enter__();value={'paths':session.paths,'python':sys.version,'timeout_ms':session.timeout_ms}
                elif method=='close':
                    if session:session.close();session=None
                    value=True
                elif method=='read32':value=session.read32(request['offset'])
                elif method=='write32':session.write32(request['offset'],request['value']);value=None
                elif method=='h2c':
                    data=base64.b64decode(request['data'],validate=True)
                    if len(data)!=request['size']:raise ValueError('RPC payload size mismatch')
                    value=session.h2c_write_local(request['channel'],data,request['offset'],1<<20)
                elif method=='c2h':value=base64.b64encode(session.c2h_read_local(request['channel'],request['size'],request['offset'],1<<20)).decode()
                else:raise ValueError('Unknown RPC method')
                response={'id':ident,'ok':True,'value':value}
            except Exception as error:response={'id':ident,'ok':False,'error':type(error).__name__+': '+str(error)}
            sys.stdout.write(json.dumps(response)+'\n');sys.stdout.flush()
            if method=='close':break
    finally:
        if session:session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--rpc',action='store_true');args=parser.parse_args()
    if args.rpc:rpc_main()
