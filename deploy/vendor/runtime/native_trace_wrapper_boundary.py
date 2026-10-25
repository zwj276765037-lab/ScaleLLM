"""Boundary-durable call tracing around the unchanged resident helper, Windows Python 3.6.

No ACK/lease/gold logic is replaced. All timing includes tracing overhead.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def utc():return datetime.datetime.utcnow().isoformat()+'Z'


class TraceWriter:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=open(str(self.path),'x',encoding='utf-8')
        self.state_path=self.path.with_suffix('.state.json');self.owner=None;self.sequence=0
        self.buffered_records=0;self.buffer_limit=128;self.last_value=None
        if self.state_path.exists():self.stream.close();raise FileExistsError(self.state_path)
    def owner_state(self):
        o=self.owner
        return None if o is None else {'lease':o.lease,'pending':o.pending,'copied':o.copied,'acked':sorted(o.acked),'failed':o.failed,'command_count':o.command_count}
    def flush_checkpoint(self):
        self.stream.flush();os.fsync(self.stream.fileno())
        if self.last_value is not None:
            tmp=str(self.state_path)+'.tmp'
            with open(tmp,'w',encoding='utf-8') as handle:
                json.dump(self.last_value,handle,sort_keys=True);handle.write('\n');handle.flush();os.fsync(handle.fileno())
            os.replace(tmp,str(self.state_path))
        self.buffered_records=0
    def record(self,event,operation,details=None):
        self.sequence+=1
        critical=(event=='error' or operation=='run' or operation.startswith('owner.') or operation.startswith('phase.') or operation in ('driver.open','driver.close'))
        forced=self.buffered_records+1>=self.buffer_limit
        value={'sequence':self.sequence,'utc':utc(),'monotonic_s':time.perf_counter(),'event':event,'operation':operation,'details':details or {},'owner':self.owner_state(),'durability':'flush+os.fsync' if critical or forced else 'buffered_until_boundary_or_128_records','trace_mode':'boundary'}
        self.stream.write(json.dumps(value,sort_keys=True)+'\n');self.last_value=value;self.buffered_records+=1
        if critical or forced:self.flush_checkpoint()
        return value
    def call(self,operation,details,function):
        self.record('before',operation,details)
        started=time.perf_counter()
        try:result=function()
        except BaseException as error:
            self.record('error',operation,dict(details,error=type(error).__name__+': '+str(error),elapsed_s=time.perf_counter()-started));raise
        measured={'elapsed_s':time.perf_counter()-started}
        if isinstance(result,bytes):measured.update(bytes=len(result),sha256=hashlib.sha256(result).hexdigest())
        elif isinstance(result,(int,str,type(None))):measured['result']=result
        self.record('after',operation,dict(details,**measured));return result
    def close(self):
        try:self.flush_checkpoint()
        finally:self.stream.close()


class TracedSession:
    def __init__(self,inner,trace):self.inner=inner;self.trace=trace
    def __getattr__(self,name):return getattr(self.inner,name)
    def __enter__(self):self.trace.call('driver.open',{},self.inner.__enter__);return self
    def __exit__(self,*args):
        # Close even if trace storage itself fails; never retry a hardware write.
        try:self.trace.record('before','driver.close')
        finally:self.inner.__exit__(*args)
        self.trace.record('after','driver.close')
    def read32(self,address):return self.trace.call('driver.read32',{'offset':address,'offset_hex':hex(address)},lambda:self.inner.read32(address))
    def write32(self,address,value):return self.trace.call('driver.write32',{'offset':address,'offset_hex':hex(address),'value':value,'value_hex':hex(value)},lambda:self.inner.write32(address,value))
    def h2c_write_local(self,channel,data,local_offset,chunk_bytes):
        details={'channel':channel,'offset':local_offset,'bytes':len(data),'chunk_bytes':chunk_bytes}
        return self.trace.call('driver.h2c_write_local',details,lambda:self.inner.h2c_write_local(channel,data,local_offset,chunk_bytes))
    def c2h_read_local(self,channel,size,local_offset,chunk_bytes):
        details={'channel':channel,'offset':local_offset,'bytes':size,'chunk_bytes':chunk_bytes}
        return self.trace.call('driver.c2h_read_local',details,lambda:self.inner.c2h_read_local(channel,size,local_offset,chunk_bytes))


def traced_owner_class(base,trace):
    class TracedOwner(base):
        def __init__(self,*args,**kwargs):
            base.__init__(self,*args,**kwargs);trace.owner=self
            trace.record('after','owner.created')
        def bind(self,epoch):return trace.call('owner.bind',{'epoch':epoch},lambda:base.bind(self,epoch))
        def execute(self,*args,**kwargs):
            details={'command':args[0] if args else kwargs.get('command'),'cohort':args[2] if len(args)>2 else kwargs.get('cohort')}
            return trace.call('owner.execute',details,lambda:base.execute(self,*args,**kwargs))
        def release(self):return trace.call('owner.release',{},lambda:base.release(self))
    return TracedOwner


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native',required=True);p.add_argument('--adapter',required=True);p.add_argument('--trace',required=True)
    args,forward=p.parse_known_args()
    output_parser=argparse.ArgumentParser(add_help=False,allow_abbrev=False);output_parser.add_argument('--result',required=True)
    output_args,unused=output_parser.parse_known_args(forward)
    result_path=Path(output_args.result).resolve();trace_path=Path(args.trace).resolve()
    if trace_path==result_path or result_path in trace_path.parents:raise ValueError('--trace must be outside --result; native creates its result directory exclusively')
    adapter=load('scalellm_windows_xdma',args.adapter);sys.modules['scalellm_windows_xdma']=adapter
    native=load('frozen_resident',args.native)
    if hashlib.sha256(Path(args.native).read_bytes()).hexdigest()!='d0ebe952783607bcc8b470d8989cb708ab0134ae7019c68016d3da7d152b52d3':raise RuntimeError('Frozen native helper identity mismatch')
    if hashlib.sha256(Path(args.adapter).read_bytes()).hexdigest()!='ff64ca61a9bb1345d55fd805e4c43f67c13538de1f58db60580453e1a369fa91':raise RuntimeError('Adapter identity mismatch')
    trace=TraceWriter(args.trace)
    original_session=native.WindowsXdmaSession;original_owner=native.ResidentOwner
    native.WindowsXdmaSession=lambda *a,**kw:TracedSession(original_session(*a,**kw),trace)
    native.ResidentOwner=traced_owner_class(original_owner,trace)
    original_save=getattr(native,'save',None);last_phase=[None]
    if original_save is not None:
        def phase_save(path,value):
            marker=value.get('markers',[])[-1] if isinstance(value,dict) and value.get('markers') else None
            key=(marker.get('phase'),marker.get('utc')) if marker else None
            if key is not None and key!=last_phase[0]:
                last_phase[0]=key
                return trace.call('phase.'+marker['phase'],marker,lambda:original_save(path,value))
            return original_save(path,value)
        native.save=phase_save
    trace.record('before','run',{'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'native_sha256':hashlib.sha256(Path(args.native).read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256(Path(args.adapter).read_bytes()).hexdigest(),'arguments':forward,'host_timing_includes_durable_trace':True,'trace_mode':'boundary','fine_call_buffer_limit':128,'fine_call_crash_loss':'up_to_last_127_records_before_boundary'})
    saved_argv=sys.argv
    try:sys.argv=[args.native]+forward;native.main();trace.record('after','run')
    except BaseException as error:trace.record('error','run',{'error':repr(error)});raise
    finally:sys.argv=saved_argv;trace.close()


if __name__=='__main__':main()
