#!/usr/bin/env python3
"""Launch one explicit native pilot or idle/load/idle measurement on Dell."""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

SOURCE=Path(__file__).resolve().parent;BOARD=SOURCE.parent
sys.path.insert(0,str(BOARD))
from run_remote_step import remote


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('kind',choices=['pilot','formal']);parser.add_argument('--epoch-base',type=int,required=True);parser.add_argument('--command-base',type=int,required=True);parser.add_argument('--request-id',type=int,required=True);parser.add_argument('--poll-s',type=float,default=0);args=parser.parse_args()
    root=BOARD.parents[2]/'experiment_results/board_validation/power_performance'
    stage=json.loads((root/'current_native_stage.json').read_text());target=stage['remote']
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ');out=root/'attempts'/('AT_'+stamp+'_native_'+args.kind);out.mkdir(parents=True)
    logdir=target+'/orchestration_'+stamp;result=target+'/native_'+stamp
    warmup=2;measured=2 if args.kind=='pilot' else 20;duration=0 if args.kind=='pilot' else 15
    command=[target+'/native_resident_gu.py','--bundle',target,'--abi',target+'/abi_gu_only.json','--provenance',target+'/provenance.json','--result',result,'--epoch-base',str(args.epoch_base),'--command-base',str(args.command_base),'--request-id',str(args.request_id),'--warmup',str(warmup),'--measured',str(measured),'--poll-s',str(args.poll_s),'--load-seconds',str(duration),'--idle-before',str(duration),'--idle-after',str(duration),'--max-commands','4000']
    launch={'stage':stage,'kind':args.kind,'windows_python_arguments':command,'logdir':logdir,'result':result,'idle_load_idle_seconds':[duration]*3,'sampler_samples':85 if duration else 0,'sampler_interval_ms':500}
    (out/'launch.json').write_text(json.dumps(launch,indent=2)+'\n');print(json.dumps({'evidence':str(out),'kind':args.kind,'execution_state':'launching'}),flush=True)
    # Every supplied token is a generated private path or a typed numeric CLI
    # value. No user command text or shell expansion is interpolated here.
    ps="$ErrorActionPreference='Stop';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);New-Item -ItemType Directory -Path '"+logdir+"' -ErrorAction Stop|Out-Null;$r=[ordered]@{started_utc=[DateTime]::UtcNow.ToString('o');native_pid=$null;sampler_pid=$null;native_exit=$null;sampler_exit=$null;result='"+result+"';logdir='"+logdir+"'};$sampler=$null;"
    if duration:
        sampler_args='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File '+target+'/sample_power_timed.ps1 -SampleCount85 -IntervalMs500 -Label dense_active_128_native -EvidencePath '+logdir+'/telemetry.json'
        # Native PowerShell requires spaces between option and value.
        sampler_args=sampler_args.replace('-SampleCount85','-SampleCount 85').replace('-IntervalMs500','-IntervalMs 500')
        ps+="$sampler=Start-Process -FilePath 'C:/Windows/SysWOW64/WindowsPowerShell/v1.0/powershell.exe' -ArgumentList '"+sampler_args+"' -WorkingDirectory '"+target+"' -RedirectStandardOutput '"+logdir+"/sampler.stdout.txt' -RedirectStandardError '"+logdir+"/sampler.stderr.txt' -WindowStyle Hidden -PassThru;$samplerHandle=$sampler.Handle;$r.sampler_pid=$sampler.Id;$r.sampler_created_utc=$sampler.StartTime.ToUniversalTime().ToString('o');"
    ps+="$native=Start-Process -FilePath 'D:/software/Anaconda3/python.exe' -ArgumentList '"+' '.join(command)+"' -WorkingDirectory '"+target+"' -RedirectStandardOutput '"+logdir+"/native.stdout.txt' -RedirectStandardError '"+logdir+"/native.stderr.txt' -WindowStyle Hidden -PassThru;$nativeHandle=$native.Handle;$r.native_pid=$native.Id;$r.native_created_utc=$native.StartTime.ToUniversalTime().ToString('o');$r|ConvertTo-Json|Set-Content -LiteralPath '"+logdir+"/started.json' -Encoding UTF8;$native.WaitForExit();$native.Refresh();$r.native_exit=$native.ExitCode;if($sampler){$sampler.WaitForExit();$sampler.Refresh();$r.sampler_exit=$sampler.ExitCode};$r.ended_utc=[DateTime]::UtcNow.ToString('o');$r|ConvertTo-Json|Set-Content -LiteralPath '"+logdir+"/orchestration.json' -Encoding UTF8;$r|ConvertTo-Json -Compress"
    r=remote(ps,out,'run');print('REMOTE_EXIT',r.returncode,flush=True)
    if r.returncode==0:
        observation=json.loads(r.stdout.decode('utf-8-sig'));(out/'orchestration.json').write_text(json.dumps(observation,indent=2)+'\n');print(json.dumps(observation),flush=True)
        for remote_path,label in [(logdir,'orchestration'),(result,'native')]:
            local=out/label;local.mkdir()
            cp=subprocess.run(['scp','-r','-o','BatchMode=yes','hap-dell:'+remote_path+'/.',str(local)],capture_output=True)
            (out/(label+'.scp.stdout.txt')).write_bytes(cp.stdout);(out/(label+'.scp.stderr.txt')).write_bytes(cp.stderr)
            if cp.returncode:raise RuntimeError('Failed to collect'+label)
        receipt=json.loads((out/'native/receipt.json').read_text())
        print(json.dumps({'verdict':receipt['verdict'],'measured_commands':receipt.get('measured_commands'),'receipt':str(out/'native/receipt.json')},indent=2))
        if observation['native_exit']!=0 or (duration and observation['sampler_exit']!=0):raise SystemExit(1)
    else:
        print(r.stderr.decode('utf-8',errors='replace')[-3000:]);raise SystemExit(1)


if __name__=='__main__':main()
