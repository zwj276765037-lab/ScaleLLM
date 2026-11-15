import base64
import json
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parents[1]
golden_path = Path.cwd() / "docs/evidence/inference_chat16/outputs.json"
golden = {entry["slot"]: entry["generated_token_ids"] for entry in json.loads(golden_path.read_text())}
powershell = r'''$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);$r='D:\ScaleLLM_final_model\dsp_all_board_20261115_001';$run=Get-Content -LiteralPath ($r+'\inference\run.json') -Raw|ConvertFrom-Json;$owner=Get-Content -LiteralPath ($r+'\board_owner.json') -Raw|ConvertFrom-Json;$launch=Get-Content -LiteralPath ($r+'\environment\inference_launch.json') -Raw|ConvertFrom-Json;$tree=Get-Content -LiteralPath ($r+'\environment\inference_owned_tree.json') -Raw|ConvertFrom-Json;$last=Get-Content -LiteralPath ($r+'\inference\progress.jsonl') -Tail 1|ConvertFrom-Json;$native=$null;if(Test-Path ($r+'\environment\inference_process_receipt.json')){$native=Get-Content -LiteralPath ($r+'\environment\inference_process_receipt.json') -Raw|ConvertFrom-Json};[ordered]@{utc=[DateTime]::UtcNow.ToString('o');execution=$run.execution;error=$run.error;rounds=$run.steps.Count;commands=$run.receipts.Count;slots=$run.slots;eta=$run.eta;launch_pid=$launch.pid;launch_birth=($tree|Where-Object pid -eq $launch.pid|Select-Object -ExpandProperty birth);guardian=($owner|Select-Object state,updated_utc,active_owned_pids,peak_owned_rss_bytes,minimum_available_bytes,minimum_disk_free_bytes,stop_reason);last_event=($last|Select-Object event,elapsed_seconds,command_id,layer,opcode);native=$native;stderr_bytes=(Get-Item -LiteralPath ($r+'\environment\inference.stderr.txt')).Length}|ConvertTo-Json -Depth 8 -Compress'''
encoded = base64.b64encode(powershell.encode("utf-16le")).decode()
command = "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + encoded
last_round = -1
while True:
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                             "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
                             "hap-dell", command], capture_output=True)
    try:
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
        state = json.loads(result.stdout.decode("utf-8-sig"))
        if state["execution"] not in ("RUNNING", "COMPLETE", "FAIL"):
            raise RuntimeError("Transient incomplete run snapshot, retry on next poll")
        native = state.get("native")
        if native and (native["pid"] != state["launch_pid"] or native["birth"] != state["launch_birth"]):
            state["previous_attempt_native"] = native
            state["native"] = None
        checked = 0
        mismatches = []
        for slot, entry in enumerate(state.get("slots") or []):
            actual = entry["generated"]
            checked += len(actual)
            if actual != golden[slot][:len(actual)]:
                mismatches.append(slot)
        state["prefix_check"] = dict(status="FAIL" if mismatches else ("PASS" if checked else "NO_GENERATED_TOKENS"),
                                    tokens_checked=checked, mismatch_slots=mismatches)
        with (root / "environment/inference_monitor.jsonl").open("a") as stream:
            stream.write(json.dumps(state) + "\n")
        if state["rounds"] != last_round or mismatches or state["execution"] != "RUNNING":
            print(json.dumps({key: state[key] for key in ("utc", "execution", "rounds", "commands", "prefix_check", "stderr_bytes", "guardian")}), flush=True)
            last_round = state["rounds"]
        if mismatches or state["guardian"]["state"] != "LEASE_HELD":
            break
        if state["execution"] != "RUNNING" and state["native"]:
            break
    except Exception as error:
        print(json.dumps(dict(monitor_poll_error=str(error), utc_unix=time.time())), flush=True)
    time.sleep(60)
