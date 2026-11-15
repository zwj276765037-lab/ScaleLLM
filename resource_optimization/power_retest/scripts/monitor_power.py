import base64
import json
from pathlib import Path
import subprocess
import time

repo = Path(__file__).resolve().parents[3]
output = repo / "outputs/resource_optimization_power/environment/monitor.jsonl"
script = r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);$r='D:\ScaleLLM_final_model\dsp_all_power_20261115_001';$m=$r+'\main_001';$receipt=Get-Content -LiteralPath ($m+'\receipt.json') -Raw|ConvertFrom-Json;$phase=$null;$last=$null;$windows=@();$native=$null;try{$phase=Get-Content -LiteralPath ($m+'\phase.json') -Raw|ConvertFrom-Json}catch{};if(Test-Path ($m+'\workload\commands_summary.jsonl')){try{$last=Get-Content -LiteralPath ($m+'\workload\commands_summary.jsonl') -Tail 1|ConvertFrom-Json}catch{}};if(Test-Path ($m+'\workload\windows.jsonl')){foreach($line in [IO.File]::ReadLines($m+'\workload\windows.jsonl')){try{$windows+=($line|ConvertFrom-Json)}catch{}}};if(Test-Path ($r+'\environment\main_process_receipt.json')){$native=Get-Content -LiteralPath ($r+'\environment\main_process_receipt.json') -Raw|ConvertFrom-Json};$owner=Get-Content -LiteralPath ($r+'\board_owner.json') -Raw|ConvertFrom-Json;[ordered]@{utc=[DateTime]::UtcNow.ToString('o');state=$receipt.state;error=$receipt.error;sampler_pid=$receipt.sampler_pid;workload_pid=$receipt.workload_pid;sampler_exit_code=$receipt.sampler_exit_code;workload_exit_code=$receipt.workload_exit_code;phase=$phase;completed_windows=$windows.Count;windows=@($windows|Select-Object kind,repeat_id,start_ticks,end_ticks,completed_commands,status);last_command=($last|Select-Object command_id,layer,opcode,position,epoch);guardian=($owner|Select-Object state,updated_utc,active_owned_pids,peak_owned_rss_bytes,minimum_available_bytes,minimum_disk_free_bytes,stop_reason);native=$native;workload_stderr_bytes=(Get-Item -LiteralPath ($m+'\workload.stderr.txt')).Length;sampler_stderr_bytes=(Get-Item -LiteralPath ($m+'\sampler.stderr.txt')).Length}|ConvertTo-Json -Depth 7 -Compress'''
command = "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + base64.b64encode(script.encode("utf-16le")).decode()
while True:
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2", "hap-dell", command], capture_output=True)
    try:
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
        row = json.loads(result.stdout.decode("utf-8-sig"))
        if row["state"] is None:
            raise RuntimeError("Snapshot temporarily unavailable")
        with output.open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        phase = row.get("phase") or {}
        live = dict(observed_utc=row["utc"], state=row["state"], phase=phase.get("phase"),
                    kind=phase.get("block_id"), repeat_id=phase.get("repeat_id"),
                    completed_windows=row["completed_windows"], last_command=row["last_command"],
                    error=row.get("error"), workload_stderr_bytes=row["workload_stderr_bytes"],
                    sampler_stderr_bytes=row["sampler_stderr_bytes"],
                    still_running=row["state"] == "RUNNING", guardian_state=row["guardian"]["state"])
        live_path = repo / "outputs/resource_optimization_power/live_progress.json"
        temporary = live_path.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(live, indent=2) + "\n")
        temporary.replace(live_path)
        print(json.dumps({key: row[key] for key in ("utc", "state", "phase", "completed_windows", "last_command", "workload_stderr_bytes", "sampler_stderr_bytes")}), flush=True)
        if row["native"] is not None and row["state"] != "RUNNING":
            break
        if row["guardian"]["state"] != "LEASE_HELD":
            break
    except Exception as error:
        print(json.dumps({"read_only_monitor_error": str(error), "unix": time.time()}), flush=True)
    time.sleep(60)
