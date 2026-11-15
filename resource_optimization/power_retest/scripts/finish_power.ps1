$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$root='D:\ScaleLLM_final_model\dsp_all_power_20261115_001'
$encoding=New-Object Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'ownership.ps1')
$owner=Assert-BoardOwner $root
$main=Get-Content -LiteralPath (Join-Path $root 'main_001\receipt.json') -Raw|ConvertFrom-Json
$workload=Get-Content -LiteralPath (Join-Path $root 'main_001\workload\workload.json') -Raw|ConvertFrom-Json
$native=Get-Content -LiteralPath (Join-Path $root 'environment\main_process_receipt.json') -Raw|ConvertFrom-Json
if($main.state -ne 'CAPTURE_COMPLETE_WITH_LIMITS' -or $main.sampler_exit_code -ne 0 -or $main.workload_exit_code -ne 0 -or $native.exitcode -ne 0 -or $workload.status -ne 'COMPLETE_WITH_LIMITS' -or $workload.completed_windows -ne 12 -or -not $workload.handles_closed -or $main.stop_reason){throw 'Native collection or closure prerequisites failed'}
$tree=Get-Content -LiteralPath (Join-Path $root 'environment\main_owned_tree.json') -Raw|ConvertFrom-Json
$all=@(Get-CimInstance Win32_Process)
$survivors=@()
foreach($entry in $tree){$p=$all|Where-Object{[int]$_.ProcessId -eq [int]$entry.pid -and $_.CreationDate.ToUniversalTime().ToString('o') -eq $entry.birth}|Select-Object -First 1;if($p){$survivors+=$entry}}
$program=Get-Content -LiteralPath (Join-Path $root 'program\receipt.json') -Raw|ConvertFrom-Json
$server=Get-Content -LiteralPath (Join-Path $root 'program\hw_server_owner.json') -Raw|ConvertFrom-Json
foreach($entry in @(@{pid=$program.native_pid;birth=$program.native_birth},$server)){$p=$all|Where-Object{[int]$_.ProcessId -eq [int]$entry.pid -and $_.CreationDate.ToUniversalTime().ToString('o') -eq $entry.birth}|Select-Object -First 1;if($p){$survivors+=$entry}}
$services=@($all|Where-Object{$_.Name -match '^(vivado|hw_server|cs_server|MaximDigitalPower)\.exe$'}|ForEach-Object{[ordered]@{pid=[int]$_.ProcessId;parent_pid=[int]$_.ParentProcessId;name=$_.Name;birth=$_.CreationDate.ToUniversalTime().ToString('o');command=$_.CommandLine}})
[IO.File]::WriteAllText((Join-Path $root 'environment\owned_process_closure.json'),(@{survivors=$survivors;observed_hardware_services=$services;verified_utc=[DateTime]::UtcNow.ToString('o')}|ConvertTo-Json -Depth 7),$encoding)
if($survivors.Count){throw 'Owned collection/program process remains live'}
$expected='5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7'
if($program.status -ne 'PASS' -or $program.bit_sha256 -ne $expected -or $program.board_owner_pid -ne $owner.owner_pid -or (Get-FileHash -LiteralPath (Join-Path $root 'bitstream\ScaleLLM_Final_Decode16_80MHz.bit') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected){throw 'Current lease programming identity differs'}
$identity=Get-Content -LiteralPath (Join-Path $root 'parent_runtime_identity.json') -Raw|ConvertFrom-Json
$verified=[ordered]@{}
foreach($entry in $identity.candidate_files.PSObject.Properties){$path=Join-Path $root $entry.Name;$bytes=(Get-Item -LiteralPath $path).Length;$sha=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();if($bytes -ne $entry.Value.bytes -or $sha -ne $entry.Value.sha256){throw ('Runtime source changed '+$entry.Name)};$verified[$entry.Name]=@{bytes=$bytes;sha256=$sha}}
[IO.File]::WriteAllText((Join-Path $root 'environment\runtime_identity_after.json'),(@{status='PASS';file_count=$verified.Count;files=$verified}|ConvertTo-Json -Depth 7),$encoding)
$p=Start-Process -FilePath 'D:\ScaleLLM_inference\py312_20261025T042311\python\python.exe' -ArgumentList @((Join-Path $PSScriptRoot 'read_only_device.py')) -RedirectStandardOutput (Join-Path $root 'environment\final_identity.stdout.txt') -RedirectStandardError (Join-Path $root 'environment\final_identity.stderr.txt') -PassThru
$handle=$p.Handle;$p.WaitForExit();$p.Refresh();$code=[int]$p.ExitCode
[IO.File]::WriteAllText((Join-Path $root 'environment\final_identity.exitcode.txt'),[string]$code,$encoding)
if($code -ne 0){throw 'Final CSR identity/idle/error readback failed'}
[IO.File]::WriteAllText((Join-Path $root 'active_processes.json'),'[]',$encoding)
Start-Sleep -Seconds 3
$latest=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json
if($latest.state -ne 'LEASE_HELD' -or @($latest.active_owned_pids).Count -or $latest.stop_reason){throw 'Guardian is not clean before lease closure'}
[IO.File]::WriteAllText((Join-Path $root 'guardian.stop'),[DateTime]::UtcNow.ToString('o'),$encoding)
for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 500;$closed=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json;if($closed.state -eq 'CLOSED' -and $closed.lease_released){break}}
if($closed.state -ne 'CLOSED' -or -not $closed.lease_released){throw 'Board lease closure receipt unavailable'}
for($i=0;$i -lt 20;$i++){$g=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid) -ErrorAction SilentlyContinue;if(-not $g -or $g.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){break};Start-Sleep -Milliseconds 250}
if($g -and $g.CreationDate.ToUniversalTime().ToString('o') -eq $owner.owner_birth){throw 'Guardian did not exit after lease closure'}
$receipt=[ordered]@{schema='scalellm_dsp_power_stage_closure_v1';status='PASS';closed_utc=[DateTime]::UtcNow.ToString('o');bit_sha256=$expected;candidate_left_in_volatile_sram=$true;completed_windows=12;sampler_native_exitcode=$main.sampler_exit_code;workload_native_exitcode=$main.workload_exit_code;phase_launcher_native_exitcode=$native.exitcode;final_identity_exitcode=$code;handles_closed=$true;owned_survivors=@();runtime_verified_files=$verified.Count;guardian=$closed;strict_physical_active_mean_w=$null;whole_board_input_power_w=$null}
[IO.File]::WriteAllText((Join-Path $root 'closure.json'),($receipt|ConvertTo-Json -Depth 8),$encoding)
$receipt|ConvertTo-Json -Depth 8
