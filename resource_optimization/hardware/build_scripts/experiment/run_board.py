#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run guarded native stages for an isolated DSP recovery board candidate."""
import argparse
import hashlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
MANIFEST = ROOT / 'deploy/final/hardware_source_manifest.json'
BASE_MANIFEST_SHA = '10795824a738727afadaf55941d7c51dc4e36ff3e1819df2ab0ab9b23160f3c9'
LEAF_REL = 'project/hardware/rtl/mlp/hap_a8w4_scalecode_recover2_lut.sv'
ATTRS = {'dsp_raw_only': ['no','no','yes','yes'], 'dsp_all': ['yes','yes','yes','yes']}
GIB = 1024**3
STAGES = ('validate', 'create', 'elaborate', 'synth', 'place', 'route', 'hold-sll', 'hold', 'bitstream')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def verify_sources():
    manifest = json.loads(MANIFEST.read_text())
    files = manifest['files'] | manifest['portable_build_files']
    for rel, want in files.items():
        p = ROOT / rel
        if not p.is_file() or sha(p) != want:
            raise ValueError('Hardware release input changed: ' + rel)
    subprocess.run([sys.executable, str(ROOT/'project/hardware/vivado/scripts/final_gen_abi.py'), '--check'], check=True)
    return files


def verify_candidate(work, cfg):
    if sha(MANIFEST) != BASE_MANIFEST_SHA:
        raise ValueError('Published source manifest changed')
    original = verify_sources()
    name = cfg.get('candidate')
    if cfg.get('schema') != 'scalellm_dsp_recovery_candidate_build_v1' or name not in ATTRS:
        raise ValueError('Invalid candidate build identity')
    if cfg.get('base_manifest_sha256') != BASE_MANIFEST_SHA:
        raise ValueError('Candidate parent manifest mismatch')
    if cfg.get('candidate_driver_sha256') != sha(Path(__file__)) or cfg.get('candidate_tcl_sha256') != sha(HERE/'scripts/build_board.tcl'):
        raise ValueError('Candidate build scripts changed')
    candidate = cfg.get('candidate_leaf', {})
    if candidate.get('relative_path') != LEAF_REL or candidate.get('base_sha256') != original[LEAF_REL] or candidate.get('attribute_values') != ATTRS[name]:
        raise ValueError('Candidate overlay identity invalid')
    if set(cfg['source_inputs']) != set(original):
        raise ValueError('Candidate source closure changed')
    for rel, digest in original.items():
        if rel != LEAF_REL and cfg['source_inputs'][rel] != digest:
            raise ValueError('Non-leaf source hash changed in candidate manifest: '+rel)
    target = work/'source'/LEAF_REL
    if candidate.get('sha256') != sha(target) or cfg['source_inputs'][LEAF_REL] != sha(target):
        raise ValueError('Candidate leaf hash mismatch')
    base = (ROOT/LEAF_REL).read_text()
    actual = target.read_text()
    import re
    attributes = re.findall(r'\(\* use_dsp = "(no|yes)" \*\)', actual)
    if attributes != ATTRS[name] or actual.replace('(* use_dsp = "yes" *)', '(* use_dsp = "no" *)') != base:
        raise ValueError('Candidate differs beyond the four approved DSP attributes')
    manifest = json.loads((work/'candidate_manifest.json').read_text())
    if (manifest.get('candidate') != name or manifest.get('parent_release_manifest_sha256') != BASE_MANIFEST_SHA
            or manifest.get('allowed_overlay') != candidate or manifest.get('source_inputs') != cfg['source_inputs']
            or manifest.get('board_inputs') != cfg['board_inputs'] or manifest.get('driver_sha256') != cfg['candidate_driver_sha256']
            or manifest.get('tcl_sha256') != cfg['candidate_tcl_sha256']):
        raise ValueError('Candidate manifest changed')
    return manifest


def mem_available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1])*1024
    raise RuntimeError('Linux MemAvailable unavailable')


def process_tree(root):
    rows={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            txt=(p/'stat').read_text(); rest=txt[txt.rindex(')')+2:].split()
            rows[int(p.name)]=(int(rest[1]),int(rest[21])*os.sysconf('SC_PAGE_SIZE'))
        except (FileNotFoundError,ProcessLookupError,PermissionError,ValueError):pass
    selected={root};changed=True
    while changed:
        new={pid for pid,(ppid,_) in rows.items() if ppid in selected}
        changed=bool(new-selected);selected|=new
    return sum(rows.get(pid,(0,0))[1] for pid in selected)


def stage(args):
    with (args.work.resolve()/'.native.lock').open('a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run_stage(args)


def total_candidate_rss():
    total = 0
    for progress_path in (HERE/'runs').glob('*/**/progress.json'):
        try:
            progress = json.loads(progress_path.read_text())
            if progress.get('status') != 'RUNNING':
                continue
            pid = int(progress['pid'])
            cmdline = (Path('/proc')/str(pid)/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if 'vivado' not in cmdline:
                continue
            total += process_tree(pid)
        except (FileNotFoundError, ValueError, KeyError, PermissionError):
            continue
    return total


def run_stage(args):
    work=args.work.resolve(); cfg=json.loads((work/'build.json').read_text())
    verify_candidate(work, cfg)
    for rel,want in cfg['source_inputs'].items():
        if rel.startswith('project/hardware/') and sha(work/'source'/rel)!=want:
            raise ValueError('Prepared hardware input changed: '+rel)
    for name,want in cfg['board_inputs'].items():
        if sha(Path(cfg['board_files'])/name)!=want:raise ValueError('Board file changed: '+name)
    if not 1<=args.threads<=32:raise ValueError('threads must be in 1..32 for installed Vivado 2025.2')
    if not 1<=args.ip_jobs<=12:raise ValueError('IP jobs must be in 1..12')
    if args.stage != 'synth' and args.ip_jobs != 1:raise ValueError('IP jobs applies only to synth')
    if args.stage in ('validate','create') and args.threads>4:raise ValueError('Frozen constructor supports at most four native threads')
    if args.timeout<1 or args.rss_gib<1:raise ValueError('Positive resource limits required')
    if args.stage in ('validate','create','elaborate') and (args.timeout>1800 or args.rss_gib>32):
        raise ValueError('Construction/elaboration limit: 1800 s and 32 GiB')
    cpus=[int(x) for x in args.cpus.split(',')]
    cpu_limit=96 if args.stage in ('route','hold-sll','hold','bitstream') else 48
    if not cpus or len(cpus)>cpu_limit or any(x<0 for x in cpus):raise ValueError('Select 1..%d available CPU IDs' % cpu_limit)
    if len(cpus)>48 and total_candidate_rss()>0:
        raise ValueError('Full-machine physical stage requires no other candidate Vivado tree')
    if not set(cpus)<=os.sched_getaffinity(0):raise ValueError('Selected CPUs unavailable')
    os.sched_setaffinity(0,cpus)
    out=work/args.stage
    if out.exists():raise FileExistsError('Stage already attempted; preserve it and use a new workspace: '+str(out))
    if args.stage in ('elaborate','synth','place','route') and not (work/'create/project/scalellm_final_decode16.xpr').is_file():
        raise ValueError('Successful create stage required')
    if args.stage == 'route' and not (work/'place/result.json').is_file():
        raise ValueError('Successful candidate placement required')
    if args.stage == 'route':
        place=json.loads((work/'place/result.json').read_text())
        if place['returncode'] != 0 or place['stop_reason'] is not None or not place['native_pass_marker']:
            raise ValueError('Successful candidate placement required')
        remaining=28800-place['elapsed_seconds']
        if remaining < 1 or args.timeout > remaining:
            raise ValueError('Place and route share 28800-second limit; remaining='+str(remaining))
    if args.stage == 'hold' and (work/'hold-sll/result.json').is_file():
        prior=json.loads((work/'hold-sll/result.json').read_text())
        remaining=7200-prior['elapsed_seconds']
        if remaining < 1 or args.timeout > remaining:
            raise ValueError('Hold-sll and hold share 7200-second limit; remaining='+str(remaining))
    checkpoint=None
    if args.source_dcp is not None and args.stage not in ('hold-sll','hold','bitstream'):
        raise ValueError('--source-dcp applies only to hold-sll, hold or bitstream')
    if args.stage in ('hold-sll','hold','bitstream'):
        prior='hold-sll' if args.stage=='hold' else 'route'
        source=(args.source_dcp or work/prior/'reports/routed.dcp').resolve()
        if not source.is_file():raise FileNotFoundError('Selected new routed checkpoint: '+str(source))
        checkpoint=dict(path=str(source),sha256=sha(source))
    if mem_available()<64*GIB:raise RuntimeError('Require at least 64 GiB available RAM')
    if shutil.disk_usage(work).free<30*GIB:raise RuntimeError('Require at least 30 GiB free disk')
    out.mkdir();reports=out/'reports';reports.mkdir()
    hw=work/'source/project/hardware'
    env=os.environ.copy()
    for name in list(env):
        if name.startswith(('HAP_','XILINX_LOCAL_USER_DATA')):env.pop(name)
    env.update(HAP_STAGE=args.stage,HAP_JOBS=str(args.threads),HAP_REPORT_DIR=str(reports),
               HAP_PROJECT_DIR=str((out if args.stage in ('validate','create') else work/'create')/'project'),
               HAP_BOARD_FILES=cfg['board_files'],HAP_BOARD_CORE_CLK_MHZ='80.0',
               HAP_BOARD_DDR_UI_CLK_HZ='200000000',HAP_BD_VALIDATE_ONLY=str(int(args.stage=='validate')),
               HAP_WORK_DIR=str(work),HAP_HW_ROOT=str(hw),HAP_IP_JOBS=str(args.ip_jobs),OMP_NUM_THREADS=str(args.threads))
    if checkpoint:env.update(HAP_SOURCE_DCP=checkpoint['path'],HAP_SOURCE_DCP_SHA256=checkpoint['sha256'])
    if args.stage in ('hold-sll','hold'):
        env['HAP_HOLD_METHOD']='sll_reg_hold_fix' if args.stage=='hold-sll' else 'hold_fix'
        script=hw/'vivado/scripts/release_hold_repair.tcl'
    elif args.stage in ('synth','place','route'):
        script=HERE/'scripts/build_board.tcl'
    else:
        script=hw/'vivado/scripts'/('release_create_board.tcl' if args.stage in ('validate','create') else 'release_build_board.tcl')
    stage_hook=HERE/'scripts/post_opt_guard.tcl' if args.stage=='place' else None
    argv=[cfg['vivado'],'-mode','batch','-notrace','-source',str(script),'-log',str(out/'vivado.log'),'-journal',str(out/'vivado.jou')]
    inputs=dict(candidate=cfg['candidate'],stage=args.stage,build_json_sha256=sha(work/'build.json'),
                candidate_manifest_sha256=sha(work/'candidate_manifest.json'),
                parent_release_manifest_sha256=sha(MANIFEST),candidate_driver_sha256=sha(Path(__file__)),
                stage_tcl_sha256=sha(script),source_inputs=cfg['source_inputs'],board_inputs=cfg['board_inputs'],
                source_checkpoint=checkpoint,
                stage_hook_sha256=sha(stage_hook) if stage_hook else None)
    (out/'stage_inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    print(json.dumps(dict(stage=args.stage,command=argv,timeout_seconds=args.timeout,rss_limit_gib=args.rss_gib,
                         minimum_available_gib=64,cpus=cpus,threads=args.threads,ip_jobs=args.ip_jobs),indent=2),flush=True)
    started=time.monotonic();peak=0;reason=None
    min_mem=mem_available();min_free=shutil.disk_usage(work).free
    def child_setup():
        os.sched_setaffinity(0,cpus);os.nice(10)
    with (out/'console.log').open('w') as log:
        p=subprocess.Popen(argv,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=child_setup)
        (out/'progress.json').write_text(json.dumps(dict(stage=args.stage,candidate=cfg['candidate'],pid=p.pid,
            status='RUNNING',started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),command=argv,
            cpus=cpus,threads=args.threads,ip_jobs=args.ip_jobs,timeout_seconds=args.timeout,rss_limit_gib=args.rss_gib),indent=2)+'\n')
        try:
            while p.poll() is None:
                rss=process_tree(p.pid);peak=max(peak,rss)
                min_mem=min(min_mem,mem_available())
                min_free=min(min_free,shutil.disk_usage(work).free)
                if time.monotonic()-started>args.timeout:reason='wall time limit'
                elif rss>args.rss_gib*GIB:reason='RSS limit'
                elif total_candidate_rss()>384*GIB:reason='combined candidate RSS limit'
                elif min_mem<64*GIB:reason='available memory floor'
                elif min_free<30*GIB:reason='free disk floor'
                if reason:
                    os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=15)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
                    break
                time.sleep(1)
        finally:
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=15)
    logs=(out/'console.log').read_text(errors='replace')
    marker={'validate':'M002_BD_VALIDATION_PASS','create':'SCALELLM_RELEASE_CREATE_PASS'}.get(args.stage,'SCALELLM_RELEASE_STAGE_PASS stage='+args.stage)
    if p.returncode==0 and marker not in logs and reason is None:reason='missing native pass marker'
    changed=[rel for rel,want in cfg['source_inputs'].items() if rel.startswith('project/hardware/') and sha(work/'source'/rel)!=want]
    if sha(script)!=inputs['stage_tcl_sha256']:changed.append('stage Tcl')
    if stage_hook and sha(stage_hook)!=inputs['stage_hook_sha256']:changed.append('stage hook Tcl')
    if checkpoint and sha(checkpoint['path'])!=checkpoint['sha256']:
        changed.append('selected source checkpoint')
    if changed and reason is None:reason='prepared inputs changed'
    result=dict(stage=args.stage,returncode=p.returncode,stop_reason=reason,changed_inputs=changed,source_checkpoint=checkpoint,native_pass_marker=marker in logs,
                elapsed_seconds=round(time.monotonic()-started,3),peak_tree_rss_bytes=peak,
                minimum_mem_available_bytes=min_mem,minimum_disk_free_bytes=min_free,
                stage_inputs_sha256=sha(out/'stage_inputs.json'),
                console_sha256=sha(out/'console.log'),vivado_log_sha256=sha(out/'vivado.log') if (out/'vivado.log').is_file() else None,
                vivado_journal_sha256=sha(out/'vivado.jou') if (out/'vivado.jou').is_file() else None,
                reports={str(f.relative_to(out)):sha(f) for f in reports.rglob('*') if f.is_file()})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    progress=json.loads((out/'progress.json').read_text())
    progress.update(status='PASS' if not reason and p.returncode==0 else 'FAIL',result=str(out/'result.json'))
    (out/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
    if reason or p.returncode:raise SystemExit(1)


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('stage');q.add_argument('--work',type=Path,required=True);q.add_argument('--stage',choices=STAGES,required=True)
    q.add_argument('--source-dcp',type=Path);q.add_argument('--threads',type=int,default=4);q.add_argument('--ip-jobs',type=int,default=1);q.add_argument('--cpus',default='0,1,2,3')
    q.add_argument('--timeout',type=int,default=1800);q.add_argument('--rss-gib',type=int,default=32)
    a=p.parse_args()
    stage(a)


if __name__=='__main__':main()
