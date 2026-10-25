#!/usr/bin/env python3
"""Create a new Dell staging directory and copy the identified engineering bit.

This performs filesystem preparation only. It does not invoke Hardware Manager.
"""
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[4]
BIT = ROOT / 'project/hardware/vivado/reports/m006_gu_AT003_preliminary_bitstream/native_output/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit'
EXPECTED = '66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47'
REMOTE = 'C:/Users/dell/ScaleLLM_board_validation/M006_GU_66a305348d30_20261025'
EVIDENCE = SOURCE.parents[2] / 'experiment_results/board_validation/host_preflight'


def main():
    if BIT.stat().st_size != 80159259 or hashlib.sha256(BIT.read_bytes()).hexdigest() != EXPECTED:
        raise RuntimeError('Local bit identity mismatch')
    out = EVIDENCE / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '_staging')
    out.mkdir(parents=True, exist_ok=False)
    commands = []
    def remote(script, label):
        command = ['ssh', '-o', 'BatchMode=yes', 'hap-dell', 'powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', base64.b64encode(script.encode('utf-16le')).decode()]
        result = subprocess.run(command, capture_output=True, check=False)
        for name,data in [('stdout',result.stdout),('stderr',result.stderr)]:
            (out/(label+'.'+name+'.bin')).write_bytes(data)
            (out/(label+'.'+name+'.txt')).write_text(data.decode('utf-8-sig',errors='replace'),encoding='utf-8')
        commands.append({'label':label,'exit_code':result.returncode,'powershell':script})
        if result.returncode: raise RuntimeError(label+' failed')
        return result.stdout.decode('utf-8-sig')
    try:
        remote("$ErrorActionPreference='Stop';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);$p='"+REMOTE+"';if(Test-Path -LiteralPath $p){throw 'Staging directory exists; refusing to overwrite'};New-Item -ItemType Directory -Path $p | Out-Null;Write-Output $p",'mkdir')
        files = [BIT] + [SOURCE/n for n in ['hw_common.tcl','probe_jtag.tcl','program_sram.tcl','probe_jtag.ps1']]
        argv = ['scp','-o','BatchMode=yes'] + [str(p) for p in files] + ['hap-dell:'+REMOTE+'/']
        cp = subprocess.run(argv,capture_output=True,check=False)
        (out/'scp.stdout.txt').write_text(cp.stdout.decode('utf-8',errors='replace'))
        (out/'scp.stderr.txt').write_text(cp.stderr.decode('utf-8',errors='replace'))
        commands.append({'label':'scp','argv':argv,'exit_code':cp.returncode})
        if cp.returncode: raise RuntimeError('SCP failed; no overwrite retry is automatic')
        verification=remote("$ErrorActionPreference='Stop';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);$p='"+REMOTE+"';$files=@(Get-ChildItem -LiteralPath $p -File | ForEach-Object {[ordered]@{name=$_.Name;bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()}});$b=@($files | Where-Object {$_.name -eq '"+BIT.name+"'});if($b.Count -ne 1 -or $b[0].bytes -ne 80159259 -or $b[0].sha256 -ne '"+EXPECTED+"'){throw 'Remote bit identity mismatch'};$files | ConvertTo-Json -Depth 5 -Compress",'verify')
        verified=json.loads(verification)
        local = {p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}
        for f in verified:
            if local[f['name']] != {'bytes':f['bytes'],'sha256':f['sha256']}: raise RuntimeError('Staged file identity mismatch: '+f['name'])
        receipt={'schema':1,'remote':REMOTE,'files':verified,'local_files':local,'status':'STAGED_VERIFIED','hardware_actions':[]}
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({'evidence':str(out),**receipt},indent=2))
    finally:
        (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')


if __name__=='__main__':
    sys.exit(main())
