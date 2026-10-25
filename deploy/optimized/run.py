"""Actual software-only resident replay; no GPU, reset, or hardware fallback."""
import argparse
import concurrent.futures as futures
import dataclasses
import datetime as dt
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import numpy as np
from evidence import Evidence,named,utc
from host_math import HostAssets,actual_requests,stream_logits,file_sha,CHECKPOINT_SHA
from resource_guard import ResourceGuard
from device_health import system_identity,control_snapshot,csr_snapshots
from scalellm_windows_xdma import WindowsXdmaSession
from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
from host.scalellm_mlp_gu_only_runtime import GuDescriptor
from host.scalellm_mlp_gu_only import prepare_down_arrays
from host.scalellm_hostops import rms_norm,pack_s24_q16,unpack_s24_q16
from host.scalellm_mlp_linear import prepare_gate_up_input_from_normalized_fp32
from .backends import ResidentAttention,ResidentGu
from .down import DownMemo
from .session import MeasuredSession
from .store import ResidentStore,prepare_layer
from .verification import GoldCatalog,DeferredCatalog
from .layout import static_spans

BIT_SHA='66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47'


def next_metadata_layer(layer,layers):return layer+1 if layer+1<layers else None


def requests_for_config(assets,config):
    prompts=config.get('prompts',('Hi','Hello'));count=config.get('max_new_tokens',2)
    if len(prompts)!=2 or not all(isinstance(p,str) and p for p in prompts) or type(count)is not int or count not in (1,2):raise ValueError('Two prompts and1..2 new tokens required')
    return actual_requests(assets,tuple(prompts),count)


def catalog_for(mode,index,artifacts,assets,baseline_root):
    if mode=='deferred':return DeferredCatalog()
    if mode!='audited_baseline' or not baseline_root:raise ValueError('Explicit audited_baseline requires its independent baseline root')
    return GoldCatalog(index,artifacts,assets,BIT_SHA,baseline_root)


def array_record(e,path,values,dtype):
    a=np.ascontiguousarray(values,dtype=dtype);r=e.write_bytes(path,a.tobytes());r.update(dtype=dtype,shape=list(a.shape));return r


class Run:
    def __init__(self,s,raw,assets,artifacts,e,catalog,guard,summary,pool,mode,pilot_layers=2):
        self.s,self.raw,self.assets,self.artifacts,self.e,self.catalog,self.guard,self.summary,self.pool,self.mode=s,raw,assets,artifacts,e,catalog,guard,summary,pool,mode
        self.failed=None;self.cpu_lock=threading.RLock();self.host_leases={};self.memo=DownMemo();self.layers=pilot_layers if mode=='pilot' else 32
        bindings={'identity':json.loads(json.dumps(summary['identity'])),'layout_sha256':file_sha(e.root/'address_layout.json')}
        self.store=ResidentStore(s,artifacts,e,self.check,bindings)
        self.a=ResidentAttention(s,artifacts,self.store,e,catalog,self.check)
        self.gu=ResidentGu(s,artifacts,self.store,e,catalog,self.check)
        self.gu.metadata_sequence=s.read32(0x144)
        self.identifier=max([int(time.time())&0x3fffffff]+[s.read32(a) for a in (0x010,0x070,0x118,0x280,0x318,0x368)])+0x1000
        if self.identifier>0xffffe000:raise ValueError('Fresh U32 identity space exhausted')
        self.down_events=[];self.boundary_events=[];self.prepared=None
    def next_id(self):self.identifier+=1;return self.identifier
    def check(self):
        with self.cpu_lock:
            if self.failed:raise RuntimeError('Central owner poisoned: '+self.failed)
        if getattr(self,'a',None) is not None and self.a.failed:raise RuntimeError('Attention owner poisoned: '+self.a.failed)
        if getattr(self,'gu',None) is not None and self.gu.poisoned:raise RuntimeError('GU owner poisoned: '+self.gu.poisoned)
        self.guard()
    def submit(self,fn,*args):
        self.check();future=self.pool.submit(fn,*args)
        def complete(f):
            try:error=f.exception()
            except BaseException as caught:error=caught
            if error is not None:
                with self.cpu_lock:
                    if self.failed is None:self.failed=repr(error)
        future.add_done_callback(complete);return future
    def owner_state(self):return {'attention_pending':None if self.a.pending is None else self.a.pending['record'],'gu_pending':None if self.gu.pending is None else dataclasses.asdict(self.gu.pending),'fpga_lease':self.gu.lease,'host_leases':list(self.host_leases),'metadata_loading':self.gu.loading,'metadata_events':self.gu.metadata_events,'failed':self.failed or self.a.failed or self.gu.poisoned}
    def save(self):
        self.summary['resources'].update(self.guard.summary());self.e.replace_json('run_summary.json',self.summary)
    def record_hidden(self,cr,name,path,value):
        cr[name]=array_record(self.e,path,value,'<f4')
    def input_a(self,h,layer):return pack_s24_q16(rms_norm(h,self.assets.weights.input_layernorm[layer],1e-5))
    def after_a(self,h,actual,layer):
        residual=np.add(h,unpack_s24_q16(actual),dtype=np.float32)
        gu_input=prepare_gate_up_input_from_normalized_fp32(rms_norm(residual,self.assets.weights.post_attention_layernorm[layer],1e-5))
        return residual,gu_input
    def down_work(self,step,layer,cohort,payload,context,initial_length):
        start=time.perf_counter();q,m=prepare_down_arrays(payload)
        out,audit=self.memo.compute(layer,cohort,payload,q,m,context,range(initial_length) if step else())
        return out,dict(audit,started_monotonic_s=start,finished_monotonic_s=time.perf_counter(),step=step,layer=layer,cohort=cohort)
    def consume_down(self,future,step,layer,cohort,base,cr,residual,context):
        out,audit=future.result();self.check()
        record=named(self.e.write_bytes(base+'/down_s32.bin',np.asarray(out,dtype='<i4').tobytes()),'output')
        if self.catalog.mode=='audited_baseline' and record['output_sha256']!=self.catalog.records[(step,layer,cohort)]['down']['output_sha256']:raise AssertionError('Optimized integer Down differs from audited baseline')
        ar=self.e.write_json(base+'/down_audit.json',audit);record.update(dtype='<i4',shape=[16,4096],comparison='PASS' if self.catalog.mode=='audited_baseline' else 'NUMERICAL_VERIFICATION_PENDING',weights_sha256={n:self.artifacts.original.layer_artifact(layer,n).sha256 for n in ('mlp_down_c0','mlp_down_c1','mlp_down_meta')},down_audit_path=ar['path']);cr['down']=record
        h=np.add(residual,np.asarray(out,dtype=np.float32)/np.float32(65536),dtype=np.float32)
        if not np.all(np.isfinite(h)):raise ValueError('Nonfinite actual hidden')
        self.record_hidden(cr,'hidden_after',base+'/hidden_after.f32.bin',h)
        self.down_events.append(audit);del self.host_leases[(layer,cohort)]
        self.summary['counts']['host_down_tasks']+=1;return h
    def forward(self,step_index,requests,tokenizer):
        batch=self.next_id();hidden=[];states=[]
        for cohort,r in enumerate(requests):
            ids=r['initial_token_ids']+r['generated_ids'];pad=ids+[r['padding_token_id']]*(16-len(ids))
            if not 0<len(ids)<=16:raise ValueError('Prefix exceeds fixed16')
            hidden.append(self.assets.embed(pad));states.append({'external_request_id':r['external_request_id'],'cohort':cohort,'prefix_token_ids':ids,'prefix_length':len(ids),'padded_token_ids':pad,'companion_only':r['stop_reason'] is not None,'last_valid_row':len(ids)-1})
        step={'step':step_index,'hardware_batch_request_id':batch,'request_states':states,'layers':[],'counts':dict(attention_commands=0,gu_commands=0,host_down_tasks=0,epoch_releases=0)};self.summary['steps'].append(step);self.save()
        prepared_future=self.submit(prepare_layer,self.artifacts,0,self.guard);next_a_started=False
        for layer in range(self.layers):
            self.check();prepared=prepared_future.result();self.check()
            if prepared['layer']!=layer:raise RuntimeError('Wrong prepared layer')
            prepared_future=self.submit(prepare_layer,self.artifacts,layer+1,self.guard) if layer+1<self.layers else None
            epoch=self.next_id();lr={'layer':layer,'epoch_id':epoch,'gu_metadata_generation':None,'epoch_released':False,'cohorts':[]};step['layers'].append(lr)
            bases=['step_%03d/layer_%02d/cohort_%d'%(step_index,layer,c) for c in (0,1)];crs=[]
            for c in (0,1):
                cr={'cohort':c};lr['cohorts'].append(cr);crs.append(cr);self.record_hidden(cr,'hidden_before',bases[c]+'/hidden_before.f32.bin',hidden[c])
            if not next_a_started:self.a.start(step_index,layer,0,self.input_a(hidden[0],layer),self.next_id(),batch,bases[0]+'/attention')
            next_a_started=False
            # A0 can run while canonical GU weights are copied and read back.
            generation=self.gu.stage_gu_layer(layer,epoch,prepared);lr['gu_metadata_generation']=generation
            output,a_record=self.a.collect();crs[0]['attention']=a_record;self.summary['counts']['attention_commands']+=1
            residual0,gu_input0=self.after_a(hidden[0],output,layer);self.record_hidden(crs[0],'after_attention_residual',bases[0]+'/after_attention_residual.f32.bin',residual0)
            input1=self.input_a(hidden[1],layer);a1command=self.next_id()
            # All GU0 Host math and descriptor preparation precedes A1 START.
            # This hook starts A1 just before the already-prepared GU0 START.
            self.gu.before_start_callback=lambda:self.a.start(step_index,layer,1,input1,a1command,batch,bases[1]+'/attention')
            descriptor0=GuDescriptor(self.next_id(),batch,0,layer,layer%3,self.next_id(),generation,epoch)
            gu0,gr0=self.gu.run_verified(step_index,descriptor0,gu_input0,bases[0]+'/gu');crs[0]['gu']=gr0;self.summary['counts']['gu_commands']+=1
            self.host_leases[(layer,0)]={'epoch':epoch,'gu_output_sha256':sha(gu0),'weights':prepared['down_context'].source}
            down0=self.submit(self.down_work,step_index,layer,0,gu0,prepared['down_context'],len(requests[0]['initial_token_ids']))
            output,a_record=self.a.collect();crs[1]['attention']=a_record;self.summary['counts']['attention_commands']+=1
            residual1,gu_input1=self.after_a(hidden[1],output,layer);self.record_hidden(crs[1],'after_attention_residual',bases[1]+'/after_attention_residual.f32.bin',residual1)
            # Do not leave an uncommitted LOAD across LM-head/EOS decisions.
            next_meta=next_metadata_layer(layer,self.layers)
            descriptor1=GuDescriptor(self.next_id(),batch,1,layer,3+layer%3,self.next_id(),generation,epoch)
            gu1,gr1=self.gu.run_verified(step_index,descriptor1,gu_input1,bases[1]+'/gu');crs[1]['gu']=gr1;self.summary['counts']['gu_commands']+=1
            self.host_leases[(layer,1)]={'epoch':epoch,'gu_output_sha256':sha(gu1),'weights':prepared['down_context'].source}
            down1=self.submit(self.down_work,step_index,layer,1,gu1,prepared['down_context'],len(requests[1]['initial_token_ids']))
            # Never overlap GU tensor execution and metadata DMA after the
            # observed WATCHDOG. Both outputs are already copied and ACKed;
            # this LOAD may overlap only the immutable CPU Down consumers.
            if next_meta is not None:self.gu.prefetch_after_pair(next_meta)
            hidden[0]=self.consume_down(down0,step_index,layer,0,bases[0],crs[0],residual0,prepared['down_context'])
            # A(L+1,0) depends only on its own completed Down0/residual. GU
            # weights/epoch remain leased until Down1 consumer also retires.
            if layer+1<self.layers:
                self.a.start(step_index,layer+1,0,self.input_a(hidden[0],layer+1),self.next_id(),batch,'step_%03d/layer_%02d/cohort_0/attention'%(step_index,layer+1));next_a_started=True
            hidden[1]=self.consume_down(down1,step_index,layer,1,bases[1],crs[1],residual1,prepared['down_context'])
            if self.host_leases:raise RuntimeError('Old Host consumers still own layer')
            self.gu.release_gu_layer(layer,epoch);lr['epoch_released']=True;self.summary['counts']['epoch_releases']+=1
            step['counts']={k:(layer+1)*(2 if k!='epoch_releases' else 1) for k in step['counts']};self.save();self.s.save()
            self.e.replace_json('schedule_timeline.json',{'attention':self.a.timeline,'gu':self.gu.timeline,'metadata':self.gu.metadata_events,'host_down':self.down_events})
            print(json.dumps({'event':'layer_complete','step':step_index,'layer':layer,'counts':self.summary['counts']}),flush=True)
            del prepared;gc.collect();self.check()
        if self.mode=='pilot':return
        for c,r in enumerate(requests):
            state=states[c];final=self.assets.final_normalized(hidden[c]);base='step_%03d/cohort_%d'%(step_index,c)
            state.update(named(array_record(self.e,base+'/final_hidden.f32.bin',hidden[c],'<f4'),'final_hidden'));state.update(named(array_record(self.e,base+'/final_normalized.f32.bin',final,'<f4'),'final_normalized'))
            logits,token=stream_logits(final,state['last_valid_row'],self.assets.lm_head,2048);state.update(named(array_record(self.e,base+'/logits.f32.bin',logits,'<f4'),'logits'));state.update(argmax_token_id=token,eos=token in r['eos_token_ids'],lm_head_chunk_rows=2048,decoded_new_text=tokenizer.decode([token],skip_special_tokens=False))
            if not state['companion_only']:
                r['generated_ids'].append(token);r['decoded_generated_text']=tokenizer.decode(r['generated_ids'],skip_special_tokens=False)
                if state['eos']:r['stop_reason']='eos'
                elif len(r['generated_ids'])>=r['max_new_tokens']:r['stop_reason']='max_new_tokens'
                elif len(state['prefix_token_ids'])+1>=16:r['stop_reason']='context_limit'
            self.save()


def sha(data):return hashlib.sha256(data).hexdigest()


def main(argv=None,config=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifacts',required=True);p.add_argument('--assets',required=True);p.add_argument('--result',required=True);p.add_argument('--validation-mode',choices=('audited_baseline','deferred'),default='deferred');p.add_argument('--baseline-root');p.add_argument('--baseline-index',default=str(Path(__file__).with_name('baseline_index.json')));p.add_argument('--mode',choices=('pilot','full'),default='full');p.add_argument('--pilot-layers',type=int,choices=(1,2),default=2);a=p.parse_args(argv)
    if a.validation_mode=='audited_baseline' and not a.baseline_root:p.error('audited_baseline requires --baseline-root; no fallback')
    if os.name!='nt':raise RuntimeError('Actual local Windows CPU+FPGA only')
    if any(os.environ.get(k)!='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')):raise ValueError('Single-thread BLAS/OMP required')
    import ctypes
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p;k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(k.GetCurrentProcess(),0xff):raise ctypes.WinError(ctypes.get_last_error())
    e=Evidence(a.result);guard=ResourceGuard();guard();initial=system_identity();startup=time.perf_counter()
    assets=HostAssets(a.assets,verify=True);artifacts=GuOnlyArtifactManifest.load(a.artifacts,verify_hashes=True)
    if artifacts.original.checkpoint_sha256!=CHECKPOINT_SHA or assets.manifest['checkpoint_sha256']!=CHECKPOINT_SHA:raise ValueError('Checkpoint source mismatch')
    cfg=config or {};tokenizer,requests=requests_for_config(assets,cfg)
    catalog=catalog_for(a.validation_mode,a.baseline_index,artifacts,assets,a.baseline_root)
    sources={str(p):file_sha(p) for p in Path(__file__).parent.glob('*.py')}
    for name in ('scalellm.py','device_health.py'):sources[str(Path(__file__).parents[1]/name)]=file_sha(Path(__file__).parents[1]/name)
    if a.validation_mode=='audited_baseline':sources[str(Path(a.baseline_index).resolve())]=file_sha(a.baseline_index)
    summary={'schema':'scalellm_llama_host_fpga_run_v1','software_mode':'resident_interleaved_post_ack_metadata_v2','validation_mode':a.validation_mode,'mode':a.mode,'pilot_layers':a.pilot_layers if a.mode=='pilot' else None,'started_utc':utc(),'execution_state':'running','verdict':'NUMERICAL_VERIFICATION_PENDING','topology':{'host_model_cpu':'Local Windows CPU','device':'VCU118 local XDMA','gpu_used':False,'cpu_workers':2,'io_owners':1,'attention_and_gu':'actual FPGA, independently pending','gu_metadata_prefetch':'only after both cohort outputs copied and ACKed; overlaps CPU Down only','input_ddr_readback':'NOT_PERFORMED; full Host inputs and exact H2C counts saved','down_norm_lmhead_tokenizer':'CPU exact original mathematics'},'resources':dict(guard.summary(),cpu_affinity=list(range(8))),'identity':{'checkpoint_sha256':CHECKPOINT_SHA,'artifact_manifest_sha256':file_sha(a.artifacts),'host_assets_manifest_sha256':file_sha(a.assets),'source_sha256':sources,'vendor_manifest_sha256':file_sha(Path(__file__).parents[1]/'vendor_manifest.json'),'bit_sha256':BIT_SHA,'driver_before':initial['driver'],'boot_before':initial['boot_utc'],'baseline_index_sha256':file_sha(a.baseline_index) if a.validation_mode=='audited_baseline' else None},'requests':requests,'steps':[],'counts':dict(attention_commands=0,gu_commands=0,host_down_tasks=0,epoch_releases=0),'first_error':None,'final':{},'timing':{'startup_including_source_sha_begin_s':startup}}
    config_record=e.write_json('deployment_config.json',config or {});summary['identity']['deployment_config_sha256']=config_record['sha256']
    if cfg.get('prior_recovery'):summary['identity']['prior_recovery']=cfg['prior_recovery']
    e.write_json('identity_before.json',initial);e.write_json('address_layout.json',[dataclasses.asdict(x) for x in static_spans()]);e.replace_json('run_summary.json',summary)
    class SnapshotSession(WindowsXdmaSession):
        def __exit__(self,kind,error,tb):
            if kind is not None and not self.poisoned:
                try:e.write_json('failure_readonly_snapshots.json',{'attention':{hex(x):self.read32(x) for x in (0xc,0x4c,0x78,0x7c,0x80,0x84,0x88)},'gu':{hex(x):self.read32(x) for x in (0x324,0x338,0x33c,0x350,0x368,0x370,0x178,0x14c)}})
                except BaseException:pass
            return super().__exit__(kind,error,tb)
    raw=SnapshotSession(timeout_ms=5000);run=None;s=None
    try:
        with raw,futures.ThreadPoolExecutor(max_workers=2,thread_name_prefix='exact_cpu') as pool:
            s=MeasuredSession(raw,e);e.write_json('control_before.json',control_snapshot(raw));att,gu=csr_snapshots(s);e.write_json('attention_before.json',att);e.write_json('gu_before.json',gu)
            run=Run(s,raw,assets,artifacts,e,catalog,guard,summary,pool,a.mode,a.pilot_layers);run.gu.initialize_shared_mode();summary['startup_residency']=run.store.load();summary['timing']['startup_finished_s']=time.perf_counter()
            s.phase='inference';summary['timing']['inference_begin_s']=time.perf_counter();summary['timing']['inference_begin_utc']=utc()
            for step in range(1 if a.mode=='pilot' else 2):
                if a.mode=='full' and all(r['stop_reason'] is not None for r in requests):break
                run.forward(step,requests,tokenizer)
            run.check()
            if run.a.pending or run.gu.pending or run.gu.lease or run.host_leases or run.gu.loading:raise RuntimeError('Owner did not fully retire')
            summary['timing']['inference_finished_s']=time.perf_counter();summary['timing']['inference_finished_utc']=utc();s.phase='final_readonly'
            att,gu=csr_snapshots(s);summary['final']={'attention_csr_path':e.write_json('attention_final.json',att)['path'],'gu_csr_path':e.write_json('gu_final.json',gu)['path'],'control_irq_path':e.write_json('control_final.json',control_snapshot(raw))['path'],'pending':None,'fpga_lease':None,'host_leases':[],'handles_closed':False,'owned_processes_exited':False};s.save()
        summary['final'].update(handles_closed=not raw.handles,owned_processes_exited=True)
        after=system_identity();e.write_json('identity_after.json',after);summary['identity'].update(driver_after=after['driver'],boot_after=after['boot_utc'])
        if after!=initial:raise RuntimeError('Driver/boot identity changed')
        expected=summary['counts']['attention_commands']+summary['counts']['gu_commands']
        if len(catalog.used)!=expected:raise RuntimeError('Output verification/record coverage differs')
        if catalog.mode=='audited_baseline':
            summary.update(execution_state='executed',verdict='HASH_VALIDATED_AWAITING_BYTEWISE_AUDIT');e.replace_json('run_summary.json',summary)
            audit=catalog.verify_bytes(e.root);e.write_json('offline_full_gold_audit.json',audit)
            if audit['full_output_count']!=expected:raise RuntimeError('Offline full output coverage differs')
            summary.update(execution_state='completed',verdict='PASS',finished_utc=utc());summary['timing']['offline_bytewise_audit_seconds']=audit['seconds']
        else:
            e.write_json('deferred_numerical_audit_required.json',{'verdict':'NUMERICAL_VERIFICATION_PENDING','full_output_count':len(catalog.used),'records':catalog.used,'next_action':'Run offline-audit in the same CPU/NumPy/BLAS environment; original summary remains immutable'})
            summary.update(execution_state='EXECUTION_COMPLETE',verdict='NUMERICAL_VERIFICATION_PENDING',finished_utc=utc())
    except BaseException as error:
        if run:
            with run.cpu_lock:run.failed=repr(error)
        summary.update(execution_state='failed',verdict='FAIL',first_error={'utc':utc(),'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc(),'owner':None if run is None else run.owner_state()})
        e.journal('run.failed',summary['first_error']);raise
    finally:
        summary['resources'].update(guard.summary());summary['final']['handles_closed']=not raw.handles;e.replace_json('run_summary.json',summary)
    print(json.dumps({'event':'run_complete','verdict':summary['verdict'],'counts':summary['counts'],'requests':requests}),flush=True)


if __name__=='__main__':main()
