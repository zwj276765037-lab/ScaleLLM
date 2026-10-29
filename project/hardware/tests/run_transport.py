#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the two final reader protocol regressions with installed Vivado XSim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import signal
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"deploy/final"))
from build_hardware import mem_available, process_tree, GIB

HW=Path(__file__).resolve().parents[1]
CASES=('hap_axi512_weight_credit','hap_attention_shared_read_credit')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vivado',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True)
    a=p.parse_args();work=a.work.resolve()
    if work.exists():raise FileExistsError('Use a new output directory')
    bins=a.vivado.resolve().parent
    for name in ('xvlog','xelab','xsim'):
        if not (bins/name).is_file():raise FileNotFoundError(bins/name)
    work.mkdir(parents=True);results=[]
    os.sched_setaffinity(0,{0,1,2,3})
    start=time.monotonic()
    for case in CASES:
        out=work/case;out.mkdir()
        manifest=HW/'tb'/(case+'.list');tb=HW/'tb'/(case+'_tb.sv')
        sources=[HW/line.strip() for line in manifest.read_text().splitlines() if line.strip()]
        glbl=bins.parent/'data/verilog/src/glbl.v'
        inputs=[manifest,tb,glbl,*sources]
        cmds=[['xvlog','-sv','-L','xpm','-L','unisims_ver',*map(str,sources),str(tb),str(glbl)],
              ['xelab','-mt','4','-L','xpm','-L','unisims_ver',case+'_tb','glbl','-s','simulation'],
              ['xsim','simulation','-runall']]
        for cmd in cmds:
            with (out/(cmd[0]+'.log')).open('w') as log:
                if mem_available()<64*GIB:raise RuntimeError('Available memory below 64 GiB')
                proc=subprocess.Popen([str(bins/cmd[0]),*cmd[1:]],cwd=out,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                began=time.monotonic();peak=0
                while proc.poll() is None:
                    peak=max(peak,process_tree(proc.pid))
                    if time.monotonic()-began>300 or peak>8*GIB or mem_available()<64*GIB:
                        os.killpg(proc.pid,signal.SIGTERM)
                        try:proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                        raise RuntimeError('Simulation resource limit')
                    time.sleep(0.5)
                if proc.returncode:raise RuntimeError(cmd[0]+' failed: '+str(proc.returncode))
        logs='\n'.join((out/(name+'.log')).read_text() for name in ('xvlog','xelab','xsim'))
        if re.search(r'(?m)^(?:ERROR|FATAL|FAIL)\b',logs):raise RuntimeError('Simulator error in '+case)
        if logs.splitlines().count('HARDWARE_AGENT_SIM_PASS')!=1:raise RuntimeError('Missing unique self-check pass marker: '+case)
        results.append(dict(case=case,status='PASS',input_sha256={str(f.relative_to(HW)) if f.is_relative_to(HW) else 'vivado/glbl.v':hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs},coverage=[line for line in logs.splitlines() if 'COVERAGE' in line]))
    result=dict(schema='scalellm_final_transport_tests_v1',elapsed_seconds=round(time.monotonic()-start,3),tests=results)
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
