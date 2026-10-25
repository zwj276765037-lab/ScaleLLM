"""Real Dell CPU + FPGA Llama inference, bounded16-row prefix recomputation.

Serial owner, frozen production GU backend, exact gold before hardware ACK.
No fallback, reset, reprogram, retry or CPU substitution for either FPGA engine.
"""
import argparse
import dataclasses
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

import numpy as np
from attention_backend import AttentionBackend
from device_health import system_identity, control_snapshot, csr_snapshots
from evidence import Evidence, named, utc
from gu_backend import VerifiedGuBackend
from host_math import HostAssets, actual_requests, stream_logits, CHECKPOINT_SHA, file_sha
from resource_guard import ResourceGuard
from reference import ReferenceLayer
from native_trace_wrapper_boundary import TraceWriter, TracedSession
from scalellm_windows_xdma import WindowsXdmaSession
from host.scalellm_hostops import rms_norm, pack_s24_q16, unpack_s24_q16
from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
from host.scalellm_mlp_gu_only_runtime import GuDescriptor
from host.scalellm_mlp_linear import prepare_gate_up_input_from_normalized_fp32
from host.scalellm_mlp_gu_only import prepare_down_arrays, down_blocked_int64, down_scalar_oracle

BIT_SHA='66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47'


class CombinedOwner:
    def __init__(self,gu,attention):self.gu=gu;self.attention=attention;self.host_leases={};self.error=None
    @property
    def lease(self):return {'gu':self.gu.lease,'host':list(self.host_leases)} if self.gu.lease or self.host_leases else None
    @property
    def pending(self):return {'gu':dataclasses.asdict(self.gu.pending) if self.gu.pending else None,'attention':self.attention.pending} if self.gu.pending or self.attention.pending else None
    @property
    def copied(self):return self.gu.output_copied or self.attention.copied
    @property
    def acked(self):return self.gu.acked_cohorts
    @property
    def failed(self):return self.error or self.gu.poisoned or self.attention.failed
    @property
    def command_count(self):return self.gu.completed_commands+self.attention.command_count


def source_identity():
    import reference,core
    import host.scalellm_mlp_gu_only_backend as backend
    import host.scalellm_mlp_gu_only as down
    import host.scalellm_mlp_linear as linear
    import host.scalellm_hostops as ops
    import scalellm_windows_xdma as transport
    import native_trace_wrapper_boundary as tracing
    files=[Path(__file__),Path(__file__).with_name('attention_backend.py'),Path(__file__).with_name('gu_backend.py'),Path(__file__).with_name('evidence.py'),Path(__file__).with_name('resource_guard.py'),Path(__file__).with_name('device_health.py'),Path(__file__).with_name('host_math.py'),Path(reference.__file__),Path(core.__file__),Path(backend.__file__),Path(down.__file__),Path(linear.__file__),Path(ops.__file__),Path(transport.__file__),Path(tracing.__file__)]
    return {str(p):file_sha(p) for p in files}


def array_record(evidence,path,array,dtype):
    a=np.ascontiguousarray(array,dtype=dtype)
    record=evidence.write_bytes(path,a.tobytes());record.update(dtype=dtype,shape=list(a.shape));return record


class Inference:
    def __init__(self,session,raw,assets,artifacts,evidence,trace,guard,summary,mode):
        self.session=session;self.raw=raw;self.assets=assets;self.artifacts=artifacts;self.evidence=evidence;self.trace=trace;self.guard=guard;self.summary=summary
        self.cached_layer=None;self.reference=None;self.mode=mode
        self.attention=AttentionBackend(session,artifacts,self.reference_for_layer,evidence,trace,guard)
        self.gu=VerifiedGuBackend(session,artifacts,evidence=evidence,reference_for_layer=self.reference_for_layer,resource_guard=guard,poll_interval_s=.001,chunk_bytes=1<<20)
        self.owner=CombinedOwner(self.gu,self.attention);trace.owner=self.owner
        self.gu.metadata_sequence=session.read32(0x144)
        seed=0x510000 if mode=='pilot' else 0x610000
        self.command=seed;self.attention_command=seed+0x10000;self.epoch=seed+0x20000;self.batch=seed+0x30000
        self.buffer_generations=[seed]*6
        self.layers=1 if mode=='pilot' else 32
    def reference_for_layer(self,layer):
        if self.cached_layer!=layer:
            self.reference=None;gc.collect();self.guard()
            mapping=self.artifacts.original.layers[layer].artifacts
            self.reference=ReferenceLayer({name:record.path for name,record in mapping.items()});self.cached_layer=layer
            self.guard()
        return self.reference
    def save(self):
        self.summary['resources'].update(self.guard.summary())
        self.evidence.replace_json('run_summary.json',self.summary)
    def tracecall(self,operation,details,fn):return self.trace.call('owner.'+operation,details,fn)
    def forward(self,step_index,requests):
        self.batch+=1
        states=[];hidden=[]
        for c,r in enumerate(requests):
            ids=r['initial_token_ids']+r['generated_ids'];pad=ids+[r['padding_token_id']]*(16-len(ids))
            if not 0<len(ids)<=16:raise ValueError('Prefix length invalid')
            state={'external_request_id':r['external_request_id'],'cohort':c,'prefix_token_ids':ids,'prefix_length':len(ids),'padded_token_ids':pad,'companion_only':r['stop_reason'] is not None,'last_valid_row':len(ids)-1}
            states.append(state);hidden.append(self.assets.embed(pad))
        step={'step':step_index,'hardware_batch_request_id':self.batch,'request_states':states,'layers':[],'counts':dict(attention_commands=0,gu_commands=0,host_down_tasks=0,epoch_releases=0)}
        self.summary['steps'].append(step);self.save()
        for layer in range(self.layers):
            self.guard();self.evidence.journal('layer.begin',{'step':step_index,'layer':layer})
            self.reference_for_layer(layer)
            weights=self.artifacts.down_weights(layer)
            self.guard();self.epoch+=1
            lr={'layer':layer,'epoch_id':self.epoch,'gu_metadata_generation':None,'epoch_released':False,'cohorts':[]};step['layers'].append(lr);self.save()
            generation=self.tracecall('gu_stage',{'layer':layer,'epoch':self.epoch},lambda:self.gu.stage_gu_layer(layer,self.epoch));lr['gu_metadata_generation']=generation;self.save()
            for cohort in (0,1):
                self.guard()
                base='step_%03d/layer_%02d/cohort_%d'%(step_index,layer,cohort)
                cr={'cohort':cohort};lr['cohorts'].append(cr)
                cr['hidden_before']=array_record(self.evidence,base+'/hidden_before.f32.bin',hidden[cohort],'<f4');self.save()
                normalized=rms_norm(hidden[cohort],self.assets.weights.input_layernorm[layer],1e-5)
                self.attention_command+=1
                actual,record=self.tracecall('attention',{'layer':layer,'cohort':cohort,'command':self.attention_command},lambda:self.attention.run(cohort,layer,pack_s24_q16(normalized),self.attention_command,self.batch,base+'/attention'))
                cr['attention']=record;step['counts']['attention_commands']+=1;self.summary['counts']['attention_commands']+=1
                residual=np.add(hidden[cohort],unpack_s24_q16(actual),dtype=np.float32)
                cr['after_attention_residual']=array_record(self.evidence,base+'/after_attention_residual.f32.bin',residual,'<f4')
                normalized=rms_norm(residual,self.assets.weights.post_attention_layernorm[layer],1e-5)
                gu_input=prepare_gate_up_input_from_normalized_fp32(normalized)
                buffer=cohort*3+layer%3;self.buffer_generations[buffer]+=1;self.command+=1
                desc=GuDescriptor(self.command,self.batch,cohort,layer,buffer,self.buffer_generations[buffer],generation,self.epoch)
                self.gu.job_dir=base+'/gu';self.save()
                result=self.tracecall('gu',{'layer':layer,'cohort':cohort,'command':self.command},lambda:self.gu.run_gu(desc,gu_input))
                cr['gu']=self.gu.current_record;step['counts']['gu_commands']+=1;self.summary['counts']['gu_commands']+=1
                key='%d:%d'%(layer,cohort);self.owner.host_leases[key]={'layer':layer,'cohort':cohort,'output_sha256':hashlib.sha256(result.payload).hexdigest()}
                self.tracecall('gu_ack',{'command':self.command},lambda:self.gu.ack_gu(self.command));self.save()
                if not self.gu.quiescent():raise RuntimeError('GU not drained after ACK')
                self.guard();started=time.perf_counter()
                q,meta=prepare_down_arrays(result.payload)
                down=down_blocked_int64(q,meta,weights)
                rows=tuple(sorted(set((0,states[cohort]['last_valid_row'],15))));cols=(0,1,15,16,4095)
                scalar=down_scalar_oracle(q,meta,weights,rows=rows,columns=cols)
                passed=np.array_equal(down[np.ix_(rows,cols)],scalar)
                sc=self.evidence.write_json(base+'/down_scalar.json',{'rows':rows,'columns':cols,'expected':scalar.tolist(),'actual':down[np.ix_(rows,cols)].tolist(),'comparison':'PASS' if passed else 'FAIL','seconds':time.perf_counter()-started})
                dr=named(self.evidence.write_bytes(base+'/down_s32.bin',np.asarray(down,dtype='<i4').tobytes()),'output')
                dr.update(weights_sha256={name:self.artifacts.original.layer_artifact(layer,name).sha256 for name in ('mlp_down_c0','mlp_down_c1','mlp_down_meta')},scalar_check_path=sc['path'],comparison='PASS' if passed else 'FAIL',dtype='<i4',shape=[16,4096]);dr.update(s32_saturation_count=int(np.count_nonzero((down==-2147483648)|(down==2147483647))),minimum=int(down.min()),maximum=int(down.max()));cr['down']=dr;self.save()
                if not passed:raise AssertionError('HostDown blocked/scalar mismatch; retained Host lease')
                hidden[cohort]=np.add(residual,np.asarray(down,dtype=np.float32)/np.float32(65536),dtype=np.float32)
                if not np.all(np.isfinite(hidden[cohort])):raise ValueError('Nonfinite actual hidden')
                cr['hidden_after']=array_record(self.evidence,base+'/hidden_after.f32.bin',hidden[cohort],'<f4')
                del self.owner.host_leases[key]
                step['counts']['host_down_tasks']+=1;self.summary['counts']['host_down_tasks']+=1;self.save()
                self.evidence.journal('cohort.layer_complete',{'step':step_index,'layer':layer,'cohort':cohort,'attention_command':self.attention_command,'gu_command':self.command,'hidden_sha256':cr['hidden_after']['sha256']})
            self.tracecall('gu_release',{'layer':layer,'epoch':self.epoch},lambda:self.gu.release_gu_layer(layer,self.epoch))
            lr['epoch_released']=True;step['counts']['epoch_releases']+=1;self.summary['counts']['epoch_releases']+=1
            self.evidence.journal('layer.complete',{'step':step_index,'layer':layer,'counts':step['counts']});self.save()
            print(json.dumps({'event':'layer_complete','step':step_index,'layer':layer,'counts':step['counts']}),flush=True)
            del weights;gc.collect();self.guard()
        if self.mode=='pilot':return
        for cohort,r in enumerate(requests):
            self.guard();state=states[cohort]
            final=self.assets.final_normalized(hidden[cohort]);base='step_%03d/cohort_%d'%(step_index,cohort)
            fr=array_record(self.evidence,base+'/final_normalized.f32.bin',final,'<f4');state.update(named(fr,'final_normalized'))
            state.update(named(step['layers'][-1]['cohorts'][cohort]['hidden_after'],'final_hidden'))
            logits,token=stream_logits(final,state['last_valid_row'],self.assets.lm_head,2048)
            state.update(named(array_record(self.evidence,base+'/logits.f32.bin',logits,'<f4'),'logits'))
            state.update(argmax_token_id=token,eos=token in r['eos_token_ids'],lm_head_chunk_rows=2048)
            state['decoded_new_text']=self.tokenizer.decode([token],skip_special_tokens=False)
            if not state['companion_only']:
                r['generated_ids'].append(token);r['decoded_generated_text']=self.tokenizer.decode(r['generated_ids'],skip_special_tokens=False)
                if state['eos']:r['stop_reason']='eos'
                elif len(r['generated_ids'])>=r['max_new_tokens']:r['stop_reason']='max_new_tokens'
                elif state['prefix_length']+1>=16:r['stop_reason']='context_limit'
            self.evidence.journal('token.generated',{'step':step_index,'cohort':cohort,'prefix_token_ids':state['prefix_token_ids'],'token':token,'text':state['decoded_new_text'],'companion':state['companion_only']});self.save()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifacts',required=True);p.add_argument('--assets',required=True);p.add_argument('--result',required=True);p.add_argument('--mode',choices=('pilot','full'),required=True);a=p.parse_args()
    if os.name!='nt':raise RuntimeError('This entrypoint is Dell Windows CPU+FPGA only')
    thread_environment={key:os.environ.get(key) for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}
    if any(value!='1' for value in thread_environment.values()):raise RuntimeError('Explicit single-thread BLAS/OMP environment required: '+repr(thread_environment))
    import ctypes
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetCurrentProcess.restype=ctypes.c_void_p;k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not k.SetProcessAffinityMask(k.GetCurrentProcess(),0xff):raise ctypes.WinError(ctypes.get_last_error())
    evidence=Evidence(a.result);trace=TraceWriter(str(Path(a.result))+'.driver_calls.jsonl');guard=ResourceGuard();guard()
    before=system_identity();assets=HostAssets(a.assets,verify=True);artifacts=GuOnlyArtifactManifest.load(a.artifacts,verify_hashes=True)
    if artifacts.original.checkpoint_sha256!=CHECKPOINT_SHA or assets.manifest['checkpoint_sha256']!=CHECKPOINT_SHA:raise ValueError('Host/FPGA checkpoint identity differs')
    tokenizer,requests=actual_requests(assets)
    summary={'schema':'scalellm_llama_host_fpga_run_v1','mode':a.mode,'started_utc':utc(),'execution_state':'running','verdict':'NOT_COMPLETE','topology':{'host_model_cpu':'Dell Windows portable CPython','device':'VCU118 via local XDMA','gpu_used':False,'attention_and_gu':'FPGA actual outputs; CPU exact reference comparison only','down_norm_lmhead_tokenizer':'Dell CPU','python':sys.version,'numpy':np.__version__,'executable':sys.executable,'thread_environment':thread_environment},'resources':dict(guard.summary(),cpu_affinity=list(range(8))),'identity':{'checkpoint_sha256':CHECKPOINT_SHA,'artifact_manifest_sha256':file_sha(a.artifacts),'host_assets_manifest_sha256':file_sha(a.assets),'source_sha256':source_identity(),'bit_sha256':BIT_SHA,'driver_before':before['driver'],'boot_before':before['boot_utc']},'requests':requests,'steps':[],'counts':dict(attention_commands=0,gu_commands=0,host_down_tasks=0,epoch_releases=0),'first_error':None,'final':{}}
    evidence.replace_json('run_summary.json',summary);evidence.write_json('identity_before.json',before)
    raw=WindowsXdmaSession(timeout_ms=5000,log_path=None);session=TracedSession(raw,trace);runtime=None
    try:
        with session:
            evidence.write_json('control_before.json',control_snapshot(raw));att,gu=csr_snapshots(session);evidence.write_json('attention_before.json',att);evidence.write_json('gu_before.json',gu)
            runtime=Inference(session,raw,assets,artifacts,evidence,trace,guard,summary,a.mode);runtime.tokenizer=tokenizer
            for step in range(1 if a.mode=='pilot' else 2):
                if a.mode=='full' and all(r['stop_reason'] is not None for r in requests):break
                runtime.forward(step,requests)
            if runtime.owner.pending or runtime.owner.lease or runtime.owner.failed:raise RuntimeError('Owner not fully retired')
            att,gu=csr_snapshots(session)
            summary['final']={'attention_csr_path':evidence.write_json('attention_final.json',att)['path'],'gu_csr_path':evidence.write_json('gu_final.json',gu)['path'],'control_irq_path':evidence.write_json('control_final.json',control_snapshot(raw))['path'],'pending':None,'fpga_lease':None,'host_leases':[],'handles_closed':False,'owned_processes_exited':False}
        summary['final']['handles_closed']=not raw.handles
        # No child job or RPC bridge is launched by this in-process owner.
        summary['final']['owned_processes_exited']=True
        after=system_identity();evidence.write_json('identity_after.json',after)
        summary['identity'].update(driver_after=after['driver'],boot_after=after['boot_utc'])
        if after!=before:raise RuntimeError('Driver or boot identity changed')
        summary.update(execution_state='completed',verdict='PASS',finished_utc=utc())
    except BaseException as error:
        if runtime:runtime.owner.error=repr(error)
        summary.update(execution_state='failed',verdict='FAIL',first_error={'utc':utc(),'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc(),'owner':trace.owner_state()})
        evidence.journal('run.failed',summary['first_error']);raise
    finally:
        summary['resources'].update(guard.summary());summary['final']['handles_closed']=not raw.handles
        evidence.replace_json('run_summary.json',summary);trace.close()
    print(json.dumps({'event':'run_complete','mode':a.mode,'verdict':summary['verdict'],'counts':summary['counts'],'requests':requests}),flush=True)


if __name__=='__main__':main()
