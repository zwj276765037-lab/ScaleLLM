"""Application gold-before-ACK binding; frozen production backend is unchanged."""
import dataclasses
from host.scalellm_mlp_gu_only_backend import GuOnlyXdmaBackend
from evidence import named

DONE=tuple(range(0x324,0x36c,4))+(0x370,0x144,0x14c,0x260)


class VerifiedGuBackend(GuOnlyXdmaBackend):
    def __init__(self,*args,evidence,reference_for_layer,resource_guard,**kwargs):
        super().__init__(*args,**kwargs)
        self.evidence=evidence;self.reference_for_layer=reference_for_layer;self.resource_guard=resource_guard
        self.job_dir=None;self.current_record=None;self.completed_commands=0
    def run_gu(self,descriptor,payload):
        self._healthy();d=str(self.job_dir)
        if self.job_dir is None:raise RuntimeError('GU evidence job directory required')
        r=dict(command_id=descriptor.command_id,request_id=descriptor.request_id,cohort=descriptor.cohort_id,layer=descriptor.layer_id,buffer_id=descriptor.buffer_id,comparison='NOT_RUN',acked=False)
        self.current_record=r
        try:
            self.resource_guard()
            r.update(named(self.evidence.write_bytes(d+'/input_rec576.bin',payload),'input'))
            rec=self.evidence.write_json(d+'/descriptor.json',dict(dataclasses.asdict(descriptor),words=list(descriptor.words())))
            r['descriptor_path']=rec['path'];r['weights_sha256']={x['name']:x['sha256'] for x in self.staged_identity[-1]['artifacts']}
            gold,audit=self.reference_for_layer(descriptor.layer_id).gu(bytes(payload))
            r.update(named(self.evidence.write_bytes(d+'/gold_s24.bin',gold),'gold'))
            r['gold_audit']=self.evidence.write_json(d+'/gold_audit.json',audit)
            self.resource_guard();self.evidence.journal('gu.before_start',r)
            result=super().run_gu(descriptor,payload)
            r['done_path']=self.evidence.write_json(d+'/done.json',{'0x%03x'%a:self._read(a) for a in DONE})['path']
            r.update(named(self.evidence.write_bytes(d+'/output_s24.bin',result.payload),'output'))
            r['comparison']='PASS' if bytes(result.payload)==bytes(gold) else 'FAIL'
            self.evidence.write_json(d+'/copied_comparison.json',r);self.evidence.journal('gu.copied_and_compared',r)
            if r['comparison']!='PASS':raise AssertionError('GU actual full output differs from independent gold')
            return result
        except BaseException as error:
            self._snapshot_failure(error)
            try:self.evidence.write_json(d+'/failed.json',dict(r,error=repr(error)));self.evidence.journal('gu.failed',dict(r,error=repr(error)))
            except BaseException:pass
            raise
    def ack_gu(self,command_id):
        r=self.current_record
        if r is None or r['comparison']!='PASS' or r['command_id']!=command_id:raise RuntimeError('Independent full gold PASS is required before ACK')
        self.evidence.journal('gu.before_ack',r)
        super().ack_gu(command_id)
        r['acked']=True;self.completed_commands+=1
        self.evidence.write_json(str(self.job_dir)+'/completed.json',r);self.evidence.journal('gu.completed',r)
