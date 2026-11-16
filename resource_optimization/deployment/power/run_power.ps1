# Portable controller. The sampler uses official 32-bit PowerTool assemblies.
param(
    [Parameter(Mandatory=$true)][ValidateSet('pilot','inspect','restore','run')][string]$Action,
    [string]$ConfigFile='',
    [string]$StageRoot='', [string]$BenchmarkRoot='', [string]$OutputDir='',
    [string]$Python='', [string]$BitFile='', [string]$ProgramReceipt='',
    [string]$BoardLockPath='', [string]$PowerToolRuntimeRoot='', [string]$AdapterSerial='',
    [string]$Assets='', [string]$Artifacts='', [string]$InspectionJson='', [string]$PilotRoot='',
    [ValidateRange(30,600)][int]$PilotSeconds=60
)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$utf8=New-Object Text.UTF8Encoding($false)

# Start-Process joins arrays with spaces. Encode every argument according to
# the Windows CRT rules, including terminal backslashes before closing quotes.
function Quote-NativeArgument([string]$Value) {
    return '"'+[regex]::Replace([regex]::Replace($Value,'(\\*)"','$1$1\"'),'(\\+)$','$1$1')+'"'
}
function Native-Arguments([string[]]$Values) {
    return (($Values | ForEach-Object { Quote-NativeArgument $_ }) -join ' ')
}
function Hash([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Birth([int]$ProcessId) {
    $item=Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($item) { return $item.CreationDate.ToUniversalTime().ToString('o') }
    return $null
}
$configBase=(Get-Location).Path
$config=$null
if ($ConfigFile) {
    $ConfigFile=(Resolve-Path -LiteralPath $ConfigFile).Path
    $configBase=Split-Path -Parent $ConfigFile
    $config=Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
}
$pathNames=@('StageRoot','BenchmarkRoot','OutputDir','Python','BitFile','ProgramReceipt','BoardLockPath',
    'PowerToolRuntimeRoot','Assets','Artifacts','InspectionJson','PilotRoot')
foreach ($name in $pathNames+@('AdapterSerial')) {
    $value=[string](Get-Variable -Name $name -ValueOnly)
    if (-not $value -and $config -and $config.PSObject.Properties[$name]) { $value=[string]$config.$name }
    if ($value -and $pathNames -contains $name) {
        if (-not [IO.Path]::IsPathRooted($value)) { $value=Join-Path $configBase $value }
        $value=[IO.Path]::GetFullPath($value)
    }
    Set-Variable -Name $name -Value $value
}
$required=@('StageRoot','BenchmarkRoot','OutputDir','Python','BitFile','ProgramReceipt','BoardLockPath')
if ($Action -in @('pilot','run')) { $required+=@('PowerToolRuntimeRoot','AdapterSerial') }
if ($Action -eq 'run') { $required+=@('Assets','Artifacts','InspectionJson','PilotRoot') }
foreach ($name in $required) {
    if (-not (Get-Variable -Name $name -ValueOnly)) { throw ('Missing parameter/configuration '+$name) }
}
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Board actions require Windows' }
if (Test-Path -LiteralPath $OutputDir) { throw 'OutputDir must be a new directory' }
if (-not (Test-Path -LiteralPath (Split-Path -Parent $OutputDir) -PathType Container)) { throw 'OutputDir parent must exist' }
if (-not (Test-Path -LiteralPath (Split-Path -Parent $BoardLockPath) -PathType Container)) { throw 'BoardLockPath parent must exist' }
$sourceManifest=Join-Path $PSScriptRoot 'source_manifest.json'
$source=Get-Content -LiteralPath $sourceManifest -Raw|ConvertFrom-Json
if ($source.schema -ne 'scalellm_portable_power_sources_v1') { throw 'Portable source manifest schema differs' }
foreach ($entry in $source.files.PSObject.Properties) {
    $file=Join-Path $PSScriptRoot $entry.Name
    if ((Get-Item -LiteralPath $file).Length -ne $entry.Value.bytes -or (Hash $file) -ne $entry.Value.sha256) {
        throw ('Portable source identity differs '+$entry.Name)
    }
}
$bitSha=Hash $BitFile
if ($bitSha -ne '5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7' -or
    (Get-Item -LiteralPath $BitFile).Length -ne 80159263) { throw 'Released all-DSP bit file differs' }
$start=[DateTime]::UtcNow
$boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
$env:SCALELLM_RUN_ID=('portable_power_'+$Action+'_'+$start.ToString('yyyyMMddTHHmmssffffZ'))
$env:SCALELLM_BOOT_UTC=$boot
$env:SCALELLM_POWER_OWNER_PID=[string]$PID
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$self=Get-Process -Id $PID
$allowedMask=$self.ProcessorAffinity.ToInt64()
$cpuMask=[long]0;$selectedCpus=0
for ($bit=0;$bit -lt ([IntPtr]::Size*8) -and $selectedCpus -lt 8;$bit++) {
    $bitMask=[long]1 -shl $bit
    if (($allowedMask -band $bitMask) -ne 0) { $cpuMask=$cpuMask -bor $bitMask;$selectedCpus++ }
}
if ($selectedCpus -lt 1) { throw 'No allowed CPU is available' }
$self.ProcessorAffinity=[IntPtr]$cpuMask
$self.PriorityClass='BelowNormal'
$workloadScript=Join-Path $PSScriptRoot 'kv128_sevenrail_workload.py'
$samplerScript=Join-Path $PSScriptRoot 'kv128_sevenrail_sampler.ps1'
$traceScript=Join-Path $PSScriptRoot 'command_active_inference.py'
$runtimeManifest=Join-Path $PSScriptRoot 'powertool_runtime_manifest.json'
$receipt=[ordered]@{schema='scalellm_portable_power_launcher_v1';state='RUNNING';action=$Action;
    started_utc=$start.ToString('o');host=[Environment]::MachineName;boot_utc=$boot;
    run_id=$env:SCALELLM_RUN_ID;bit_sha256=$bitSha;qpc_frequency=[Diagnostics.Stopwatch]::Frequency;
    source_manifest_sha256=(Hash $sourceManifest);sampler_script_sha256=(Hash $samplerScript);
    powertool_manifest_sha256=(Hash $runtimeManifest);board_lock_path=$BoardLockPath;
    owner_pid=$PID;owner_birth=(Birth $PID);fixed_wall_time_termination=$false;
    rss_limit_bytes=8589934592;available_floor_bytes=2147483648;disk_floor_bytes=42949672960;
    cpu_mask=$cpuMask;cpu_count=$selectedCpus;peak_tree_rss_bytes=[long]0;minimum_available_bytes=[long]::MaxValue;
    minimum_disk_free_bytes=[long]::MaxValue;sampler_exit_code=$null;workload_exit_code=$null;
    sampler_pid=$null;sampler_birth=$null;workload_pid=$null;workload_birth=$null;
    target_period_ms=$null;gap_threshold_ms=$null;stop_reason=$null;error=$null;
    lease_released=$false;survivors=@()}
$lock=$null;$sampler=$null;$samplerBirth=$null;$workload=$null;$workloadBirth=$null
$stopFile=Join-Path $OutputDir 'workload.stop'
$samplerStop=Join-Path $OutputDir 'sampler.stop'
$telemetryPath=Join-Path $OutputDir 'telemetry.jsonl'
function Save {
    [IO.File]::WriteAllText((Join-Path $OutputDir 'receipt.json'),($receipt|ConvertTo-Json -Depth 14),$utf8)
}
function Request-Stop([string]$Reason) {
    if (-not $script:receipt.stop_reason) {
        $script:receipt.stop_reason=$Reason
        [IO.File]::WriteAllText($script:stopFile,$Reason,$script:utf8)
        [IO.File]::WriteAllText($script:samplerStop,$Reason,$script:utf8)
        Save
    }
}
function Observe([bool]$RequireSamplerHeartbeat=$false) {
    $free=[long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1024
    $script:self.Refresh();$rss=[long]$script:self.WorkingSet64
    foreach ($child in @($script:sampler,$script:workload)) {
        if ($child -and -not $child.HasExited) { $child.Refresh();$rss+=[long]$child.WorkingSet64 }
    }
    $disk=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($script:OutputDir))
    $script:receipt.peak_tree_rss_bytes=[Math]::Max($rss,[long]$script:receipt.peak_tree_rss_bytes)
    $script:receipt.minimum_available_bytes=[Math]::Min($free,[long]$script:receipt.minimum_available_bytes)
    $script:receipt.minimum_disk_free_bytes=[Math]::Min($disk.AvailableFreeSpace,[long]$script:receipt.minimum_disk_free_bytes)
    if ($rss -gt $script:receipt.rss_limit_bytes) { Request-Stop 'OWNED_RSS_LIMIT' }
    if ($free -lt $script:receipt.available_floor_bytes) { Request-Stop 'AVAILABLE_MEMORY_FLOOR' }
    if ($disk.AvailableFreeSpace -lt $script:receipt.disk_floor_bytes) { Request-Stop 'OUTPUT_VOLUME_DISK_FLOOR' }
    if ($RequireSamplerHeartbeat) {
        $tick=$null
        foreach ($line in @(Get-Content -LiteralPath $script:telemetryPath -Tail 100 -ErrorAction SilentlyContinue)) {
            try { $row=$line|ConvertFrom-Json } catch { continue }
            if ($row.record -eq 'bus_read' -and $row.run_id -eq $script:receipt.run_id -and
                $row.qpc_frequency -eq $script:receipt.qpc_frequency) { $tick=[long]$row.after_ticks }
        }
        $age=if($null -eq $tick){-1}else{([Diagnostics.Stopwatch]::GetTimestamp()-$tick)/$script:receipt.qpc_frequency}
        if ($age -lt 0 -or $age -gt 10) {
            Request-Stop 'SAMPLER_OPERATION_HEARTBEAT_TIMEOUT'
        }
    }
    if ($script:receipt.stop_reason) { throw $script:receipt.stop_reason }
}
function Start-Owned([string]$File,[string[]]$Arguments,[string]$Prefix) {
    $child=Start-Process -FilePath $File -ArgumentList (Native-Arguments $Arguments) -WorkingDirectory $OutputDir `
        -RedirectStandardOutput (Join-Path $OutputDir ($Prefix+'.stdout.txt')) `
        -RedirectStandardError (Join-Path $OutputDir ($Prefix+'.stderr.txt')) -PassThru
    $handle=$child.Handle
    return $child
}
New-Item -ItemType Directory -Path $OutputDir -ErrorAction Stop|Out-Null
try {
    $lock=[IO.File]::Open($BoardLockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $other=@(Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -ne $PID -and ($_.Name -match '^(vivado|hw_server|cs_server|MaximDigitalPower)(\.exe)?$' -or
        ($_.Name -match '^(python|pythonw|powershell)(\.exe)?$' -and
         $_.CommandLine -match 'kv128_sevenrail_(main|probe|sampler|workload)|scalellm\.py.+(run|benchmark|program)|command_active_inference\.py'))
    })
    if ($other.Count) { throw 'Existing board/tool process owns the device' }
    Save
    & $Python (Join-Path $PSScriptRoot 'portable_source.py') --main $BenchmarkRoot --program-receipt $ProgramReceipt 1> (Join-Path $OutputDir 'verify-source.stdout.txt') 2> (Join-Path $OutputDir 'verify-source.stderr.txt')
    $receipt.verify_source_exit_code=$LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'Fresh benchmark source verification failed' }
    $target=0
    if ($Action -eq 'run') {
        $freezePath=Join-Path $PilotRoot 'freeze.json'
        $frozen=Get-Content -LiteralPath $freezePath -Raw|ConvertFrom-Json
        $validatedPath=Join-Path $OutputDir 'validated_pilot.json'
        & $Python (Join-Path $PSScriptRoot 'pilot.py') --metadata (Join-Path $PilotRoot 'telemetry.json') `
            --jsonl (Join-Path $PilotRoot 'telemetry.jsonl') --receipt (Join-Path $PilotRoot 'receipt.json') --output $validatedPath `
            1> (Join-Path $OutputDir 'pilot-validation.stdout.txt') 2> (Join-Path $OutputDir 'pilot-validation.stderr.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Pilot raw data verification failed' }
        $validated=Get-Content -LiteralPath $validatedPath -Raw|ConvertFrom-Json
        foreach ($key in @('schema','status','pilot_metadata_sha256','pilot_jsonl_sha256','pilot_receipt_sha256',
            'pilot_run_id','boot_utc','host','qpc_frequency','adapter_serial_sha256','sampler_script_sha256',
            'powertool_manifest_sha256','bit_sha256','target_period_ms','gap_threshold_ms','formula','period_source','frozen_before_formal_run')) {
            if ($frozen.$key -ne $validated.$key) { throw ('Frozen pilot changed '+$key) }
        }
        $serialSha=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($AdapterSerial)))).Replace('-','').ToLowerInvariant()
        $bootDrift=([DateTime]::Parse($boot).ToUniversalTime()-[DateTime]::Parse([string]$frozen.boot_utc).ToUniversalTime()).TotalSeconds
        if ($frozen.host -ne $receipt.host -or [Math]::Abs($bootDrift) -gt 10 -or
            $frozen.adapter_serial_sha256 -ne $serialSha -or $frozen.sampler_script_sha256 -ne $receipt.sampler_script_sha256 -or
            $frozen.powertool_manifest_sha256 -ne $receipt.powertool_manifest_sha256) { throw 'Pilot host/boot/adapter/runtime differs' }
        $inspection=Get-Content -LiteralPath $InspectionJson -Raw|ConvertFrom-Json
        if ([Math]::Abs(([DateTime]::Parse($boot).ToUniversalTime()-[DateTime]::Parse([string]$inspection.observed_boot_utc).ToUniversalTime()).TotalSeconds) -gt 10) { throw 'Inspection and current OS boot differ' }
        $target=[int]$frozen.target_period_ms
        $receipt.target_period_ms=$target;$receipt.gap_threshold_ms=3*$target
        $receipt.pilot_freeze_sha256=Hash $freezePath
    }
    if ($Action -in @('pilot','run')) {
        $ps32=Join-Path $env:WINDIR 'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
        $samplerArgs=@('-NoProfile','-NonInteractive','-File',$samplerScript,
            '-RuntimeRoot',$PowerToolRuntimeRoot,'-ExpectedAdapterSerial',$AdapterSerial,
            '-EvidencePath',(Join-Path $OutputDir 'telemetry.json'),'-JsonlPath',$telemetryPath,
            '-ReadyPath',(Join-Path $OutputDir 'sampler.ready.json'),'-StopFile',$samplerStop,
            '-PhasePath',(Join-Path $OutputDir 'phase.json'),'-TargetPeriodMs',([string]$target),
            '-IntervalMs','0','-MaxSweeps','0','-MaxSeconds',$(if($Action -eq 'pilot'){[string]$PilotSeconds}else{'0'}))
        $sampler=Start-Owned $ps32 $samplerArgs 'sampler'
        $samplerBirth=Birth $sampler.Id
        if (-not $samplerBirth) { throw 'Sampler lacks process birth identity' }
        $receipt.sampler_pid=$sampler.Id;$receipt.sampler_birth=$samplerBirth
        $sampler.ProcessorAffinity=[IntPtr]$cpuMask;$sampler.PriorityClass='BelowNormal'
        $readyStart=[Diagnostics.Stopwatch]::GetTimestamp()
        while (-not (Test-Path -LiteralPath (Join-Path $OutputDir 'sampler.ready.json')) -and -not $sampler.HasExited) {
            Observe
            if (([Diagnostics.Stopwatch]::GetTimestamp()-$readyStart)/$receipt.qpc_frequency -gt 30) { throw 'Sampler ready timeout' }
            Start-Sleep -Milliseconds 200;$sampler.Refresh()
        }
        if ($sampler.HasExited) { throw 'Sampler exited before first complete sweep' }
    }
    if ($Action -eq 'pilot') {
        while (-not $sampler.HasExited) { Observe $true; Start-Sleep -Milliseconds 500; $sampler.Refresh() }
    } else {
        $mode=if($Action -eq 'inspect'){'inspect-live'}else{$Action}
        $workArgs=@($workloadScript,$mode,'--main',$BenchmarkRoot,'--runtime-root',$StageRoot,'--bit-file',$BitFile,'--program-receipt',$ProgramReceipt)
        if ($Action -eq 'run') {
            $out=Join-Path $OutputDir 'workload'
            $workArgs=@($traceScript,'--frozen-run',$workloadScript,'--command-trace',(Join-Path $OutputDir 'commands.jsonl'))+$workArgs[1..($workArgs.Count-1)]
            $workArgs+=@('--inspection',$InspectionJson,'--assets',$Assets,'--artifacts',$Artifacts,
                '--sampler-jsonl',$telemetryPath,'--sampler-ready',(Join-Path $OutputDir 'sampler.ready.json'),
                '--windows-jsonl',(Join-Path $out 'windows.jsonl'),'--phase-path',(Join-Path $OutputDir 'phase.json'),
                '--stop-file',$stopFile)
        } else {
            $out=Join-Path $OutputDir 'inspection'
        }
        $workArgs+=@('--out',$out)
        $workload=Start-Owned $Python $workArgs 'workload'
        $workloadBirth=Birth $workload.Id
        if (-not $workloadBirth) { throw 'Workload lacks process birth identity' }
        $receipt.workload_pid=$workload.Id;$receipt.workload_birth=$workloadBirth
        $workload.ProcessorAffinity=[IntPtr]$cpuMask;$workload.PriorityClass='BelowNormal';Save
        while (-not $workload.HasExited) {
            Observe ($Action -eq 'run')
            if ($Action -eq 'run' -and $sampler.HasExited) { throw 'Sampler exited during workload' }
            Start-Sleep -Milliseconds 500;$workload.Refresh()
        }
        $workload.WaitForExit();$workload.Refresh();$receipt.workload_exit_code=$workload.ExitCode
        if ($workload.ExitCode -ne 0) { throw ('Workload native exit '+$workload.ExitCode) }
        $resultFile=if($Action -eq 'run'){Join-Path $out 'workload.json'}else{Join-Path $out 'inspection.json'}
        $result=Get-Content -LiteralPath $resultFile -Raw|ConvertFrom-Json
        if (-not $result.handles_closed) { throw 'XDMA handles did not close' }
        if ($Action -eq 'run') {
            if ($result.status -ne 'COMPLETE_WITH_LIMITS' -or $result.completed_windows -ne 12 -or
                $result.final_csr.STATUS -ne 0 -or $result.final_csr.ADMISSION_ERROR -ne 0 -or $result.final_csr.DONE_ERROR -ne 0) {
                throw 'Twelve-window/final-idle workload gate failed'
            }
            [IO.File]::WriteAllText($samplerStop,'workload-complete',$utf8)
        } elseif ($result.status -ne 'PASS_WITH_LIMITS') { throw 'Snapshot inspection/restore gate failed' }
    }
    if ($sampler) {
        if (-not $sampler.WaitForExit(30000)) { throw 'Sampler close timeout' }
        $sampler.Refresh();$receipt.sampler_exit_code=$sampler.ExitCode
        $meta=Get-Content -LiteralPath (Join-Path $OutputDir 'telemetry.json') -Raw|ConvertFrom-Json
        if ($sampler.ExitCode -ne 0 -or -not $meta.pass -or $meta.status -ne 'COMPLETE' -or
            $meta.read_errors -ne 0 -or $meta.disconnect_error -or -not $meta.adapter_disconnect_completed -or $meta.run_id -ne $receipt.run_id -or $meta.boot_utc -ne $boot -or
            $meta.target_period_ms -ne $target -or $meta.complete_rail_points -ne 7*$meta.complete_sweeps) {
            throw 'Sampler native exit/data identity gate failed'
        }
        $receipt.complete_sweeps=$meta.complete_sweeps
        $receipt.complete_rail_points=$meta.complete_rail_points
    }
    $receipt.state='COMPLETE'
} catch {
    $receipt.state='FAIL';$receipt.error=$_.Exception.Message
} finally {
    foreach ($owned in @(@{process=$workload;birth=$workloadBirth},@{process=$sampler;birth=$samplerBirth})) {
        $child=$owned.process
        if ($child -and (Birth $child.Id) -eq $owned.birth) {
            [IO.File]::WriteAllText($stopFile,'owner-stop',$utf8)
            [IO.File]::WriteAllText($samplerStop,'owner-stop',$utf8)
            if (-not $child.WaitForExit(30000)) {
                Stop-Process -Id $child.Id -Force -ErrorAction SilentlyContinue
                $stopped=$child.WaitForExit(10000)
            }
        }
        if ($child -and (Birth $child.Id) -eq $owned.birth) { $receipt.survivors+=,$child.Id }
    }
    foreach ($name in @('sampler','workload')) {
        $child=Get-Variable -Name $name -ValueOnly
        if ($child) {
            $child.Refresh()
            if ($child.HasExited) { $child.WaitForExit();$receipt[$name+'_exit_code']=$child.ExitCode }
        }
    }
    if ($lock) { $lock.Dispose();$receipt.lease_released=$true }
    $receipt.finished_utc=[DateTime]::UtcNow.ToString('o')
    $receipt.wall_seconds=([DateTime]::UtcNow-$start).TotalSeconds
    Save
    Remove-Item Env:SCALELLM_POWER_OWNER_PID -ErrorAction SilentlyContinue
}
@{state=$receipt.state;result=$OutputDir;error=$receipt.error;survivors=$receipt.survivors}|ConvertTo-Json -Compress
if ($receipt.state -ne 'COMPLETE' -or $receipt.survivors.Count) { exit 1 }
