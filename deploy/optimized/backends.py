"""Single-owner interleaved engines; one independent pending per engine."""
import dataclasses
import hashlib
import time
from attention_backend import AttentionBackend,SNAPSHOT
from host.scalellm_mlp_gu_only_backend import GuOnlyXdmaBackend
from .layout import attention_bases,layer_spans


def sha(data):return hashlib.sha256(data).hexdigest()


def global_guard(session):
    if session.read32(0x10c)&0x1f!=0x1b or session.read32(0x260)&0x1f!=3:raise RuntimeError('SHARED owner/switch/error/maintenance mismatch')
    gu_status=session.read32(0x324)
    # DONE error is a retained historical field after an ID ACK. It is a
    # current failure only while completion-valid is asserted.
    if gu_status&0x14 or (gu_status&2 and session.read32(0x350)) or session.read32(0x370) or session.read32(0x2a8):raise RuntimeError('GU reset/error/admission/maintenance fault')
    if session.read32(0x178)&0x18:raise RuntimeError('GU tensor/metadata DMA fault forbids new START')
    if session.read32(0x00c)&4 or session.read32(0x04c):raise RuntimeError('Attention error forbids any new engine START')


class ResidentAttention:
    def __init__(self,session,artifacts,store,evidence,catalog,check_cpu_failure):
        self.s,self.artifacts,self.store,self.evidence,self.catalog=session,artifacts,store,evidence,catalog
        self.check_cpu_failure=check_cpu_failure;self.pending=None;self.failed=None;self.layer=None;self.rope_loaded=False;self.timeline=[];self.seen_commands=set()
    def snapshot(self):return {'0x%03x'%a:self.s.read32(a) for a in SNAPSHOT}
    def guard(self):
        self.check_cpu_failure();global_guard(self.s)
        status=self.s.read32(0x00c)
        if status&0x27 or self.s.read32(0x04c):raise RuntimeError('Attention not ready; independent GU busy is allowed')
        if self.rope_loaded and status&0x18!=0x18:raise RuntimeError('Resident Attention metadata/RoPE lost')
    def start(self,step,layer,cohort,payload,command,request,job):
        try:return self._start(step,layer,cohort,payload,command,request,job)
        except BaseException as error:self.failed=repr(error);raise
    def _start(self,step,layer,cohort,payload,command,request,job):
        if self.pending is not None or self.failed:raise RuntimeError('Attention pending/poisoned')
        if any(type(v)is not int or not 0<v<2**32 for v in (command,request)) or command in self.seen_commands:raise ValueError('Attention requires fresh positive U32 command and request')
        self.store.require();self.guard();payload=bytes(payload)
        if len(payload)!=196608:raise ValueError('Full16row Attention input required')
        expected=self.catalog.expected(step,layer,cohort,'attention',payload);bases=attention_bases(layer,cohort)
        record={'command_id':command,'request_id':request,'cohort':cohort,'layer':layer,'buffer_id':bases['buffer'],'copied':False,'sticky_cleared':False,'comparison':'NOT_RUN','started':False,'input_base':bases['input'],'output_base':bases['output'],'weights_sha256':{n:self.artifacts.original.layer_artifact(layer,n).sha256 for n in ('attention_c0','attention_c1','attention_meta')},'rope_sha256':self.artifacts.original.rope.sha256,'resident':True,'query_start':0,'query_count':16,'valid_key_count':16,'preserve_historical_kv':False}
        record['input_readback']='NOT_PERFORMED; full Host input saved; exact H2C count; output follows explicit validation_mode'
        record['validation_mode']=self.catalog.mode
        stored=self.evidence.write_bytes(job+'/input_s24.bin',payload);record.update(input_path=stored['path'],input_sha256=stored['sha256'])
        if self.s.h2c_write_local(0,payload,bases['input'],1<<20)!=len(payload):raise IOError('Short Attention input H2C')
        config=((0x010,command),(0x014,layer),(0x018,0x00101000),(0x01c,0x48384103),(0x020,bases['input']),(0x024,bases['output']),(0x028,bases['c0']),(0x02c,bases['c1']),(0x030,bases['meta']),(0x034,bases['rope']),(0x070,request),(0x074,(bases['buffer']<<16)|cohort))
        for a,v in config:self.s.write32(a,v)
        record['descriptor_path']=self.evidence.write_json(job+'/descriptor.json',{'0x%03x'%a:v for a,v in config})['path']
        record['expected_output_sha256']=expected;record['reload_metadata']=layer!=self.layer;record['reload_rope']=not self.rope_loaded
        self.guard();self.pending={'record':record,'payload':payload,'step':step,'job':job};self.seen_commands.add(command);record['host_command_begin_monotonic_s']=time.perf_counter()
        self.evidence.journal('attention.before_start',record)
        try:
            record['start_before_monotonic_s']=time.perf_counter()
            self.s.write32(0x008,1|(4 if record['reload_metadata'] else 0)|(8 if record['reload_rope'] else 0));record['started']=True
            record['start_accepted_observed_s']=time.perf_counter();self.layer=layer;self.rope_loaded=True
            self.timeline.append({'engine':'attention','event':'start','time_s':record['start_before_monotonic_s'],'command':command})
        except BaseException as error:self.failed=repr(error);raise
        return record
    def collect(self):
        if self.pending is None or self.failed:raise RuntimeError('No healthy Attention pending')
        p=self.pending;r=p['record'];job=p['job'];deadline=time.perf_counter()+10
        try:
            while True:
                self.check_cpu_failure();status=self.s.read32(0x00c)
                if status&6:break
                if time.perf_counter()>deadline:raise TimeoutError('Attention timeout; retained pending/no clear')
                time.sleep(.001)
            r['done_observed_monotonic_s']=time.perf_counter();snap=self.snapshot()
            r['done_path']=self.evidence.write_json(job+'/done.json',snap)['path']
            AttentionBackend.completion_guard(snap,r['command_id'],r['request_id'],r['cohort'],r['buffer_id'],r['layer'])
            output=self.s.c2h_read_local(0,196608,r['output_base'],1<<20)
            if len(output)!=196608:raise IOError('Short Attention C2H; retained pending')
            stored=self.evidence.write_bytes(job+'/output_s24.bin',output)
            r.update(output_path=stored['path'],output_sha256=stored['sha256'],copied=True,copied_bytes=len(output))
            self.catalog.check(p['step'],r['layer'],r['cohort'],'attention',p['payload'],output,job);r['comparison']='AUDITED_FULL_SHA_PASS_PENDING_BYTEWISE' if self.catalog.mode=='audited_baseline' else 'NUMERICAL_VERIFICATION_PENDING'
            recheck=self.snapshot();self.evidence.write_json(job+'/done_recheck.json',recheck)
            AttentionBackend.completion_guard(recheck,r['command_id'],r['request_id'],r['cohort'],r['buffer_id'],r['layer'])
            if recheck!=snap:raise RuntimeError('Attention DONE changed before clear')
            self.check_cpu_failure();self.evidence.write_json(job+'/copied_comparison.json',r);self.evidence.journal('attention.before_clear',r)
            self.s.write32(0x008,2)
            deadline=time.perf_counter()+10
            while self.s.read32(0x00c)&0x27:
                if time.perf_counter()>deadline:raise TimeoutError('Attention clear did not retire')
                time.sleep(.001)
            r['sticky_cleared']=True;r['ack_finished_monotonic_s']=time.perf_counter();self.timeline.append({'engine':'attention','event':'cleared','time_s':r['ack_finished_monotonic_s'],'command':r['command_id']})
            self.evidence.write_json(job+'/completed.json',r);self.pending=None;return output,r
        except BaseException as error:
            self.failed=repr(error);r['error']=self.failed;self.evidence.write_json(job+'/failed.json',r);raise


class ResidentGu(GuOnlyXdmaBackend):
    def __init__(self,session,artifacts,store,evidence,catalog,check_cpu_failure):
        super().__init__(session,artifacts,poll_interval_s=.001,chunk_bytes=1<<20)
        self.store,self.evidence,self.catalog,self.check_cpu_failure=store,evidence,catalog,check_cpu_failure
        self.loading=None;self.current_record=None;self.job_dir=None;self.step=None;self.timeline=[];self.metadata_events=[];self.before_start_callback=None;self._staging=False
    def _healthy(self):
        super()._healthy();self.check_cpu_failure()
    def _clear_admission(self):
        if self._read(0x370):raise RuntimeError('Existing admission fault retained; no diagnostic clear')
    def _status(self):
        value=super()._status()
        if self._read(0x178)&0x18:raise RuntimeError('Metadata/tensor DMA fault retained')
        return value
    def _write(self,address,value):
        self._healthy()
        if address==0x320 and value==1:
            if self.before_start_callback is not None:
                callback,self.before_start_callback=self.before_start_callback,None;callback()
            self.current_record['start_before_monotonic_s']=time.perf_counter()
        super()._write(address,value)
        if address==0x320 and value==1:
            if self._read(0x370):raise RuntimeError('GU START rejected; not prefetching')
            event={'engine':'gu','event':'start','time_s':time.perf_counter(),'command':self.pending.command_id,'attention_status':self._read(0x00c),'gu_status':self._read(0x324)}
            self.timeline.append(event)
    def _check_done(self,descriptor):
        super()._check_done(descriptor)
        if self.current_record is not None and 'done_observed_monotonic_s' not in self.current_record:self.current_record['done_observed_monotonic_s']=time.perf_counter()
    def load_metadata(self,layer,after_last_start=False):
        if self.loading is not None:raise RuntimeError('Metadata prefetch already owned')
        if after_last_start:raise RuntimeError('Concurrent GU tensor/metadata LOAD disabled after real watchdog; require complete pair ACK')
        if self.pending is not None:raise RuntimeError('No metadata LOAD during a GU pending command')
        if not self._staging and (self.lease is None or self.acked_cohorts!={0,1}):raise RuntimeError('Metadata prefetch requires both cohort ACKs')
        self._require_idle()
        bank=1-(self._read(0x14c)&1)
        if self._read(0x14c)&0x18:raise RuntimeError('An unowned metadata LOAD already exists')
        item={'layer':layer,'bank':bank,'source':layer_spans(layer)['mlp_gate_meta'].address,'boundary':'initial stage' if self._staging else 'after both cohort full copies and ACKs','load_before_s':time.perf_counter()}
        self.loading=item;self.metadata_events.append(item)
        self.evidence.journal('metadata.before_load',item)
        for a,v in ((0x150,bank),(0x16c,item['source']),(0x170,0),(0x154,1)):self._write(a,v)
        item['load_write_return_s']=time.perf_counter();item['post_load_snapshot']={'gu_status':self._read(0x324),'dma_status':self._read(0x178),'meta_status':self._read(0x14c)}
        self._wait('metadata loading observed',lambda:bool(self._read(0x14c)&(8<<bank)));item['loading_observed_s']=time.perf_counter()
    def prefetch_after_pair(self,layer):
        self._healthy()
        if self.pending is not None or self.lease is None or self.acked_cohorts!={0,1} or not self.quiescent():raise RuntimeError('Metadata prefetch requires complete copied/ACKed pair and GU quiescent')
        self.load_metadata(layer);self.loading['prefetch_boundary']='after both full copy/identity/ACK; HostDown leases may remain'
        self.wait_metadata()
    def wait_metadata(self):
        if self.loading is None:raise RuntimeError('No metadata owner')
        bank=self.loading['bank']
        self._wait('metadata complete',lambda:not(self._read(0x178)&4) and self._read(0x160 if bank else 0x15c)==229376)
        self.loading.update(dma_complete_observed_s=time.perf_counter(),count=self._read(0x160 if bank else 0x15c),dma_status=self._read(0x178),meta_status=self._read(0x14c))
        records=self._read(0x250);physical_bytes=self._read(0x258)|(self._read(0x25c)<<32)
        self.loading.update(dma_gate_records=records,dma_physical_bytes=physical_bytes)
        if records!=229376 or physical_bytes!=7340032:raise RuntimeError('Metadata physical DMA workload differs')
    def stage_gu_layer(self,layer_id,epoch_id,prepared):
        self._healthy();self.store.require()
        if not self.initialized:self.initialize_shared_mode()
        if self.lease is not None or self.pending is not None or epoch_id in self.seen_epochs:raise RuntimeError('Old epoch/consumer lease not released')
        self._require_idle();global_guard(self.session)
        if prepared['layer']!=layer_id:raise ValueError('Wrong prepared canonical weights')
        self.seen_epochs.add(epoch_id);self.metadata_sequence+=1;generation=self.metadata_sequence
        self.lease=(layer_id,epoch_id,generation);self.acked_cohorts=set()
        try:
            identity=[]
            for name,data,address in zip(('mlp_gate_up_c0','mlp_gate_up_c1'),prepared['gu_payloads'],(0,0x01c00000)):
                want=self.artifacts.original.layer_artifact(layer_id,name)
                if len(data)!=29360128 or sha(data)!=want.sha256:raise ValueError('Prepared canonical weight identity changed')
                self._h2c(data,address);actual=self.session.c2h_read_local(1,len(data),address,self.chunk_bytes)
                item={'name':name,'address':address,'bytes':len(data),'sha256':want.sha256,'readback_sha256':sha(actual)};identity.append(item)
                if len(actual)!=len(data) or item['readback_sha256']!=want.sha256:raise IOError('Canonical GU DDR readback differs')
            if self.loading is None:
                self._staging=True
                try:self.load_metadata(layer_id)
                finally:self._staging=False
            if self.loading['layer']!=layer_id:raise RuntimeError('Wrong prefetched metadata owner')
            self.wait_metadata();bank=self.loading['bank']
            for a,v in ((0x150,bank),(0x158,generation),(0x154,2)):self._write(a,v)
            self._wait('metadata COMMIT',lambda:self._read(0x144)==generation and (self._read(0x14c)&(1|(2<<bank)))==(bank|(2<<bank)))
            self.loading.update(commit_observed_s=time.perf_counter(),generation=generation);self.loading=None
            for a,v in ((0x11c,layer_id),(0x12c,0),(0x130,0x01c00000),(0x134,0),(0x138,0)):self._write(a,v)
            self._clear_admission();self._write(0x36c,epoch_id)
            if self._read(0x370) or self._read(0x368)!=epoch_id:raise RuntimeError('GU epoch bind rejected')
            stage={'layer':layer_id,'epoch':epoch_id,'generation':generation,'canonical_weight_readbacks':identity,'metadata_sha256':self.artifacts.original.layer_artifact(layer_id,'mlp_gate_meta').sha256}
            self.evidence.write_json('staging/epoch_%d.json'%epoch_id,stage);return generation
        except BaseException as error:self._snapshot_failure(error);raise
    def run_verified(self,step,descriptor,payload,job):
        self.step,self.job_dir=step,job
        expected=self.catalog.expected(step,descriptor.layer_id,descriptor.cohort_id,'gu',payload)
        r={'command_id':descriptor.command_id,'request_id':descriptor.request_id,'cohort':descriptor.cohort_id,'layer':descriptor.layer_id,'buffer_id':descriptor.buffer_id,'copied':False,'acked':False,'comparison':'NOT_RUN','expected_output_sha256':expected,'weights_sha256':{n:self.artifacts.original.layer_artifact(descriptor.layer_id,n).sha256 for n in ('mlp_gate_up_c0','mlp_gate_up_c1','mlp_gate_meta')}};self.current_record=r
        r['input_readback']='NOT_PERFORMED; full Host input saved; exact H2C count; output follows explicit validation_mode'
        r['validation_mode']=self.catalog.mode
        stored=self.evidence.write_bytes(job+'/input_rec576.bin',payload);r.update(input_path=stored['path'],input_sha256=stored['sha256']);r['descriptor_path']=self.evidence.write_json(job+'/descriptor.json',dict(dataclasses.asdict(descriptor),words=list(descriptor.words())))['path']
        r['host_command_begin_monotonic_s']=time.perf_counter();self.evidence.journal('gu.before_start',r)
        try:
            result=super().run_gu(descriptor,payload)
            r['done_path']=self.evidence.write_json(job+'/done.json',{'0x%03x'%a:self._read(a) for a in tuple(range(0x324,0x36c,4))+(0x370,0x144,0x14c,0x260)})['path']
            stored=self.evidence.write_bytes(job+'/output_s24.bin',result.payload);r.update(output_path=stored['path'],output_sha256=stored['sha256'],copied=True)
            self.catalog.check(step,descriptor.layer_id,descriptor.cohort_id,'gu',payload,result.payload,job);r['comparison']='AUDITED_FULL_SHA_PASS_PENDING_BYTEWISE' if self.catalog.mode=='audited_baseline' else 'NUMERICAL_VERIFICATION_PENDING';self.evidence.write_json(job+'/copied_comparison.json',r)
            if self.loading is not None:self.wait_metadata()
            self.evidence.journal('gu.before_ack',r);super().ack_gu(descriptor.command_id);r.update(acked=True,ack_finished_monotonic_s=time.perf_counter())
            self.timeline.append({'engine':'gu','event':'acked','time_s':r['ack_finished_monotonic_s'],'command':descriptor.command_id});self.evidence.write_json(job+'/completed.json',r)
            return result.payload,r
        except BaseException as error:self._snapshot_failure(error);r['error']=repr(error);self.evidence.write_json(job+'/failed.json',r);raise
