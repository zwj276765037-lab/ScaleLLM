#!/usr/bin/env python3
"""Run the staged read-only JTAG probe; collect its receipt and logs locally."""
import base64
import datetime as dt
import json
from pathlib import Path
import subprocess

SOURCE = Path(__file__).resolve().parent
REMOTE = 'C:/Users/dell/ScaleLLM_board_validation/M006_GU_66a305348d30_20261025'


def main():
    out = SOURCE.parents[2] / 'experiment_results/board_validation/host_preflight' / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '_jtag')
    out.mkdir(parents=True,exist_ok=False)
    def call(script,label):
        (out/(label+'.ps1')).write_text(script,encoding='utf-8')
        argv=['ssh','-o','BatchMode=yes','hap-dell','powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()]
        result=subprocess.run(argv,capture_output=True,check=False)
        for suffix,data in [('stdout',result.stdout),('stderr',result.stderr)]:
            (out/(label+'.'+suffix+'.bin')).write_bytes(data)
            (out/(label+'.'+suffix+'.txt')).write_text(data.decode('utf-8-sig',errors='replace'),encoding='utf-8')
        (out/(label+'.exit.json')).write_text(json.dumps({'exit_code':result.returncode})+'\n')
        return result
    result=call("& '"+REMOTE+"/probe_jtag_checked.ps1'",'run')
    collection=call("$ErrorActionPreference='Stop';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);$p=Get-ChildItem -LiteralPath '"+REMOTE+"' -Directory -Filter 'jtag_probe_*' | Sort-Object Name | Select-Object -Last 1;$r=@(Get-ChildItem -LiteralPath $p.FullName -File | Where-Object {$_.Extension -in @('.txt','.log','.json')} | ForEach-Object {[ordered]@{name=$_.Name;content=[IO.File]::ReadAllText($_.FullName)}});[ordered]@{directory=$p.FullName;files=$r} | ConvertTo-Json -Depth 5 -Compress",'collect')
    if collection.returncode == 0:
        data=json.loads(collection.stdout.decode('utf-8-sig'))
        (out/'collected.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        for f in data['files']:
            content=f['content'] or ''
            if isinstance(content,dict): content=content.get('value','')
            (out/f['name']).write_text(content,encoding='utf-8')
    print(json.dumps({'evidence':str(out),'probe_exit':result.returncode,'collection_exit':collection.returncode},indent=2))


if __name__=='__main__':main()
