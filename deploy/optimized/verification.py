"""Audited-input fingerprint guards, followed by full bytewise gold audit."""
import hashlib
import json
from pathlib import Path


def sha(data):return hashlib.sha256(data).hexdigest()


class GoldCatalog:
    mode='audited_baseline'
    def __init__(self,path,artifacts,assets,bit_sha,baseline_root):
        self.path=Path(path);self.index=json.loads(self.path.read_text());self.baseline_root=Path(baseline_root);self.used=[]
        if self.index.get('schema')!='scalellm_audited_baseline_index_v1':raise ValueError('Unknown audited gold index')
        identity=self.index['identity']
        expected={'checkpoint_sha256':artifacts.original.checkpoint_sha256,'artifact_manifest_sha256':artifacts.manifest_sha256,'host_assets_manifest_sha256':sha(assets.path.read_bytes()),'bit_sha256':bit_sha}
        if any(identity.get(k)!=v for k,v in expected.items()):raise ValueError('Baseline does not bind these model/bit artifacts')
        self.records={(r['step'],r['layer'],r['cohort']):r for r in self.index['records']}
        if len(self.records)!=128:raise ValueError('Complete128-command-pair baseline required')
        # Verify the independent bytewise audit source before touching hardware.
        for (step,layer,cohort),record in self.records.items():
            for engine,size in (('attention',196608),('gu',1376256)):
                old=self.baseline_root/('step_%03d/layer_%02d/cohort_%d/%s/gold_s24.bin'%(step,layer,cohort,engine))
                data=old.read_bytes()
                if len(data)!=size or sha(data)!=record[engine]['gold_sha256'] or record[engine]['gold_sha256']!=record[engine]['output_sha256']:raise ValueError('Independent baseline gold unavailable/changed: '+str(old))
    def expected(self,step,layer,cohort,engine,payload):
        entry=self.records[(step,layer,cohort)][engine]
        if sha(payload)!=entry['input_sha256']:raise ValueError('No exact input gold identity; no START: '+repr((step,layer,cohort,engine)))
        return entry['output_sha256']
    def check(self,step,layer,cohort,engine,payload,actual,job_dir):
        expected=self.expected(step,layer,cohort,engine,payload)
        if sha(actual)!=expected:raise AssertionError('Actual full output SHA differs; no ACK: '+repr((step,layer,cohort,engine)))
        self.used.append((step,layer,cohort,engine,job_dir,expected))
    def verify_bytes(self,result_root):
        started=__import__('time').perf_counter();records=[]
        for step,layer,cohort,engine,job,expected in self.used:
            actual=(Path(result_root)/job/'output_s24.bin').read_bytes()
            old=self.baseline_root/('step_%03d/layer_%02d/cohort_%d/%s/gold_s24.bin'%(step,layer,cohort,engine))
            gold=old.read_bytes()
            if sha(gold)!=expected or actual!=gold:raise AssertionError('Offline full gold bytes mismatch: '+str(old))
            records.append({'step':step,'layer':layer,'cohort':cohort,'engine':engine,'bytes':len(actual),'comparison':'PASS'})
        return {'verdict':'PASS','full_output_count':len(records),'seconds':__import__('time').perf_counter()-started,'records':records,'baseline_index_sha256':sha(self.path.read_bytes())}


class DeferredCatalog:
    """No baseline/reference files read or expected outputs used at runtime."""
    mode='deferred'
    def __init__(self):self.used=[]
    def expected(self,step,layer,cohort,engine,payload):
        sizes={'attention':196608,'gu':73728}
        if engine not in sizes or len(payload)!=sizes[engine] or not 0<=layer<32 or cohort not in (0,1):raise ValueError('Malformed deferred input identity')
        return None
    def check(self,step,layer,cohort,engine,payload,actual,job_dir):
        self.expected(step,layer,cohort,engine,payload)
        if len(actual)!={'attention':196608,'gu':1376256}[engine]:raise IOError('Short deferred C2H')
        self.used.append({'step':step,'layer':layer,'cohort':cohort,'engine':engine,'job_dir':job_dir,'input_sha256':sha(payload),'actual_output_sha256':sha(actual),'numerical_verification':'PENDING'})
