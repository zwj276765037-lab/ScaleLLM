# Dell read-only pilot. The controller chooses when to run this entry.
param(
    [Parameter(Mandatory=$true)][string]$StageRoot,
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [string]$RuntimeRoot = 'D:/ScaleLLM_final_model/power_portable_cpu_20261029_001/official_runtime',
    [ValidateRange(10,300)][int]$DurationSeconds = 60,
    [ValidateRange(0,60000)][int]$TargetPeriodMs = 0,
    [ValidateRange(1,10000)][int]$MinimumSweeps = 30
)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
if (-not [IO.Path]::IsPathRooted($OutputDir) -or (Test-Path -LiteralPath $OutputDir)) {
    throw 'OutputDir must be absolute and new'
}
$cfg=Get-Content -LiteralPath (Join-Path $StageRoot 'power_config.json') -Raw | ConvertFrom-Json
$sampler=Join-Path $PSScriptRoot 'kv128_sevenrail_sampler.ps1'
$manifest=Join-Path $PSScriptRoot 'powertool_runtime_manifest.json'
foreach ($path in @($sampler,$manifest)) { if (-not (Test-Path -LiteralPath $path)) { throw ('Missing sampler dependency: '+$path) } }
$expectedBit='5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7'
$actualBit=(Get-FileHash -LiteralPath ([string]$cfg.bit_path) -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualBit -ne $expectedBit) { throw 'Published bit file identity differs; pilot stopped' }
$lock=$null;$child=$null;$birth=$null;$start=[DateTime]::UtcNow
$receipt=[ordered]@{schema='scalellm_kv128_sevenrail_probe_v1';status='RUNNING';
    started_utc=$start.ToString('o');host=[Environment]::MachineName;
    boot_utc=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o');
    bit_sha256=$actualBit;
    sampler_sha256=(Get-FileHash -LiteralPath $sampler -Algorithm SHA256).Hash.ToLowerInvariant();
    manifest_sha256=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant();
    qpc_frequency=[Diagnostics.Stopwatch]::Frequency;cpu_mask=255;
    wall_limit_s=$DurationSeconds+50;sampler_max_seconds=$DurationSeconds;
    target_period_ms=$TargetPeriodMs;minimum_sweeps=$MinimumSweeps;
    child_pid=$null;child_birth=$null;child_exit_code=$null;
    stop_reason=$null;error=$null;lease_released=$false;survivors=@()}
function Save { [IO.File]::WriteAllText((Join-Path $OutputDir 'receipt.json'),($receipt|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false))) }
function Birth([int]$id) {
    $p=Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if ($p) { return $p.CreationDate.ToUniversalTime().ToString('o') }
    return $null
}
New-Item -ItemType Directory -Path $OutputDir -ErrorAction Stop | Out-Null
try {
    . (Join-Path $PSScriptRoot 'ownership.ps1')
    $externalOwner=Assert-BoardOwner $StageRoot
    $receipt.external_board_owner_pid=$externalOwner.owner_pid
    $receipt.lease_managed_externally=$true
    $other=@(Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match '^(vivado|hw_server|cs_server|python|pythonw|MaximDigitalPower)(\.exe)?$' -or
        ($_.ProcessId -ne $PID -and $_.Name -match '^powershell(\.exe)?$' -and
         $_.CommandLine -match 'sample_power|command_active_(pilot|full|sampler)|pmbus_v2_(probe|pilot|sampler)|kv128_(capture|pmbus_sampler|sevenrail)')
    })
    if ($other.Count) { throw 'Existing board/tool owner; pilot did not take over' }
    $env:SCALELLM_BOOT_UTC=$receipt.boot_utc
    $env:SCALELLM_RUN_ID=('kv128_sevenrail_probe_'+$start.ToString('yyyyMMddTHHmmssZ'))
    $receipt.run_id=$env:SCALELLM_RUN_ID;Save
    $ps32=Join-Path $env:WINDIR 'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
    $args=@('-NoProfile','-NonInteractive','-File',$sampler,
        '-RuntimeRoot',$RuntimeRoot,'-ExpectedAdapterSerial',[string]$cfg.adapter_serial,
        '-EvidencePath',(Join-Path $OutputDir 'telemetry.json'),
        '-JsonlPath',(Join-Path $OutputDir 'telemetry.jsonl'),
        '-ReadyPath',(Join-Path $OutputDir 'sampler.ready.json'),
        '-StopFile',(Join-Path $OutputDir 'sampler.stop'),
        '-MaxSweeps','10000','-MaxSeconds',([string]$DurationSeconds),
        '-TargetPeriodMs',([string]$TargetPeriodMs),'-IntervalMs','0')
    $child=Start-Process -FilePath $ps32 -ArgumentList $args -WorkingDirectory $OutputDir `
        -RedirectStandardOutput (Join-Path $OutputDir 'sampler.stdout.txt') `
        -RedirectStandardError (Join-Path $OutputDir 'sampler.stderr.txt') -PassThru
    $childHandle=$child.Handle;$birth=Birth $child.Id
    if (-not $birth) { throw 'Sampler child lacks process birth identity' }
    $child.ProcessorAffinity=[IntPtr]255;$child.PriorityClass='BelowNormal'
    $receipt.child_pid=$child.Id;$receipt.child_birth=$birth;Save
    $ready=Join-Path $OutputDir 'sampler.ready.json'
    while (-not (Test-Path -LiteralPath $ready) -and -not $child.HasExited) {
        if (([DateTime]::UtcNow-$start).TotalSeconds -ge 30) {
            $receipt.stop_reason='READY_TIMEOUT';[IO.File]::WriteAllText((Join-Path $OutputDir 'sampler.stop'),'ready-timeout')
            throw 'First complete seven-rail sweep not ready in 30 seconds'
        }
        Start-Sleep -Milliseconds 200;$child.Refresh()
    }
    if (-not (Test-Path -LiteralPath $ready)) { throw 'Sampler exited before first complete seven-rail sweep' }
    while (-not $child.HasExited) {
        if (([DateTime]::UtcNow-$start).TotalSeconds -ge $DurationSeconds+40) {
            $receipt.stop_reason='PILOT_WALL_LIMIT';[IO.File]::WriteAllText((Join-Path $OutputDir 'sampler.stop'),'pilot-wall-limit')
            if (-not $child.WaitForExit(10000)) { throw 'Sampler exceeded pilot wall limit' }
        }
        Start-Sleep -Milliseconds 200;$child.Refresh()
    }
    $child.WaitForExit();$child.Refresh();$receipt.child_exit_code=$child.ExitCode
    $meta=Get-Content -LiteralPath (Join-Path $OutputDir 'telemetry.json') -Raw | ConvertFrom-Json
    $receipt.complete_sweeps=$meta.complete_sweeps
    $receipt.complete_rail_points=$meta.complete_rail_points
    $receipt.read_errors=$meta.read_errors
    if ($child.ExitCode -ne 0 -or -not $meta.pass -or $meta.complete_sweeps -lt $MinimumSweeps -or
        $meta.complete_rail_points -ne 7*$meta.complete_sweeps -or $meta.read_errors -ne 0 -or
        $meta.configuration.Count -ne 7 -or $meta.run_id -ne $receipt.run_id -or
        $meta.boot_utc -ne $receipt.boot_utc -or $meta.qpc_frequency -ne $receipt.qpc_frequency -or
        $meta.target_period_ms -ne $TargetPeriodMs) {
        throw 'Pilot sampling/data identity gate failed'
    }
    if ($TargetPeriodMs -gt 0) {
        $bus=0;$points=0;$sweeps=0;$lastReadId=0
        foreach ($line in [IO.File]::ReadLines((Join-Path $OutputDir 'telemetry.jsonl'))) {
            $item=$line|ConvertFrom-Json
            if ($item.record -eq 'bus_read') {
                $bus++
                if ($item.read_id -ne $lastReadId+1 -or $item.native_ack_status -ne 'NOT_EXPOSED_BY_OFFICIAL_API') {
                    throw 'Immediate bus-read sequence/ACK disclosure differs'
                }
                $lastReadId=$item.read_id
            } elseif ($item.record -eq 'rail_point') { $points++ }
            elseif ($item.record -eq 'sweep') { $sweeps++ }
        }
        $cal=0;$calibration=@()
        foreach ($rail in $meta.configuration) {
            foreach ($read in $rail.calibration) {
                $cal++
                $calibration+=@{address=$rail.address;command=$read.command;
                    api_status=$read.api_status;raw_hex=$read.raw_hex;error=$read.error}
            }
        }
        if ($points -ne $meta.complete_rail_points -or $sweeps -ne $meta.complete_sweeps -or
            $bus -ne 17*$meta.complete_sweeps+7+$cal) {
            throw 'Immediate bus-read/sweep/point counts differ'
        }
        $receipt.bus_reads=$bus;$receipt.calibration=$calibration
        $receipt.missed_deadlines=$meta.missed_deadlines
    }
    $receipt.status='COMPLETE'
} catch {
    $receipt.status='FAIL';$receipt.error=$_.Exception.Message
} finally {
    if ($child -and (Birth $child.Id) -eq $birth) {
        [IO.File]::WriteAllText((Join-Path $OutputDir 'sampler.stop'),'owner-stop')
        if (-not $child.WaitForExit(10000)) { Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue }
    }
    if ($child -and (Birth $child.Id) -eq $birth) { $receipt.survivors+=,$child.Id }
    if ($lock) { $lock.Dispose();$receipt.lease_released=$true }
    $receipt.finished_utc=[DateTime]::UtcNow.ToString('o')
    $receipt.wall_seconds=([DateTime]::UtcNow-$start).TotalSeconds
    Save
}
@{status=$receipt.status;result=$OutputDir;error=$receipt.error}|ConvertTo-Json -Compress
if ($receipt.status -ne 'COMPLETE' -or $receipt.survivors.Count) { exit 1 }
