#!/usr/bin/env python3
"""Portable front end to the unchanged, numerically verified runtime."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE=Path(__file__).resolve().parent
BIT_SHA='66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47'
DEPENDENCIES={'numpy':'1.26.4','tokenizers':'0.20.3','Jinja2':'3.1.6'}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def vendor_check():
    manifest=json.loads((HERE/'vendor_manifest.json').read_text())
    for rel,item in manifest['files'].items():
        path=(HERE/rel).resolve();path.relative_to(HERE)
        if not path.is_file() or path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('Vendored source identity mismatch: '+rel)
    return len(manifest['files'])


def config(path):
    path=Path(path).resolve();value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('schema')!='scalellm_deploy_v1':raise ValueError('Wrong deployment config schema')
    for key in ('artifacts','host_assets','output_dir','bitstream'):
        text=os.path.expandvars(value[key]);value[key]=str((path.parent/Path(text)).resolve())
    prompts=value.get('prompts')
    if not isinstance(prompts,list) or len(prompts)!=2 or not all(isinstance(x,str) and x for x in prompts):raise ValueError('Exactly two nonempty real prompts required')
    if type(value.get('max_new_tokens'))is not int or value['max_new_tokens'] not in (1,2):raise ValueError('This runtime supports1..2 newtokens')
    digest=value.get('expected_checkpoint_sha256')
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Expected strict checkpoint SHA must be lowercase SHA256')
    return value


def bootstrap():
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    os.environ['SCALELLM_REFERENCE_HARDWARE_ROOT']=str(HERE/'vendor/hardware')
    for path in reversed([HERE,HERE/'vendor/runtime',HERE/'vendor/runtime/numeric_reference',HERE/'vendor/hardware']):sys.path.insert(0,str(path))


def cpu_check(c,models=False):
    checked_files=vendor_check()
    if sys.version_info<(3,10) or sys.maxsize<=2**32:raise RuntimeError('64-bit Python3.10+ required; validated version3.12.10')
    try:versions={name:importlib.metadata.version(name) for name in DEPENDENCIES}
    except importlib.metadata.PackageNotFoundError as error:raise RuntimeError('Install deploy/requirements.txt into your isolated Python environment') from error
    if versions!=DEPENDENCIES:raise RuntimeError('Use pinned deployment dependencies: '+repr(versions))
    bootstrap()
    for name in ('run_inference','reference','core','resource_guard','device_health'):importlib.import_module(name)
    result={'python':platform.python_version(),'dependencies':versions,'imports':'PASS','gpu_used':False,'device_opened':False,'vendor_files_verified':checked_files}
    if models:
        import host_math
        host_math.CHECKPOINT_SHA=c['expected_checkpoint_sha256']
        from host.scalellm_mlp_gu_only_artifacts import GuOnlyArtifactManifest
        assets=host_math.HostAssets(c['host_assets'],verify=True);artifacts=GuOnlyArtifactManifest.load(c['artifacts'])
        if artifacts.original.checkpoint_sha256!=c['expected_checkpoint_sha256']:raise ValueError('Hardware/Host assets source identity mismatch')
        tokenizer,requests=host_math.actual_requests(assets,tuple(c['prompts']),c['max_new_tokens']);result['requests']=requests;result['models']='ALL_SHA_PASS'
    return result


def run(c,mode):
    if os.name!='nt':raise RuntimeError('Actual local XDMA execution requires Windows')
    expected=c.get('expected_driver_sha256')
    if not isinstance(expected,str) or len(expected)!=64 or any(x not in '0123456789abcdef' for x in expected):raise ValueError('Configure SHA256 of your verified locally built/signed XDMA.sys before running')
    cpu_check(c)
    import device_health,host_math,run_inference as runtime
    saved_globals=(host_math.CHECKPOINT_SHA,runtime.CHECKPOINT_SHA,runtime.Evidence,runtime.actual_requests,runtime.source_identity)
    device_health.configure(c);host_math.CHECKPOINT_SHA=c['expected_checkpoint_sha256'];runtime.CHECKPOINT_SHA=c['expected_checkpoint_sha256']
    original_evidence=runtime.Evidence
    class ConfigEvidence(original_evidence):
        def __init__(self,path):
            super().__init__(path);self.write_json('deployment_config.json',c)
        def replace_json(self,rel,value):
            if rel=='run_summary.json' and 'topology' in value:
                value['topology'].update(host_model_cpu='Local Windows CPU',host_platform=platform.platform(),host_processor=platform.processor())
            return super().replace_json(rel,value)
    runtime.Evidence=ConfigEvidence
    runtime.actual_requests=lambda assets:host_math.actual_requests(assets,tuple(c['prompts']),c['max_new_tokens'])
    # Original identity helper names a rig-specific file; replace only the audit
    # producer, recording every distributed source plus this portable adapter.
    def identity():
        m=json.loads((HERE/'vendor_manifest.json').read_text())
        values={str(HERE/rel):sha(HERE/rel) for rel in m['files'] if (HERE/rel).suffix=='.py'}
        for rel in ('scalellm.py','device_health.py','vendor_manifest.json'):values[str(HERE/rel)]=sha(HERE/rel)
        config_snapshot=output/'deployment_config.json';values[str(config_snapshot)]=sha(config_snapshot)
        return values
    runtime.source_identity=identity
    output=Path(c['output_dir'])/('AT_'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'_llama')
    output.parent.mkdir(parents=True,exist_ok=True)
    print(json.dumps({'result':str(output),'mode':mode,'scope':'Actual Windows CPU+FPGA, full gold before clear/ACK'}),flush=True)
    saved=sys.argv
    try:
        sys.argv=[runtime.__file__,'--artifacts',c['artifacts'],'--assets',c['host_assets'],'--result',str(output),'--mode',mode];runtime.main()
    finally:
        sys.argv=saved
        host_math.CHECKPOINT_SHA,runtime.CHECKPOINT_SHA,runtime.Evidence,runtime.actual_requests,runtime.source_identity=saved_globals


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',default=str(HERE/'config.example.json'))
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('dry-run');q=sub.add_parser('preflight');q.add_argument('--models',action='store_true');q.add_argument('--device',action='store_true')
    q=sub.add_parser('run');q.add_argument('--mode',choices=('pilot','full'),default='full')
    q=sub.add_parser('resident');q.add_argument('--mode',choices=('pilot','full'),default='full');q.add_argument('--pilot-layers',type=int,choices=(1,2),default=2);q.add_argument('--validation-mode',choices=('deferred','audited_baseline'),default='deferred');q.add_argument('--baseline-root');q.add_argument('--baseline-index',default=str(HERE/'optimized/baseline_index.json'));q.add_argument('--dry-run',action='store_true')
    q=sub.add_parser('offline-audit');q.add_argument('--run',required=True);q.add_argument('--source-root',required=True);q.add_argument('--receipt',required=True)
    q=sub.add_parser('program');q.add_argument('--vivado',required=True);q.add_argument('--server',required=True);q.add_argument('--target',required=True);q.add_argument('--device',required=True);q.add_argument('--dry-run',action='store_true')
    a=p.parse_args();c=config(a.config)
    if a.command=='dry-run':print(json.dumps({'verdict':'PLAN_VALID','device_opened':False,'vendor_files_verified':vendor_check(),'resolved_config':c,'missing_paths':[c[k] for k in ('artifacts','host_assets','bitstream') if not Path(c[k]).is_file()]},indent=2));return
    if a.command=='preflight':
        result=cpu_check(c,a.models)
        if a.device:
            if os.name!='nt':raise RuntimeError('Device preflight requires Windows')
            import device_health
            device_health.configure(c);result['identity']=device_health.system_identity()
            from scalellm_windows_xdma import WindowsXdmaSession
            with WindowsXdmaSession() as session:
                att,gu=device_health.csr_snapshots(session);result['readonly_csrs']={'attention':att,'gu':gu,'control':device_health.control_snapshot(session)}
            result['device_opened']=True;result['device_writes']=False;result['handles_closed']=not session.handles
        print(json.dumps({'verdict':'PASS',**result},indent=2));return
    if a.command=='run':run(c,a.mode);return
    if a.command=='offline-audit':
        cpu_check(c)
        from optimized.offline_audit import main as audit_main
        return audit_main(['--run',a.run,'--artifacts',c['artifacts'],'--assets',c['host_assets'],'--source-root',a.source_root,'--receipt',a.receipt])
    if a.command=='resident':
        vendor_check()
        if a.validation_mode=='audited_baseline' and not a.baseline_root:p.error('audited_baseline requires --baseline-root; no fallback')
        if a.dry_run:
            print(json.dumps({'device_opened':False,'implementation':'resident_interleaved_post_ack_metadata_v2','mode':a.mode,'pilot_layers':a.pilot_layers,'validation_mode':a.validation_mode,'config':c,'baseline_index':str(Path(a.baseline_index).resolve()) if a.validation_mode=='audited_baseline' else None,'baseline_root':str(Path(a.baseline_root).resolve()) if a.validation_mode=='audited_baseline' else None,'numerical_verdict_after_execution':'NUMERICAL_VERIFICATION_PENDING' if a.validation_mode=='deferred' else 'requires exact audited input/output and full bytewise comparison','GU_weight_limit':'canonical56MiB reloaded per layer; only A weights/meta and GU meta resident'},indent=2));return
        if os.name!='nt':raise RuntimeError('Actual resident execution requires Windows')
        if not isinstance(c.get('expected_driver_sha256'),str) or len(c['expected_driver_sha256'])!=64:raise ValueError('Verified installed driver SHA required')
        cpu_check(c)
        import device_health
        device_health.configure(c)
        from optimized.run import main as resident_main
        output=Path(c['output_dir'])/('AT_'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'_resident')
        output.parent.mkdir(parents=True,exist_ok=True)
        print(json.dumps({'result':str(output),'mode':a.mode,'validation_mode':a.validation_mode,'implementation':'resident_interleaved_post_ack_metadata_v2'}),flush=True)
        args=['--artifacts',c['artifacts'],'--assets',c['host_assets'],'--result',str(output),'--mode',a.mode,'--pilot-layers',str(a.pilot_layers),'--validation-mode',a.validation_mode]
        if a.validation_mode=='audited_baseline':args.extend(['--baseline-root',a.baseline_root,'--baseline-index',a.baseline_index])
        resident_main(args,config=c);return
    vendor_check();bit=Path(c['bitstream'])
    argv=[a.vivado,'-mode','batch','-source',str(HERE/'jtag/program_sram.tcl'),'-tclargs',a.server,a.target,a.device,str(bit)]
    if not bit.is_file() or bit.stat().st_size!=80159259 or sha(bit)!=BIT_SHA:raise ValueError('Specified released bitstream identity mismatch')
    if a.dry_run:print(json.dumps({'device_opened':False,'command':argv,'bit_sha256':BIT_SHA},indent=2));return
    subprocess.run(argv,check=True)

if __name__=='__main__':main()
