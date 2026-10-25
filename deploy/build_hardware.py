#!/usr/bin/env python3
"""Materialize a new GU-only build tree; never mutate released source snapshots."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prepare(work,vivado,board,dry_run=False):
    from scalellm import vendor_check
    vendor_check()
    release=json.loads((HERE/'hardware_release_manifest.json').read_text());source=HERE/'vendor/hardware'
    for rel,want in release['files'].items():
        if sha(source/rel)!=want:raise ValueError('Released hardware source changed: '+rel)
    plan={'work':str(work),'vivado':str(vivado),'required_vivado':'2025.2','board_files':str(board),'source_files':release['source_count'],'rtl_changes':False,'adaptation':'independent copied tree: executable and board-store paths, then new source freeze','bit_identical_rebuild_claimed':False}
    if dry_run:return plan
    if work.exists():raise FileExistsError('Build workspace must be new: '+str(work))
    if not vivado.is_file():raise FileNotFoundError(vivado)
    for n in ('board.xml','part0_pins.xml','preset.xml'):
        if not (board/n).is_file():raise FileNotFoundError(board/n)
    hw=work/'project/hardware';hw.parent.mkdir(parents=True);shutil.copytree(source,hw)
    shutil.copytree(HERE/'vendor/mission',work/'mission')
    driver=hw/'vivado/scripts/run_mlp_gu_board.py';text=driver.read_text();old=next(line for line in text.splitlines() if line.startswith('VIVADO='));text=text.replace(old,'VIVADO='+repr(str(vivado)));driver.write_text(text)
    constructor=hw/'vivado/scripts/create_mlp_gu_board.tcl';text=constructor.read_text();start=text.index('set board_files [list \\');end=text.index('\nset inputs ',start)
    def tcl(p):return '{'+str(p).replace('\\','/')+'}'
    text=text[:start]+'set board_files [list '+ ' '.join(tcl(board/n) for n in ('board.xml','part0_pins.xml','preset.xml'))+']'+text[end:];constructor.write_text(text)
    for n in ('project','reports'):(hw/'vivado'/n).mkdir(exist_ok=True)
    subprocess.run([sys.executable,str(hw/'vivado/scripts/m006_gu_entry.py'),'freeze'],check=True)
    subprocess.run([sys.executable,str(hw/'vivado/scripts/m006_gu_entry.py'),'check'],check=True)
    plan['adapted_files']={str(p.relative_to(hw)):sha(p) for p in (driver,constructor)};plan['board_files_sha256']={n:sha(board/n) for n in ('board.xml','part0_pins.xml','preset.xml')}
    (work/'portable_build.json').write_text(json.dumps(plan,indent=2)+'\n');return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('prepare');q.add_argument('--work',type=Path,required=True);q.add_argument('--vivado',type=Path,required=True);q.add_argument('--board-files',type=Path,required=True);q.add_argument('--dry-run',action='store_true')
    q=s.add_parser('stage');q.add_argument('--work',type=Path,required=True);q.add_argument('--stage',choices=('create','synth','impl'),required=True);q.add_argument('--attempt',required=True);q.add_argument('--project',type=Path);q.add_argument('--synth-dcp',type=Path);q.add_argument('--dry-run',action='store_true')
    q=s.add_parser('bitstream');q.add_argument('--vivado',required=True);q.add_argument('--routed-dcp',type=Path,required=True);q.add_argument('--output',type=Path,required=True);q.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':print(json.dumps(prepare(a.work.resolve(),a.vivado.resolve(),a.board_files.resolve(),a.dry_run),indent=2));return
    if a.action=='stage':
        if not a.attempt.replace('_','').isalnum():raise ValueError('Simple unique attempt label required')
        hw=a.work.resolve()/'project/hardware';argv=[sys.executable,str(hw/'vivado/scripts/run_mlp_gu_board.py'),a.stage,a.attempt]
        if a.stage!='create' and a.project is None:raise ValueError('--project from successful create required')
        if a.project:argv+=['--project',str(a.project.resolve())]
        if a.stage=='impl' and a.synth_dcp is None:raise ValueError('--synth-dcp from successful new synthesis required')
        if a.synth_dcp:argv+=['--synth-dcp',str(a.synth_dcp.resolve())]
    else:argv=[a.vivado,'-mode','batch','-source',str(HERE/'write_bitstream.tcl'),'-tclargs',str(a.routed_dcp.resolve()),str(a.output.resolve())]
    print(json.dumps({'command':argv,'executed':not a.dry_run},indent=2))
    if not a.dry_run:subprocess.run(argv,check=True)

if __name__=='__main__':main()
