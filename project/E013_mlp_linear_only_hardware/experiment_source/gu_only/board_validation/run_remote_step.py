#!/usr/bin/env python3
"""Run an explicitly selected board operation and retain complete evidence.

The caller is responsible for the active experiment's operation authorization.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import zlib

SOURCE=Path(__file__).resolve().parent
EVIDENCE=SOURCE.parents[2]/'experiment_results/board_validation'


def remote(script, directory, label):
    (directory/(label+'.ps1')).write_text(script,encoding='utf-8')
    c=zlib.compressobj(9,wbits=-15);payload=base64.b64encode(c.compress(script.encode('utf-8'))+c.flush()).decode()
    wrapper="$b=[Convert]::FromBase64String('"+payload+"');$m=New-Object IO.MemoryStream(,$b);$d=New-Object IO.Compression.DeflateStream($m,[IO.Compression.CompressionMode]::Decompress);$r=New-Object IO.StreamReader($d,[Text.Encoding]::UTF8);& ([ScriptBlock]::Create($r.ReadToEnd()))"
    argv=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','hap-dell','powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(wrapper.encode('utf-16le')).decode()]
    started=dt.datetime.now(dt.timezone.utc).isoformat()
    (directory/(label+'.started.json')).write_text(json.dumps({'started_utc':started,'script_sha256':hashlib.sha256(script.encode('utf-8')).hexdigest(),'host':'hap-dell','operation_script':label},indent=2)+'\n')
    result=subprocess.run(argv,capture_output=True,check=False)
    for suffix,data in [('stdout',result.stdout),('stderr',result.stderr)]:
        (directory/(label+'.'+suffix+'.bin')).write_bytes(data)
        (directory/(label+'.'+suffix+'.txt')).write_text(data.decode('utf-8-sig',errors='replace'),encoding='utf-8')
    (directory/(label+'.exit.json')).write_text(json.dumps({'exit_code':result.returncode,'ended_utc':dt.datetime.now(dt.timezone.utc).isoformat()})+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step',choices=['program','collect_program'])
    args=parser.parse_args()
    directory=EVIDENCE/('AT_'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'_'+args.step)
    directory.mkdir(parents=True,exist_ok=False)
    print(json.dumps({'evidence':str(directory),'execution_state':'running'}),flush=True)
    if args.step=='program':
        result=remote((SOURCE/'program_and_probe.ps1').read_text(),directory,'program_and_probe')
        try:
            receipt=json.loads(result.stdout.decode('utf-8-sig'))
            (directory/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        except ValueError:receipt=None
        print(json.dumps({'exit_code':result.returncode,'receipt':receipt},ensure_ascii=False,indent=2))
    else:
        script="[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);$p=Get-ChildItem -LiteralPath 'C:/Users/dell/ScaleLLM_board_validation/M006_GU_66a305348d30_20261025' -Directory -Filter 'program_*' | Sort-Object Name | Select-Object -Last 1;[ordered]@{directory=$p.FullName;files=@(Get-ChildItem -LiteralPath $p.FullName -File | ForEach-Object {[ordered]@{name=$_.Name;content=[IO.File]::ReadAllText($_.FullName)}});processes=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match '^(hw_server|vivado|cs_server)(\\.exe)?$'}|Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine);listeners=@(Get-NetTCPConnection -State Listen -LocalPort 33121 -ErrorAction SilentlyContinue|Select-Object LocalPort,OwningProcess)}|ConvertTo-Json -Depth 6 -Compress"
        result=remote(script,directory,'collect_program')
        if result.returncode==0:
            d=json.loads(result.stdout.decode('utf-8-sig'))
            for f in d['files']:(directory/f['name']).write_text(f['content'] or '',encoding='utf-8')
            (directory/'collection.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'remote':d['directory'],'processes':d['processes'],'listeners':d['listeners']}))


if __name__=='__main__':main()
