param([Parameter(Mandatory=$true)][ValidateSet('pilot','restore','main')][string]$Phase)
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$root='D:\ScaleLLM_final_model\dsp_all_power_20261115_001'
. (Join-Path $PSScriptRoot 'ownership.ps1')
$owner=Assert-BoardOwner $root
$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$env:SCALELLM_BOOT_UTC=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')
if($Phase -eq 'pilot'){
 $exe="$PSHOME\powershell.exe"
 $arguments=@('-NoProfile','-NonInteractive','-File',(Join-Path $PSScriptRoot 'kv128_sevenrail_probe.ps1'),'-StageRoot',$root,'-OutputDir',(Join-Path $root 'pilot_001'),'-DurationSeconds','60','-TargetPeriodMs','0','-MinimumSweeps','30')
}elseif($Phase -eq 'restore'){
 $exe='D:\ScaleLLM_inference\py312_20261025T042311\python\python.exe'
 $arguments=@((Join-Path $PSScriptRoot 'restore_snapshot.py'))
}else{
 $frozen=Get-Content -LiteralPath (Join-Path $root 'pilot_frozen.json') -Raw|ConvertFrom-Json
 $exe="$PSHOME\powershell.exe"
 $arguments=@('-NoProfile','-NonInteractive','-File',(Join-Path $PSScriptRoot 'kv128_sevenrail_main.ps1'),'-StageRoot',$root,'-MainRun','D:\ScaleLLM_final_model\operator_kv128_20261101_001\run_002','-InspectionJson',(Join-Path $root 'restore_001\inspection.json'),'-OutputDir',(Join-Path $root 'main_001'),'-TargetPeriodMs',([string]$frozen.target_period_ms))
}
$started=[DateTime]::UtcNow.ToString('o')
$p=Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $root -RedirectStandardOutput (Join-Path $root ('environment\'+$Phase+'.stdout.txt')) -RedirectStandardError (Join-Path $root ('environment\'+$Phase+'.stderr.txt')) -PassThru
$handle=$p.Handle;$birth=$p.StartTime.ToUniversalTime().ToString('o')
$p.ProcessorAffinity=[IntPtr]255;$p.PriorityClass='BelowNormal'
$roots=@(@{pid=$p.Id;birth=$birth;phase=$Phase})
[IO.File]::WriteAllText((Join-Path $root 'active_processes.next.json'),(ConvertTo-Json -InputObject $roots),(New-Object Text.UTF8Encoding($false)))
Move-Item -LiteralPath (Join-Path $root 'active_processes.next.json') -Destination (Join-Path $root 'active_processes.json') -Force
'PHASE='+$Phase+' PID='+$p.Id+' BIRTH='+$birth
$p.WaitForExit();$p.Refresh();$code=[int]$p.ExitCode
$receipt=[ordered]@{schema='scalellm_dsp_power_phase_process_v1';phase=$Phase;pid=$p.Id;birth=$birth;started_utc=$started;finished_utc=[DateTime]::UtcNow.ToString('o');exitcode=$code;board_owner_pid=$owner.owner_pid;fixed_whole_run_wall_termination=$false}
[IO.File]::WriteAllText((Join-Path $root ('environment\'+$Phase+'_process_receipt.json')),($receipt|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
$receipt|ConvertTo-Json
Get-Content -LiteralPath (Join-Path $root ('environment\'+$Phase+'.stdout.txt')) -Raw
Get-Content -LiteralPath (Join-Path $root ('environment\'+$Phase+'.stderr.txt')) -Raw
exit $code
