# Portable full-run power orchestration; CPU-tested, not board-tested.
# No programming, reset, driver changes, installation, or vendor redistribution.
param(
    [Parameter(Mandatory=$true)][string]$RuntimeRoot,
    [Parameter(Mandatory=$true)][string]$AdapterSerial,
    [Parameter(Mandatory=$true)][string]$Config,
    [Parameter(Mandatory=$true)][string]$Requests,
    [Parameter(Mandatory=$true)][string]$Output,
    [Parameter(Mandatory=$true)][string]$BoardLease,
    [string]$Python = 'python.exe',
    [ValidateRange(60,7500)][int]$WholeSeconds = 7500,
    [ValidateRange(1000,60000)][int]$IntervalMs = 1000,
    [ValidateSet('D5749E5EBB80B4AD7C81C73CC9863467BB988915922A9337DA75BB304FC23F31',
                 'CA0CEBC63364312C56C3949655B40352758177B243B56EADC1C7BFFF30F08E68')]
    [string]$ExpectedExecutableSha256 = 'D5749E5EBB80B4AD7C81C73CC9863467BB988915922A9337DA75BB304FC23F31',
    [switch]$PlanOnly
)
$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$release=Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$cli=Join-Path $release 'deploy/scalellm.py'
$Config=[IO.Path]::GetFullPath($Config); $Requests=[IO.Path]::GetFullPath($Requests)
$logs=[IO.Path]::GetFullPath($Output)
$cfg=Get-Content -LiteralPath $Config -Raw|ConvertFrom-Json
if($cfg.schema-ne'scalellm_final_deploy_v1'){throw 'Use the release deployment config schema'}
if($cfg.wall_seconds-le0-or$cfg.wall_seconds-gt($WholeSeconds-30)){throw 'Configured workload must fit within whole window minus30s'}
if($cfg.command_timeout_seconds-le0-or$cfg.command_timeout_seconds-gt120){throw 'Command timeout must be positive and <=120s'}
$python=$Python
$samplerScript=Join-Path $PSScriptRoot 'sample_power.ps1'
$workArgs=@($cli,'--config',$Config,'run','--requests',$Requests,'--result',(Join-Path $logs 'device'),'--power-log',(Join-Path $logs 'telemetry.jsonl'))
function Join-NativeArguments([string[]]$Values){
    # Windows CRT escaping: double backslashes before quotes and closing quote.
    return (($Values|ForEach-Object {
        $v=[regex]::Replace($_,'(\\*)"','$1$1\"')
        $v=[regex]::Replace($v,'(\\+)$','$1$1')
        '"'+$v+'"'
    }) -join ' ')
}
if($PlanOnly){
    @{board_io=$false;config=$Config;requests=$Requests;output=$logs;command=@($python)+$workArgs;commandline=(Join-NativeArguments $workArgs);whole_seconds=$WholeSeconds;launcher_board_tested=$false}|ConvertTo-Json -Depth 8
    exit 0
}
if(Test-Path -LiteralPath $logs){throw 'Output directory must be new'}
New-Item -ItemType Directory -Path $logs -ErrorAction Stop|Out-Null
$self=Get-Process -Id $PID; $self.ProcessorAffinity=[IntPtr]255; $self.PriorityClass='BelowNormal'
$env:OPENBLAS_NUM_THREADS='1';$env:OMP_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$ownerCim=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
$receipt=[ordered]@{action='portable-full-model-seven-rail-power';started_utc=[DateTime]::UtcNow.ToString('o');owner_pid=$PID;owner_birth=$ownerCim.CreationDate.ToUniversalTime().ToString('o');cpu_mask=255;rss_limit_bytes=8589934592;peak_tree_rss_bytes=0;available_memory_lowest_bytes=[long]::MaxValue;whole_limit_s=$WholeSeconds;requested_interval_ms=$IntervalMs;operations=@();phases=@();qpc_frequency=[Diagnostics.Stopwatch]::Frequency;error=$null;owned_cleanup=@();launcher_board_tested=$false}
$owned=@{};$lock=$null;$sampler=$null;$samplerBirth=$null;$samplingRequired=$false;$began=[DateTime]::UtcNow
function Save-Receipt { [IO.File]::WriteAllText((Join-Path $logs 'receipt.json'),($receipt|ConvertTo-Json -Depth 12),(New-Object Text.UTF8Encoding($false))) }
function Cim-Birth([int]$ProcessId){$v=Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue;if($v){return $v.CreationDate.ToUniversalTime().ToString('o')};return $null}
function Observe-Owned {
    $all=@(Get-CimInstance Win32_Process);$parents=@([int]$PID)
    foreach($p in $all){$key=[string]$p.ProcessId;if($script:owned.ContainsKey($key)-and$p.CreationDate.ToUniversalTime().ToString('o')-eq$script:owned[$key]){$parents+=[int]$p.ProcessId}}
    for($i=0;$i-lt 10;$i++){$new=@($all|Where-Object{[int]$_.ParentProcessId -in $parents -and [int]$_.ProcessId -notin $parents});if(-not $new.Count){break};foreach($p in $new){$script:owned[[string]$p.ProcessId]=$p.CreationDate.ToUniversalTime().ToString('o');$parents+=[int]$p.ProcessId}}
    $rss=[long]0
    foreach($p in $all){$id=[string]$p.ProcessId;if($p.ProcessId-eq$PID-or($script:owned.ContainsKey($id)-and$p.CreationDate.ToUniversalTime().ToString('o')-eq$script:owned[$id])){$rss+=[long]$p.WorkingSetSize;$process=Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue;if($process -and -not $process.HasExited){try{$mask=$process.ProcessorAffinity.ToInt64();if($mask -band (-bnot 255)){throw 'Owned process escaped CPU0..7'}}catch{if(Cim-Birth $p.ProcessId){throw}}}}}
    $available=[long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1024
    $script:receipt.available_memory_lowest_bytes=[Math]::Min($available,$script:receipt.available_memory_lowest_bytes)
    if($available-lt 2147483648){throw 'System available memory below2GiB'}
    if($rss-gt 8589934592){throw 'Owned tree exceeded8GiB RSS'}
    $script:receipt.peak_tree_rss_bytes=[Math]::Max($rss,$script:receipt.peak_tree_rss_bytes)
    if(([DateTime]::UtcNow-$script:began).TotalSeconds-gt $WholeSeconds){throw ('Full model/power ceiling '+$WholeSeconds+'s')}
}
function Run-Bounded([string]$Name,[string]$File,[string[]]$Arguments,[int]$Seconds){
    $p=Start-Process -FilePath $File -ArgumentList (Join-NativeArguments $Arguments) -WorkingDirectory $logs -RedirectStandardOutput (Join-Path $logs ($Name+'.stdout.txt')) -RedirectStandardError (Join-Path $logs ($Name+'.stderr.txt')) -PassThru
    $handle=$p.Handle;$birth=Cim-Birth $p.Id;if(-not$birth){if(-not$p.HasExited){throw 'Live child lacks native creation identity'};$birth='EXITED_BEFORE_CIM_SAMPLE'};$script:owned[[string]$p.Id]=$birth;$start=[DateTime]::UtcNow;$script:receipt.active_native=@{name=$Name;pid=$p.Id;birth=$birth};Save-Receipt
    while(-not $p.HasExited){Observe-Owned;Observe-Sampling;if(([DateTime]::UtcNow-$start).TotalSeconds-gt $Seconds){throw ($Name+' exceeded bounded timeout')};Start-Sleep -Milliseconds 500;$p.Refresh()}
    $p.WaitForExit();$p.Refresh();$code=$p.ExitCode
    $script:receipt.operations+=@{name=$Name;pid=$p.Id;birth=$script:owned[[string]$p.Id];exit_code=$code;wall_s=([DateTime]::UtcNow-$start).TotalSeconds};Save-Receipt
    if($null-eq$code -or $code-ne 0){throw ($Name+' native failure')}
}

function Mark([string]$Name){
    $entry=@{name=$Name;utc=[DateTime]::UtcNow.ToString('o');ticks=[Diagnostics.Stopwatch]::GetTimestamp()}
    $script:receipt.phases+=$entry;Save-Receipt
}
function Observe-Sampling {
    if(-not$script:samplingRequired){return}
    $script:sampler.Refresh()
    if($script:sampler.HasExited){throw 'Power sampler exited before complete workload/idle windows'}
    $f=Get-Item (Join-Path $logs 'telemetry.jsonl') -ErrorAction Stop
    if(([DateTime]::UtcNow-$f.LastWriteTimeUtc).TotalSeconds-gt15){throw 'Power telemetry heartbeat stale15s; full coverage unavailable'}
}
function Idle-Window([string]$Name){
    Mark ($Name+'_begin');$until=[DateTime]::UtcNow.AddSeconds(10)
    while([DateTime]::UtcNow-lt$until){Observe-Owned;Observe-Sampling;Start-Sleep -Milliseconds 500}
    Mark ($Name+'_end')
}

try {
    $lock=[IO.File]::Open([IO.Path]::GetFullPath($BoardLease),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    $others=@(Get-CimInstance Win32_Process|Where-Object{$_.Name-match'^(vivado|hw_server|cs_server|python|pythonw|MaximDigitalPower)(\.exe)?$' -or ($_.ProcessId-ne$PID -and $_.CommandLine-match'sample_power(_(controlled|full))?\.ps1')})
    if($others.Count){throw 'Existing board/power/tool owner; no takeover'}
    $bit=[IO.Path]::GetFullPath([IO.Path]::Combine((Split-Path $Config -Parent),[Environment]::ExpandEnvironmentVariables([string]$cfg.bitstream)))
    $receipt.bit_sha256=(Get-FileHash -LiteralPath $bit -Algorithm SHA256).Hash.ToLower()
    if($receipt.bit_sha256-ne'96df1a5c1bf4174921bc02ccd88df4066dece3d62b491acb3106bb90ac0ffc85'-or(Get-Item -LiteralPath $bit).Length-ne80159263){throw 'Released bitstream file identity mismatch; no programming permitted'}
    $receipt.requests_sha256=(Get-FileHash -LiteralPath $Requests -Algorithm SHA256).Hash.ToLower()
    $receipt.config_sha256=(Get-FileHash -LiteralPath $Config -Algorithm SHA256).Hash.ToLower()
    $receipt.sampler_script_sha256=(Get-FileHash -LiteralPath $samplerScript -Algorithm SHA256).Hash.ToLower()
    Run-Bounded 'identity' $python @($cli,'--config',$Config,'preflight','--device','--requests',$Requests) 60
    $identity=Get-Content -LiteralPath (Join-Path $logs 'identity.stdout.txt') -Raw|ConvertFrom-Json
    if($identity.verdict-ne'PASS'-or-not$identity.handles_closed){throw 'Read-only board preflight did not close successfully'}
    $sampleBase=@('-NoProfile','-NonInteractive','-File',$samplerScript,'-IntervalMs',[string]$IntervalMs,'-RuntimeRoot',$RuntimeRoot,'-ExpectedAdapterSerial',$AdapterSerial,'-ExpectedExecutableSha256',$ExpectedExecutableSha256)
    $ps32=Join-Path $env:WINDIR 'SysWOW64/WindowsPowerShell/v1.0/powershell.exe'
    Run-Bounded 'power_probe' $ps32 ($sampleBase+@('-SampleCount','1','-Label','readonly_probe','-EvidencePath',(Join-Path $logs 'probe.json'))) 30
    $probe=Get-Content -LiteralPath (Join-Path $logs 'probe.json') -Raw|ConvertFrom-Json
    if(-not$probe.pass-or$probe.samples.Count-ne1-or$probe.samples[0].rails.Count-ne7){throw 'Read-only power probe invalid; workload not started'}
    $receipt.readonly_power_probe=$probe.summary
    $count=[int][Math]::Ceiling($WholeSeconds*1000.0/$IntervalMs)+8
    $sampleArgs=$sampleBase+@('-SampleCount',[string]$count,'-Label','complete_model_with_resident_load','-EvidencePath',(Join-Path $logs 'telemetry.json'),'-JsonlPath',(Join-Path $logs 'telemetry.jsonl'),'-ReadyPath',(Join-Path $logs 'sampler.ready.json'),'-StopFile',(Join-Path $logs 'sampler.stop'))
    $sampler=Start-Process -FilePath $ps32 -ArgumentList (Join-NativeArguments $sampleArgs) -WorkingDirectory $logs -RedirectStandardOutput (Join-Path $logs 'sampler.stdout.txt') -RedirectStandardError (Join-Path $logs 'sampler.stderr.txt') -PassThru
    $samplerHandle=$sampler.Handle;$samplerBirth=Cim-Birth $sampler.Id
    if(-not$samplerBirth){throw 'Sampler lacks native process creation identity'}
    $owned[[string]$sampler.Id]=$samplerBirth
    $receipt.sampler=@{pid=$sampler.Id;birth=$samplerBirth;script_sha256=$receipt.sampler_script_sha256;expected_executable_sha256=$ExpectedExecutableSha256};Save-Receipt
    $readyDeadline=[DateTime]::UtcNow.AddSeconds(20)
    while(-not(Test-Path -LiteralPath (Join-Path $logs 'sampler.ready.json'))){$sampler.Refresh();if($sampler.HasExited){throw 'Sampler exited before first valid sweep'};Observe-Owned;if([DateTime]::UtcNow-gt$readyDeadline){throw 'Sampler readiness timeout'};Start-Sleep -Milliseconds 200}
    $receipt.sampler_ready=Get-Content -LiteralPath (Join-Path $logs 'sampler.ready.json') -Raw|ConvertFrom-Json
    $samplingRequired=$true
    Idle-Window 'idle_before'
    Mark 'model_begin';Run-Bounded 'inference' $python $workArgs ([int]$cfg.wall_seconds);Mark 'model_end'
    Idle-Window 'idle_after'
    $samplingRequired=$false
    [IO.File]::WriteAllText((Join-Path $logs 'sampler.stop'),'complete')
    $stopDeadline=[DateTime]::UtcNow.AddSeconds(30)
    while(-not$sampler.HasExited){Observe-Owned;if([DateTime]::UtcNow-gt$stopDeadline){throw 'Sampler stop timeout'};Start-Sleep -Milliseconds 200;$sampler.Refresh()}
    $sampler.WaitForExit();$sampler.Refresh();$receipt.sampler.native_exit=$sampler.ExitCode
    if($sampler.ExitCode-ne0){throw 'Sampler native failure'}
    $telemetry=Get-Content -LiteralPath (Join-Path $logs 'telemetry.json') -Raw|ConvertFrom-Json
    if(-not$telemetry.pass-or$telemetry.summary.sample_count-lt20){throw 'Power data invalid/insufficient'}
    $receipt.telemetry_summary=$telemetry.summary
    $result=Get-Content -LiteralPath (Join-Path $logs 'device/run.json') -Raw|ConvertFrom-Json
    if($result.execution-ne'COMPLETE'-or-not$result.handles_closed-or$result.final_status.STATUS-ne0-or$result.final_status.ADMISSION_ERROR-ne0-or$result.final_status.DONE_ERROR-ne0){throw 'Model final state invalid'}
    $receipt.state='COMPLETE'
}catch{$receipt.state='FAIL';$receipt.error=$_.Exception.Message}
finally {
    $samplingRequired=$false
    if($sampler-and-not$sampler.HasExited){[IO.File]::WriteAllText((Join-Path $logs 'sampler.stop'),'owner-stop');$sampler.WaitForExit(10000)|Out-Null}
    try{Observe-Owned}catch{}
    foreach($id in @($owned.Keys|Sort-Object{[int]$_}-Descending)){if((Cim-Birth ([int]$id))-eq$owned[$id]){Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue;$receipt.owned_cleanup+=@{pid=[int]$id;birth=$owned[$id]}}}
    Start-Sleep -Milliseconds 300
    $receipt.owned_birth=$owned;$receipt.survivors=@()
    foreach($id in $owned.Keys){if((Cim-Birth ([int]$id))-eq$owned[$id]){$receipt.survivors+=[int]$id}}
    if($lock){$lock.Dispose()};$receipt.lease_released=($null-ne$lock);$receipt.finished_utc=[DateTime]::UtcNow.ToString('o');Save-Receipt
}
$receipt|ConvertTo-Json -Depth 12 -Compress
if($receipt.state-ne'COMPLETE'-or$receipt.survivors.Count){exit 1}
