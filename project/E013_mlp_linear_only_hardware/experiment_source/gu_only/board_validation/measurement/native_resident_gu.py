"""Python3.6 native Windows resident GU benchmark under the frozen v7 ABI.

Precondition: unchanged original backend has staged and independently validated
both cohorts, ACKed and released its lease, then closed every RPC handle.
This independent measurement owner never loads metadata or changes GU bases.
"""
import argparse
import ctypes as C
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0,str(Path(__file__).resolve().parent))
from scalellm_windows_xdma import WindowsXdmaSession

ABI_SHA='318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a'
IDENTITY={0:0x48384103,4:0x20000,0x100:0x48384605,0x104:0x70000,0x2b8:0x4d303032,0x300:0x4d4c0002,0x304:0x1d,0x308:1}
SNAPSHOT=(0x10c,0x11c,0x12c,0x130,0x134,0x138,0x144,0x14c,0x178,0x260,0x2a8,0x324,0x350,0x368,0x370)


def utc():return datetime.datetime.utcnow().isoformat()+'Z'
def digest(data):return hashlib.sha256(data).hexdigest()
def save(path,value):
    with open(str(path),'w',encoding='utf-8') as handle:json.dump(value,handle,indent=2,sort_keys=True)


class ResidentOwner:
    def __init__(self,session,descriptor_fields,output_dir,generation,bank,poll_s=0.0001):
        self.session=session;self.fields=descriptor_fields;self.output_dir=output_dir
        self.generation=generation;self.bank=bank;self.poll_s=poll_s
        self.lease=None;self.pending=None;self.copied=False;self.acked=set()
        self.seen_epochs=set();self.seen_commands=set();self.failed=None;self.command_count=0
        self.stream=open(str(output_dir/'commands.jsonl'),'a',encoding='utf-8')

    def read(self,address):return self.session.read32(address)
    def write(self,address,value):self.session.write32(address,value)
    def snapshot(self):return {'0x%03x'%a:self.read(a) for a in tuple(IDENTITY)+SNAPSHOT}
    def idle(self):
        status=self.read(0x324)
        if status&31!=8 or self.read(0x2a8)&3 or self.read(0x260)&0x1c:raise RuntimeError('Hardware not idle/drained/ACKed/fault-free')
    def resident(self):
        self.idle()
        meta=self.read(0x14c)
        if meta&0x18 or meta&1!=self.bank or not meta&(2<<self.bank) or self.read(0x144)!=self.generation:raise RuntimeError('Resident metadata identity changed')
        for address,expected in ((0x11c,0),(0x12c,0),(0x130,0x01c00000),(0x134,0),(0x138,0)):
            if self.read(address)!=expected:raise RuntimeError('Resident layer/base changed0x%x'%address)
        if self.read(0x370):raise RuntimeError('Existing admission error retained; not cleared')
    def bind(self,epoch):
        if self.failed or self.lease is not None or self.pending is not None or epoch<=0 or epoch in self.seen_epochs:raise RuntimeError('Resident epoch/lease ownership violation')
        self.resident()
        if self.read(0x368)==epoch:raise RuntimeError('Reusing active hardware epoch')
        self.write(0x36c,epoch)
        if self.read(0x370) or self.read(0x368)!=epoch:raise RuntimeError('Resident rebind rejected')
        self.lease=epoch;self.seen_epochs.add(epoch);self.acked=set()
    def release(self):
        if self.pending is not None or self.acked!={0,1}:raise RuntimeError('Cannot release incomplete pair')
        self.resident();self.lease=None
    def _wait_done(self):
        deadline=time.perf_counter()+10.0;last_not_done=None;polls=0
        while True:
            before=time.perf_counter();status=self.read(0x324);after=time.perf_counter();polls+=1
            if status&0x14:raise RuntimeError('Hardware fault/job_error/reset_required')
            if status&2:
                if status&1 or not status&8:raise RuntimeError('Completion not idle/drained')
                return {'done_poll_before_s':before,'done_poll_after_s':after,'last_not_done_after_s':last_not_done,'polls':polls,'status':status}
            last_not_done=after
            if after>=deadline:raise TimeoutError('GU completion timeout; no retry')
            if self.poll_s:time.sleep(self.poll_s)
    def execute(self,command,request,cohort,buffer_generation,payload,gold,tag):
        if self.failed or self.lease is None or self.pending is not None or command in self.seen_commands or cohort in self.acked:raise RuntimeError('Command/cohort/lease ownership violation')
        self.idle();buffer_id=cohort*3;base=0x10000000+buffer_id*0x800000
        words=(command,request,(buffer_id<<16)|cohort,0,1,0x48384605,base,base+0x100000,73728,1376256,buffer_generation,self.generation,self.lease,0,0x01c00000,0,0)
        record={'index':self.command_count,'command':command,'request':request,'cohort':cohort,'buffer':buffer_id,'buffer_generation':buffer_generation,'metadata_generation':self.generation,'epoch':self.lease,'tag':tag,'started_utc':utc(),'command_begin_s':time.perf_counter(),'descriptor_words':list(words),'acked':False,'comparison':'NOT_RUN'}
        self.pending=command;self.seen_commands.add(command)
        try:
            start=time.perf_counter();count=self.session.h2c_write_local(1,payload,base,1<<20);record['input_h2c_s']=time.perf_counter()-start
            if count!=73728:raise IOError('Input H2C short write')
            if self.read(0x370):raise RuntimeError('Prior admission error; no clearing')
            for field,value in zip(self.fields,words):self.write(field['csr'],value)
            record['start_call_before_s']=time.perf_counter();record['start_call_before_utc']=utc()
            self.write(0x320,1)
            record['start_call_after_s']=time.perf_counter()
            if self.read(0x370):raise RuntimeError('START admission rejected')
            record.update(self._wait_done());record['first_done_utc']=utc()
            expected={0x328:1,0x32c:buffer_generation,0x330:self.lease,0x334:self.generation,0x338:command,0x33c:request,0x340:(buffer_id<<16)|cohort,0x344:0,0x348:73728,0x34c:1376256,0x350:0,0x364:1792}
            done={a:self.read(a) for a in sorted(set(expected)|{0x354,0x358,0x35c,0x360})}
            record['done']={'0x%03x'%a:v for a,v in done.items()}
            for address,value in expected.items():
                if done[address]!=value:raise RuntimeError('DONE mismatch0x%x:actual%d expected%d'%(address,done[address],value))
            if any(done[a]==0xffffffff for a in (0x354,0x358,0x35c,0x360)):raise RuntimeError('Saturated timing counter')
            start=time.perf_counter();output=self.session.c2h_read_local(1,1376256,base+0x100000,1<<20);record['output_c2h_s']=time.perf_counter()-start
            if len(output)!=1376256:raise IOError('Output C2H short read')
            self.copied=True
            start=time.perf_counter();matches=output==gold;record['gold_compare_s']=time.perf_counter()-start
            record.update(comparison='PASS' if matches else 'FAIL',output_sha256=digest(output),gold_sha256=digest(gold),copied_bytes=len(output))
            artifact='output_'+record['output_sha256']+'.bin'
            if not (self.output_dir/artifact).exists():(self.output_dir/artifact).write_bytes(output)
            record['output_artifact']=artifact
            if not matches:
                first=next(index for index,(a,b) in enumerate(zip(output,gold)) if a!=b)
                record['first_mismatched_byte']=first
            record['before_ack_utc']=utc();record['before_ack_s']=time.perf_counter()
            self.stream.write(json.dumps(record,sort_keys=True)+'\n');self.stream.flush()
            if not matches:raise AssertionError('Full output differs from independent gold; DONE retained')
            # ACK remains after full owned copy, complete byte comparison and
            # persistence of DONE/identity/comparison for this exact command.
            self.write(0x2a0,command)
            deadline=time.perf_counter()+10
            while self.read(0x324)&3:
                if time.perf_counter()>=deadline:raise TimeoutError('ACK cleanup timeout')
                if self.poll_s:time.sleep(self.poll_s)
            self.idle();self.acked.add(cohort);self.pending=None;self.copied=False
            record.update(acked=True,ended_utc=utc(),command_end_s=time.perf_counter())
            record['start_to_first_done_observed_s']=record['done_poll_after_s']-record['start_call_before_s']
            record['host_end_to_end_s']=record['command_end_s']-record['command_begin_s']
            self.stream.write(json.dumps({'event':'ack','command':command,'record':record},sort_keys=True)+'\n');self.stream.flush()
            self.command_count+=1;self.last_output_artifact=artifact
            return record
        except BaseException as error:
            self.failed=type(error).__name__+': '+str(error);record['error']=self.failed
            self.stream.write(json.dumps({'event':'failure','command':command,'record':record},sort_keys=True)+'\n');self.stream.flush()
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',required=True);parser.add_argument('--abi',required=True);parser.add_argument('--provenance',required=True);parser.add_argument('--result',required=True)
    parser.add_argument('--epoch-base',type=int,required=True);parser.add_argument('--command-base',type=int,required=True);parser.add_argument('--request-id',type=int,required=True)
    parser.add_argument('--warmup',type=int,default=2);parser.add_argument('--measured',type=int,default=20);parser.add_argument('--load-seconds',type=float,default=0);parser.add_argument('--idle-before',type=float,default=0);parser.add_argument('--idle-after',type=float,default=0);parser.add_argument('--poll-s',type=float,default=.0001);parser.add_argument('--max-commands',type=int,default=4000)
    args=parser.parse_args();bundle=Path(args.bundle);out=Path(args.result);out.mkdir(parents=True,exist_ok=False)
    if args.warmup<2 or args.warmup%2 or args.measured<2 or args.measured%2:raise ValueError('Warmup and measured counts must be complete pairs')
    abi_bytes=Path(args.abi).read_bytes()
    if digest(abi_bytes)!=ABI_SHA:raise ValueError('Frozen ABI SHA mismatch')
    abi=json.loads(abi_bytes.decode());manifest=json.loads((bundle/'manifest.json').read_text())
    if manifest['bit_sha256']!='66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47':raise ValueError('Bit manifest identity mismatch')
    inputs={}
    for name in ('input_rec576','gold_gu_s24'):
        entry=manifest['files'][name];data=(bundle/entry['path']).read_bytes()
        if len(data)!=entry['size'] or digest(data)!=entry['sha256']:raise ValueError('Input identity mismatch:'+name)
        inputs[name]=data
    provenance=json.loads(Path(args.provenance).read_text())
    if provenance['bundle_manifest_sha256']!=digest((bundle/'manifest.json').read_bytes()) or not provenance['original_backend_two_cohorts_pass_released']:raise ValueError('No matching completed resident staging provenance')
    receipt={'schema':1,'execution_state':'running','case':manifest['case'],'started_utc':utc(),'host_monotonic_started_s':time.perf_counter(),'clock_hz':100000000,'poll_s':args.poll_s,'source_sha256':digest(Path(__file__).read_bytes()),'adapter_sha256':digest(Path(__file__).with_name('scalellm_windows_xdma.py').read_bytes()),'bundle_manifest_sha256':digest((bundle/'manifest.json').read_bytes()),'provenance':provenance,'markers':[],'commands':[],'warmup_commands':args.warmup,'measured_minimum':args.measured,'max_commands':args.max_commands,'retained_pending':None,'retained_lease':None}
    owner=None
    def marker(phase):
        value={'phase':phase,'utc':utc(),'monotonic_s':time.perf_counter(),'commands_completed':owner.command_count if owner else 0};receipt['markers'].append(value);save(out/'receipt.json',receipt)
    try:
        with WindowsXdmaSession() as session:
            kernel=session.kernel
            kernel.GetCurrentProcess.restype=C.c_void_p
            kernel.GetProcessAffinityMask.argtypes=[C.c_void_p,C.POINTER(C.c_size_t),C.POINTER(C.c_size_t)]
            kernel.SetProcessAffinityMask.argtypes=[C.c_void_p,C.c_size_t]
            process=kernel.GetCurrentProcess();allowed=C.c_size_t();system=C.c_size_t()
            if not kernel.GetProcessAffinityMask(process,C.byref(allowed),C.byref(system)):raise C.WinError(C.get_last_error())
            bits=[1<<index for index in range(C.sizeof(C.c_size_t)*8) if allowed.value&(1<<index)][:8]
            mask=sum(bits)
            if not kernel.SetProcessAffinityMask(process,mask):raise C.WinError(C.get_last_error())
            receipt['cpu_affinity_mask']=mask
            initial={a:session.read32(a) for a in tuple(IDENTITY)+SNAPSHOT};save(out/'csr_before.json',{'0x%03x'%a:v for a,v in initial.items()})
            for address,value in IDENTITY.items():
                if initial[address]!=value:raise RuntimeError('Application ABI mismatch before any write')
            generation=initial[0x144];bank=initial[0x14c]&1
            if generation!=provenance['metadata_generation'] or bank!=provenance['metadata_bank']:raise RuntimeError('Resident provenance generation/bank mismatch')
            owner=ResidentOwner(session,abi['descriptor']['fields'],out,generation,bank,args.poll_s);owner.resident()
            pair=0;command=args.command_base
            def run_pair(tag):
                nonlocal pair,command
                if owner.command_count+2>args.max_commands:raise RuntimeError('Bounded command budget reached')
                owner.bind(args.epoch_base+pair)
                for cohort in (0,1):
                    record=owner.execute(command,args.request_id,cohort,pair+1,inputs['input_rec576'],inputs['gold_gu_s24'],tag)
                    receipt['commands'].append(record);command+=1
                owner.release();pair+=1
            marker('warmup_begin')
            for unused in range(args.warmup//2):run_pair('warmup')
            marker('idle_before_begin')
            if args.idle_before:time.sleep(args.idle_before)
            marker('load_begin');start=time.perf_counter();measured=0
            while measured<args.measured or time.perf_counter()-start<args.load_seconds:
                run_pair('measured');measured+=2
            marker('load_end')
            marker('idle_after_begin')
            if args.idle_after:time.sleep(args.idle_after)
            marker('idle_after_end')
            save(out/'csr_after.json',owner.snapshot())
            if owner.lease is not None or owner.pending is not None:raise RuntimeError('Final owner lease was not released')
            if hasattr(owner,'last_output_artifact'):receipt['last_output_artifact']=owner.last_output_artifact
            receipt.update(execution_state='completed',verdict='PASS',measured_commands=measured,retained_lease=owner.lease,retained_pending=owner.pending)
    except BaseException as error:
        receipt.update(execution_state='failed',verdict='FAIL',error=type(error).__name__+': '+str(error),traceback=traceback.format_exc(),retained_lease=owner.lease if owner else None,retained_pending=owner.pending if owner else None)
        if owner:
            try:save(out/'csr_failure.json',owner.snapshot())
            except Exception as secondary:receipt['snapshot_error']=str(secondary)
        raise
    finally:
        if owner:owner.stream.close()
        receipt['ended_utc']=utc();receipt['host_monotonic_ended_s']=time.perf_counter();save(out/'receipt.json',receipt)
    print(json.dumps({'verdict':receipt['verdict'],'measured_commands':receipt['measured_commands'],'result':str(out)}))


if __name__=='__main__':main()
