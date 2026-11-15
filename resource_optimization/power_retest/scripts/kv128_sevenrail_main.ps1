# Dell controller for the frozen read-only seven-rail sampler and KV128 workload.
# The inspection file is produced by the separate same-board read-only gate.
param(
    [Parameter(Mandatory=$true)][string]$StageRoot,
    [Parameter(Mandatory=$true)][string]$MainRun,
    [Parameter(Mandatory=$true)][string]$InspectionJson,
    [string]$ResumeCommandTrace='',
    [Parameter(Mandatory=$true)][string]$OutputDir,
    [int]$TargetPeriodMs=140,
    [string]$RuntimeRoot='D:/ScaleLLM_final_model/power_portable_cpu_20261029_001/official_runtime'
)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
if (-not [IO.Path]::IsPathRooted($OutputDir) -or (Test-Path -LiteralPath $OutputDir)) {
    throw 'OutputDir must be absolute and new'
}
$samplerScript=Join-Path $PSScriptRoot 'kv128_sevenrail_sampler.ps1'
$workloadScript=Join-Path $PSScriptRoot 'kv128_sevenrail_workload.py'
$traceScript=Join-Path $PSScriptRoot 'command_active_inference.py'
$manifest=Join-Path $PSScriptRoot 'powertool_runtime_manifest.json'
foreach ($path in @($samplerScript,$workloadScript,$traceScript,$manifest,$InspectionJson)) {
    if (-not (Test-Path -LiteralPath $path)) { throw ('Missing source or inspected state: '+$path) }
}
$traceSha=(Get-FileHash -LiteralPath $traceScript -Algorithm SHA256).Hash.ToLowerInvariant()
if ($traceSha -ne '892f551c6cedcbb5b30eb884f0935909684d7d1931d30a6fa8645377323b4ec1') {
    throw 'Sealed QPC command wrapper differs'
}
$cfg=Get-Content -LiteralPath (Join-Path $StageRoot 'power_config.json') -Raw | ConvertFrom-Json
$model=Get-Content -LiteralPath (Join-Path $StageRoot 'run_config.json') -Raw | ConvertFrom-Json
$bitSha=(Get-FileHash -LiteralPath ([string]$cfg.bit_path) -Algorithm SHA256).Hash.ToLowerInvariant()
if ($bitSha -ne '5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7') {
    throw 'Published bit file differs'
}
$start=[DateTime]::UtcNow
$boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
$env:SCALELLM_RUN_ID=('kv128_sevenrail_main_'+$start.ToString('yyyyMMddTHHmmssZ'))
$env:SCALELLM_BOOT_UTC=$boot
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$self=Get-Process -Id $PID;$self.ProcessorAffinity=[IntPtr]255;$self.PriorityClass='BelowNormal'
$receipt=[ordered]@{schema='scalellm_kv128_sevenrail_main_launcher_v1';state='RUNNING';
    run_id=$env:SCALELLM_RUN_ID;started_utc=$start.ToString('o');host=[Environment]::MachineName;
    boot_utc=$boot;bit_sha256=$bitSha;cpu_mask=255;rss_limit_bytes=8589934592;
    available_floor_bytes=2147483648;whole_wall_limit_s=$null;fixed_wall_time_termination=$false;
    workload_wall_limit_s=$null;sampler_max_seconds=0;target_sweep_period_ms=$TargetPeriodMs;
    sampler_script_sha256=(Get-FileHash -LiteralPath $samplerScript -Algorithm SHA256).Hash.ToLowerInvariant();
    workload_script_sha256=(Get-FileHash -LiteralPath $workloadScript -Algorithm SHA256).Hash.ToLowerInvariant();
    command_trace_script_sha256=$traceSha;
    manifest_sha256=(Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant();
    inspection_sha256=(Get-FileHash -LiteralPath $InspectionJson -Algorithm SHA256).Hash.ToLowerInvariant();
    resume_command_trace=$ResumeCommandTrace;
    resume_command_trace_sha256=$null;
    resume_receipt_sha256=$null;
    qpc_frequency=[Diagnostics.Stopwatch]::Frequency;operations=@();
    sampler_pid=$null;sampler_birth=$null;sampler_exit_code=$null;
    workload_pid=$null;workload_birth=$null;workload_exit_code=$null;
    peak_tree_rss_bytes=[long]0;minimum_available_bytes=[long]::MaxValue;
    stop_reason=$null;error=$null;lease_released=$false;survivors=@()}
$lock=$null;$sampler=$null;$samplerBirth=$null;$workload=$null;$workloadBirth=$null
$stopFile=Join-Path $OutputDir 'workload.stop'
$samplerStop=Join-Path $OutputDir 'sampler.stop'
function Save { [IO.File]::WriteAllText((Join-Path $OutputDir 'receipt.json'),($receipt|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false))) }
function Birth([int]$id) {
    $p=Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if ($p) { return $p.CreationDate.ToUniversalTime().ToString('o') }
    return $null
}
function Request-Stop([string]$reason) {
    if (-not $script:receipt.stop_reason) {
        $script:receipt.stop_reason=$reason
        [IO.File]::WriteAllText($script:stopFile,$reason)
        Save
    }
}
function Observe {
    $free=[long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1024
    $script:self.Refresh();$rss=[long]$script:self.WorkingSet64
    foreach ($child in @($script:sampler,$script:workload)) {
        if ($child -and -not $child.HasExited) { $child.Refresh();$rss+=[long]$child.WorkingSet64 }
    }
    $script:receipt.peak_tree_rss_bytes=[Math]::Max($rss,[long]$script:receipt.peak_tree_rss_bytes)
    $script:receipt.minimum_available_bytes=[Math]::Min($free,[long]$script:receipt.minimum_available_bytes)
    if ($rss -gt $script:receipt.rss_limit_bytes) { Request-Stop 'OWNED_RSS_LIMIT' }
    if ($free -lt $script:receipt.available_floor_bytes) { Request-Stop 'AVAILABLE_MEMORY_FLOOR' }
    if ((Get-PSDrive D).Free -lt 42949672960) { Request-Stop 'DISK_FLOOR' }
    if ($script:sampler -and $script:workload -and -not $script:workload.HasExited) {
        $script:sampler.Refresh()
        if ($script:sampler.HasExited) { Request-Stop 'SAMPLER_EXITED_DURING_WORKLOAD' }
        # The workload validates fresh sampler bus_read QPC evidence with a
        # strict 10-second same-clock gate. NTFS LastWriteTime is not a safe
        # clock for a concurrently appended file; process exit remains here.
    }
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
    if ($other.Count) { throw 'Existing board/tool owner; no takeover' }
    $inspection=Get-Content -LiteralPath $InspectionJson -Raw | ConvertFrom-Json
    $inspectedBoot=[DateTime]::Parse([string]$inspection.observed_boot_utc,
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
    $currentBoot=[DateTime]::Parse($boot,[Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
    $bootDrift=($currentBoot-$inspectedBoot).TotalSeconds
    $receipt.inspection_boot_drift_seconds=$bootDrift
    $receipt.inspection_boot_tolerance_seconds=10
    if ($inspection.status -ne 'PASS_WITH_LIMITS' -or
        [Math]::Abs($bootDrift) -gt 10 -or $inspection.bit_sha256 -ne $bitSha) {
        throw 'Read-only live inspection does not match this boot and published bit'
    }
    Save
    $ps32=Join-Path $env:WINDIR 'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
    $samplerArgs=@('-NoProfile','-NonInteractive','-File',$samplerScript,
        '-RuntimeRoot',$RuntimeRoot,'-ExpectedAdapterSerial',[string]$cfg.adapter_serial,
        '-EvidencePath',(Join-Path $OutputDir 'telemetry.json'),
        '-JsonlPath',(Join-Path $OutputDir 'telemetry.jsonl'),
        '-ReadyPath',(Join-Path $OutputDir 'sampler.ready.json'),
        '-StopFile',$samplerStop,'-PhasePath',(Join-Path $OutputDir 'phase.json'),
        '-TargetPeriodMs',([string]$TargetPeriodMs),'-MaxSweeps','0','-MaxSeconds','0')
    $sampler=Start-Process -FilePath $ps32 -ArgumentList $samplerArgs -WorkingDirectory $OutputDir `
        -RedirectStandardOutput (Join-Path $OutputDir 'sampler.stdout.txt') `
        -RedirectStandardError (Join-Path $OutputDir 'sampler.stderr.txt') -PassThru
    $samplerHandle=$sampler.Handle;$samplerBirth=Birth $sampler.Id
    if (-not $samplerBirth) { throw 'Sampler child lacks birth identity' }
    $sampler.ProcessorAffinity=[IntPtr]255;$sampler.PriorityClass='BelowNormal'
    $receipt.sampler_pid=$sampler.Id;$receipt.sampler_birth=$samplerBirth;Save
    $ready=Join-Path $OutputDir 'sampler.ready.json'
    while (-not (Test-Path -LiteralPath $ready) -and -not $sampler.HasExited) {
        Observe
        if (([DateTime]::UtcNow-$start).TotalSeconds -ge 30) { throw 'Sampler ready timeout' }
        Start-Sleep -Milliseconds 200;$sampler.Refresh()
    }
    if (-not (Test-Path -LiteralPath $ready)) { throw 'Sampler stopped before first complete sweep' }
    $receipt.sampler_ready=Get-Content -LiteralPath $ready -Raw | ConvertFrom-Json;Save
    $out=Join-Path $OutputDir 'workload'
    $windows=Join-Path $out 'windows.jsonl'
    $tracePath=Join-Path $OutputDir 'commands.jsonl'
    $args=@('-I',$traceScript,'--frozen-run',$workloadScript,
        '--command-trace',$tracePath,'run',
        '--main',$MainRun,'--runtime-root',$StageRoot,'--bit-file',[string]$cfg.bit_path,
        '--out',$out,'--inspection',$InspectionJson,
        '--artifacts',$model.manifests.'scalecode_manifest.json'.path,
        '--assets',$model.manifests.'host_assets/manifest.json'.path,
        '--sampler-jsonl',(Join-Path $OutputDir 'telemetry.jsonl'),
        '--sampler-ready',$ready,'--windows-jsonl',$windows,
        '--phase-path',(Join-Path $OutputDir 'phase.json'),
        '--stop-file',$stopFile)
    $workload=Start-Process -FilePath ([string]$cfg.python) -ArgumentList $args -WorkingDirectory $OutputDir `
        -RedirectStandardOutput (Join-Path $OutputDir 'workload.stdout.txt') `
        -RedirectStandardError (Join-Path $OutputDir 'workload.stderr.txt') -PassThru
    $workloadHandle=$workload.Handle;$workloadBirth=Birth $workload.Id
    if (-not $workloadBirth) { throw 'Workload child lacks birth identity' }
    $workload.ProcessorAffinity=[IntPtr]255;$workload.PriorityClass='BelowNormal'
    $receipt.workload_pid=$workload.Id;$receipt.workload_birth=$workloadBirth;Save
    while (-not $workload.HasExited) {
        Observe
        Start-Sleep -Milliseconds 1000;$workload.Refresh()
    }
    $workload.WaitForExit();$workload.Refresh();$receipt.workload_exit_code=$workload.ExitCode
    if ($workload.ExitCode -ne 0) { throw ('Workload exited '+$workload.ExitCode) }
    $run=Get-Content -LiteralPath (Join-Path $out 'workload.json') -Raw | ConvertFrom-Json
    if ($run.status -ne 'COMPLETE_WITH_LIMITS' -or $receipt.stop_reason) {
        throw 'KV128 workload completion/resource gate failed'
    }
    $receipt.workload_status=$run.status
    $traceClock=$null;$tracedCommands=0;$incompleteCommands=0;$firstCommandId=$null;$lastCommandId=$null
    foreach ($line in [IO.File]::ReadLines($tracePath)) {
        $item=$line | ConvertFrom-Json
        if ($item.record -eq 'clock') {
            if ($traceClock) { throw 'Duplicate QPC command clock' }
            $traceClock=$item
        } elseif ($item.record -eq 'command') {
            $tracedCommands++
            if ($item.trace_state -ne 'ACK_WRITTEN' -or
                $null -eq $item.first_done -or $null -eq $item.ack_write) { $incompleteCommands++ }
            if ($null -eq $firstCommandId) { $firstCommandId=$item.descriptor.command_id }
            $lastCommandId=$item.descriptor.command_id
        }
    }
    if (-not $traceClock -or $traceClock.schema -ne 'scalellm_command_qpc_v1' -or
        $traceClock.run_id -ne $receipt.run_id -or $traceClock.boot_utc -ne $boot -or
        $traceClock.qpc_frequency -ne $receipt.qpc_frequency -or
        $tracedCommands -lt 192 -or $incompleteCommands -ne 0) {
        throw 'QPC command trace identity/completion gate failed'
    }
    $receipt.traced_commands=$tracedCommands
    $receipt.first_command_id=$firstCommandId
    $receipt.last_command_id=$lastCommandId
    [IO.File]::WriteAllText($samplerStop,'workload-complete')
    if (-not $sampler.WaitForExit(30000)) { throw 'Sampler did not stop in 30 seconds' }
    $sampler.Refresh();$receipt.sampler_exit_code=$sampler.ExitCode
    $telemetry=Get-Content -LiteralPath (Join-Path $OutputDir 'telemetry.json') -Raw | ConvertFrom-Json
    if ($sampler.ExitCode -ne 0 -or -not $telemetry.pass -or
        $telemetry.read_errors -ne 0 -or $telemetry.target_period_ms -ne $TargetPeriodMs -or
        $telemetry.run_id -ne $receipt.run_id -or $telemetry.boot_utc -ne $boot) {
        throw 'Seven-rail sampler/launcher identity or exit gate failed'
    }
    $receipt.complete_sweeps=$telemetry.complete_sweeps
    $receipt.complete_rail_points=$telemetry.complete_rail_points
    $receipt.state='CAPTURE_COMPLETE_WITH_LIMITS'
} catch {
    $receipt.state='FAIL';$receipt.error=$_.Exception.Message
} finally {
    if ($workload -and (Birth $workload.Id) -eq $workloadBirth) {
        Request-Stop 'OWNER_STOP'
        if (-not $workload.WaitForExit(30000)) { Stop-Process -Id $workload.Id -Force -ErrorAction SilentlyContinue }
    }
    if ($sampler -and (Birth $sampler.Id) -eq $samplerBirth) {
        [IO.File]::WriteAllText($samplerStop,'owner-stop')
        if (-not $sampler.WaitForExit(30000)) { Stop-Process -Id $sampler.Id -Force -ErrorAction SilentlyContinue }
    }
    foreach ($child in @(@{process=$workload;birth=$workloadBirth},@{process=$sampler;birth=$samplerBirth})) {
        if ($child.process -and (Birth $child.process.Id) -eq $child.birth) {
            $receipt.survivors+=,$child.process.Id
        }
    }
    if ($lock) { $lock.Dispose();$receipt.lease_released=$true }
    $receipt.finished_utc=[DateTime]::UtcNow.ToString('o')
    $receipt.wall_seconds=([DateTime]::UtcNow-$start).TotalSeconds
    Save
}
@{state=$receipt.state;result=$OutputDir;error=$receipt.error;survivors=$receipt.survivors}|ConvertTo-Json -Compress
if ($receipt.state -ne 'CAPTURE_COMPLETE_WITH_LIMITS' -or $receipt.survivors.Count) { exit 1 }
