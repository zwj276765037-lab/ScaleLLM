param([Parameter(Mandatory=$true)][string]$RunRoot)
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$encoding=New-Object Text.UTF8Encoding($false)
$lockPath='C:/Users/dell/ScaleLLM_board_validation/.board.lock'
$receipt=[ordered]@{state='STARTING';owner_pid=$PID;owner_birth=(Get-CimInstance Win32_Process -Filter "ProcessId=$PID").CreationDate.ToUniversalTime().ToString('o');host=$env:COMPUTERNAME;lock_path=$lockPath;fixed_wall_time_termination=$false;rss_limit_bytes=8589934592;available_floor_bytes=2147483648;disk_floor_bytes=42949672960;peak_owned_rss_bytes=0;minimum_available_bytes=[long]::MaxValue;minimum_disk_free_bytes=[long]::MaxValue;stop_reason=$null;lease_released=$false}
function Save {
 $text=$receipt|ConvertTo-Json -Depth 8
 $tmp=Join-Path $RunRoot 'board_owner.tmp.json'
 [IO.File]::WriteAllText($tmp,$text,$encoding)
 for($attempt=0;$attempt -lt 6;$attempt++){
  try{Move-Item -LiteralPath $tmp -Destination (Join-Path $RunRoot 'board_owner.json') -Force;return}catch{Start-Sleep -Milliseconds 50}
 }
 throw 'Unable to publish board ownership'
}
$lease=$null
try{
 if($env:COMPUTERNAME -ne 'DESKTOP-D3'){throw 'Unexpected board host'}
 $lease=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
 $receipt.state='LEASE_HELD';Save
 while(-not(Test-Path -LiteralPath (Join-Path $RunRoot 'guardian.stop'))){
  $owned=@{};$all=@(Get-CimInstance Win32_Process)
  $active=Join-Path $RunRoot 'active_processes.json'
  if(Test-Path -LiteralPath $active){
   try{$roots=Get-Content -LiteralPath $active -Raw|ConvertFrom-Json}catch{$roots=@()}
   foreach($entry in $roots){
    $p=$all|Where-Object{[int]$_.ProcessId -eq [int]$entry.pid -and $_.CreationDate.ToUniversalTime().ToString('o') -eq $entry.birth}|Select-Object -First 1
    if($p){$owned[[int]$p.ProcessId]=$p}
   }
  }
  for($depth=0;$depth -lt 10;$depth++){
   $new=@($all|Where-Object{$owned.ContainsKey([int]$_.ParentProcessId) -and -not $owned.ContainsKey([int]$_.ProcessId)})
   if(-not $new.Count){break};foreach($p in $new){$owned[[int]$p.ProcessId]=$p}
  }
  $rss=[long](Get-Process -Id $PID).WorkingSet64
  foreach($p in $owned.Values){$rss+=[long]$p.WorkingSetSize}
  $free=[long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1024
  $disk=[long](Get-PSDrive -Name D).Free
  $receipt.peak_owned_rss_bytes=[Math]::Max([long]$receipt.peak_owned_rss_bytes,$rss)
  $receipt.minimum_available_bytes=[Math]::Min([long]$receipt.minimum_available_bytes,$free)
  $receipt.minimum_disk_free_bytes=[Math]::Min([long]$receipt.minimum_disk_free_bytes,$disk)
  $receipt.active_owned_pids=@($owned.Keys);$receipt.updated_utc=[DateTime]::UtcNow.ToString('o')
  $reason=$null
  if($rss -gt 8589934592){$reason='OWNED_RSS_LIMIT'}elseif($free -lt 2147483648){$reason='AVAILABLE_MEMORY_FLOOR'}elseif($disk -lt 42949672960){$reason='DISK_FLOOR'}
  if($reason){
   $receipt.stop_reason=$reason;$receipt.state='RESOURCE_STOP';Save
   foreach($p in $owned.Values){$now=Get-CimInstance Win32_Process -Filter ("ProcessId="+$p.ProcessId) -ErrorAction SilentlyContinue;if($now -and $now.CreationDate -eq $p.CreationDate){Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue}}
   break
  }
  Save;Start-Sleep -Seconds 2
 }
}catch{$receipt.state='FAIL';$receipt.stop_reason=$_.Exception.Message;Save;throw}
finally{if($lease){$lease.Dispose();$receipt.lease_released=$true};if($receipt.state -eq 'LEASE_HELD'){$receipt.state='CLOSED'};Save}
