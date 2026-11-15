#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the current Decode16 design from RTL and Vivado IP in a new workspace."""
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

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'deploy/final/hardware_source_manifest.json'
GIB = 1024**3
STAGES = ('validate', 'create', 'elaborate', 'synth', 'impl', 'hold-sll', 'hold', 'bitstream')


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


def prepare(args):
    files = verify_sources()
    work = args.work.resolve()
    if work.exists():
        raise FileExistsError('Use a new build workspace: ' + str(work))
    vivado, board = args.vivado.resolve(), args.board_files.resolve()
    if not vivado.is_file():
        raise FileNotFoundError(vivado)
    for name in ('board.xml', 'part0_pins.xml', 'preset.xml'):
        if not (board/name).is_file():
            raise FileNotFoundError(board/name)
    config = dict(schema='scalellm_final_portable_build_v1', vivado=str(vivado),
                  board_files=str(board), source_inputs=files,
                  board_inputs={n:sha(board/n) for n in ('board.xml','part0_pins.xml','preset.xml')},
                  bit_identical_rebuild_claimed=False)
    work.mkdir(parents=True)
    for rel in files:
        if rel.startswith('project/hardware/'):
            out=work/'source'/rel; out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/rel,out)
    (work/'build.json').write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps(dict(work=str(work),source_files=len(files),next_stage='validate or create',
                         synth_implementation='NOT_RUN'),indent=2))


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


def run_stage(args):
    work=args.work.resolve(); cfg=json.loads((work/'build.json').read_text())
    for rel,want in cfg['source_inputs'].items():
        if rel.startswith('project/hardware/') and sha(work/'source'/rel)!=want:
            raise ValueError('Prepared hardware input changed: '+rel)
    for name,want in cfg['board_inputs'].items():
        if sha(Path(cfg['board_files'])/name)!=want:raise ValueError('Board file changed: '+name)
    if not 1<=args.threads<=4:raise ValueError('threads must be in 1..4')
    if args.timeout<1 or args.rss_gib<1:raise ValueError('Positive resource limits required')
    if args.stage in ('validate','create','elaborate') and (args.timeout>1800 or args.rss_gib>32):
        raise ValueError('Construction/elaboration limit: 1800 s and 32 GiB')
    cpus=[int(x) for x in args.cpus.split(',')]
    if not cpus or len(cpus)>4 or any(x<0 for x in cpus):raise ValueError('Select 1..4 available CPU IDs')
    if not set(cpus)<=os.sched_getaffinity(0):raise ValueError('Selected CPUs unavailable')
    os.sched_setaffinity(0,cpus)
    out=work/args.stage
    if out.exists():raise FileExistsError('Stage already attempted; preserve it and use a new workspace: '+str(out))
    if args.stage in ('elaborate','synth','impl') and not (work/'create/project/scalellm_final_decode16.xpr').is_file():
        raise ValueError('Successful create stage required')
    checkpoint=None
    if args.source_dcp is not None and args.stage not in ('hold-sll','hold','bitstream'):
        raise ValueError('--source-dcp applies only to hold-sll, hold or bitstream')
    if args.stage in ('hold-sll','hold','bitstream'):
        prior='hold-sll' if args.stage=='hold' else 'impl'
        source=(args.source_dcp or work/prior/'reports/routed.dcp').resolve()
        if not source.is_file():raise FileNotFoundError('Selected new routed checkpoint: '+str(source))
        checkpoint=dict(path=str(source),sha256=sha(source))
    if mem_available()<64*GIB:raise RuntimeError('Require at least 64 GiB available RAM')
    out.mkdir();reports=out/'reports';reports.mkdir()
    hw=work/'source/project/hardware'
    env=os.environ.copy()
    for name in list(env):
        if name.startswith(('HAP_','XILINX_LOCAL_USER_DATA')):env.pop(name)
    env.update(HAP_STAGE=args.stage,HAP_JOBS=str(args.threads),HAP_REPORT_DIR=str(reports),
               HAP_PROJECT_DIR=str((out if args.stage in ('validate','create') else work/'create')/'project'),
               HAP_BOARD_FILES=cfg['board_files'],HAP_BOARD_CORE_CLK_MHZ='80.0',
               HAP_BOARD_DDR_UI_CLK_HZ='200000000',HAP_BD_VALIDATE_ONLY=str(int(args.stage=='validate')),
               HAP_WORK_DIR=str(work),HAP_HW_ROOT=str(hw),OMP_NUM_THREADS=str(args.threads))
    if checkpoint:env.update(HAP_SOURCE_DCP=checkpoint['path'],HAP_SOURCE_DCP_SHA256=checkpoint['sha256'])
    if args.stage in ('hold-sll','hold'):
        env['HAP_HOLD_METHOD']='sll_reg_hold_fix' if args.stage=='hold-sll' else 'hold_fix'
        script=hw/'vivado/scripts/release_hold_repair.tcl'
    else:
        script=hw/'vivado/scripts'/('release_create_board.tcl' if args.stage in ('validate','create') else 'release_build_board.tcl')
    argv=[cfg['vivado'],'-mode','batch','-notrace','-source',str(script),'-log',str(out/'vivado.log'),'-journal',str(out/'vivado.jou')]
    print(json.dumps(dict(stage=args.stage,command=argv,timeout_seconds=args.timeout,rss_limit_gib=args.rss_gib,
                         minimum_available_gib=64,cpus=cpus,threads=args.threads,jobs=1),indent=2),flush=True)
    started=time.monotonic();peak=0;reason=None
    def child_setup():
        os.sched_setaffinity(0,cpus);os.nice(10)
    with (out/'console.log').open('w') as log:
        p=subprocess.Popen(argv,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=child_setup)
        try:
            while p.poll() is None:
                rss=process_tree(p.pid);peak=max(peak,rss)
                if time.monotonic()-started>args.timeout:reason='wall time limit'
                elif rss>args.rss_gib*GIB:reason='RSS limit'
                elif mem_available()<64*GIB:reason='available memory floor'
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
    if checkpoint and sha(checkpoint['path'])!=checkpoint['sha256']:
        changed.append('selected source checkpoint')
    if changed and reason is None:reason='prepared inputs changed'
    result=dict(stage=args.stage,returncode=p.returncode,stop_reason=reason,changed_inputs=changed,source_checkpoint=checkpoint,native_pass_marker=marker in logs,
                elapsed_seconds=round(time.monotonic()-started,3),peak_tree_rss_bytes=peak,
                reports={str(f.relative_to(out)):sha(f) for f in reports.rglob('*') if f.is_file()})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    if reason or p.returncode:raise SystemExit(1)


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    s.add_parser('check')
    q=s.add_parser('prepare');q.add_argument('--work',type=Path,required=True);q.add_argument('--vivado',type=Path,required=True);q.add_argument('--board-files',type=Path,required=True)
    q=s.add_parser('stage');q.add_argument('--work',type=Path,required=True);q.add_argument('--stage',choices=STAGES,required=True)
    q.add_argument('--source-dcp',type=Path);q.add_argument('--threads',type=int,default=4);q.add_argument('--cpus',default='0,1,2,3')
    q.add_argument('--timeout',type=int,default=1800);q.add_argument('--rss-gib',type=int,default=32)
    a=p.parse_args()
    if a.action=='check':print(json.dumps({'source_files':len(verify_sources()),'status':'PASS'}))
    elif a.action=='prepare':prepare(a)
    else:stage(a)


if __name__=='__main__':main()
