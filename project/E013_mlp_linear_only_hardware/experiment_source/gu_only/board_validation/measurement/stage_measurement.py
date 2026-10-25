#!/usr/bin/env python3
"""Stage a native measurement helper against a proven resident bundle."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SOURCE=Path(__file__).resolve().parent
BOARD=SOURCE.parent
sys.path.insert(0,str(BOARD))
from run_remote_step import remote


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--prior',type=Path,required=True);args=parser.parse_args()
    root=next(p for p in SOURCE.parents if (p/'project/hardware/source/mlp_linear/abi_gu_only.json').is_file())
    resultroot=BOARD.parents[2]/'experiment_results/board_validation/power_performance'
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');out=resultroot/'attempts'/('AT_'+stamp+'_native_stage');out.mkdir(parents=True)
    receipt=json.loads((args.prior/'receipt.json').read_text());stage=json.loads((args.prior/'csr_after_stage.json').read_text())
    assert receipt['verdict']=='PASS' and receipt['layer_released'] and receipt['retained_layer_lease'] is None
    assert len(receipt['cohorts'])==2 and all(x['verdict']=='PASS' and x['acked'] for x in receipt['cohorts'])
    assert receipt['bundle']==str(args.bundle.resolve())
    provenance={'original_backend_two_cohorts_pass_released':True,'bundle_manifest_sha256':sha(args.bundle/'manifest.json'),'original_backend_attempt':str(args.prior.resolve()),'original_backend_receipt_sha256':sha(args.prior/'receipt.json'),'original_epoch':receipt['epoch'],'metadata_generation':receipt['metadata_generation'],'metadata_bank':stage['0x14c']&1,'metadata_status_after_stage':stage['0x14c'],'original_output_sha256':[x['output_sha256'] for x in receipt['cohorts']],'bit_sha256':'66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47'}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    target='C:/Users/dell/ScaleLLM_board_validation/M006_GU_66a305348d30_20261025/native_measurement_'+stamp
    r=remote("$ErrorActionPreference='Stop';New-Item -ItemType Directory -Path '"+target+"' -ErrorAction Stop|Out-Null",out,'mkdir');assert r.returncode==0
    files=[SOURCE/'native_resident_gu.py',BOARD/'scalellm_windows_xdma.py',SOURCE/'sample_power_timed.ps1',root/'project/hardware/source/mlp_linear/abi_gu_only.json',args.bundle/'manifest.json',args.bundle/'input_rec576.bin',args.bundle/'gold_gu_s24.bin',out/'provenance.json']
    argv=['scp','-o','BatchMode=yes']+[str(x) for x in files]+['hap-dell:'+target+'/']
    r=subprocess.run(argv,capture_output=True);(out/'scp.stdout.txt').write_bytes(r.stdout);(out/'scp.stderr.txt').write_bytes(r.stderr);assert r.returncode==0
    script="[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);$p='"+target+"';$errors=$null;$tokens=$null;[Management.Automation.Language.Parser]::ParseFile(($p+'/sample_power_timed.ps1'),[ref]$tokens,[ref]$errors)|Out-Null;& 'D:/software/Anaconda3/python.exe' -m py_compile ($p+'/native_resident_gu.py') ($p+'/scalellm_windows_xdma.py');$compile=$LASTEXITCODE;[ordered]@{native_compile_exit=$compile;sampler_parse_errors=@($errors|ForEach-Object {$_.Message});files=@(Get-ChildItem -LiteralPath $p -File|ForEach-Object {[ordered]@{name=$_.Name;size=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()}})}|ConvertTo-Json -Depth 5 -Compress"
    r=remote(script,out,'verify');assert r.returncode==0;verified=json.loads(r.stdout.decode('utf-8-sig'));assert verified['native_compile_exit']==0 and not verified['sampler_parse_errors']
    local={x.name:{'size':x.stat().st_size,'sha256':sha(x)} for x in files}
    for x in verified['files']:assert local[x['name']]=={'size':x['size'],'sha256':x['sha256']}
    result={'remote':target,'bundle':str(args.bundle.resolve()),'provenance':provenance,'files':verified['files'],'stage_attempt':str(out)}
    (out/'stage.json').write_text(json.dumps(result,indent=2)+'\n');(resultroot/'current_native_stage.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
