$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$root='D:\ScaleLLM_final_model\dsp_all_power_20261115_001'
$id='PCI\VEN_10EE&DEV_9018&SUBSYS_000710EE&REV_00\4&3533FCBB&0&0008'
$owner=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json
$guard=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid)
if($owner.state -ne 'LEASE_HELD' -or -not $guard -or $guard.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){throw 'Exclusive board lease unavailable'}
$matches=@(Get-PnpDevice -PresentOnly|Where-Object InstanceId -like 'PCI\VEN_10EE&DEV_9018*')
if($matches.Count -ne 1 -or $matches[0].InstanceId -ne $id){throw 'XDMA device is not uniquely identified'}
$roots=Get-Content -LiteralPath (Join-Path $root 'active_processes.json') -Raw|ConvertFrom-Json
foreach($entry in $roots){$live=Get-CimInstance Win32_Process -Filter ('ProcessId='+$entry.pid) -ErrorAction SilentlyContinue;if($live -and $live.CreationDate.ToUniversalTime().ToString('o') -eq $entry.birth){throw 'Owned hardware process remains live'}}
function Snapshot {
 $pnp=Get-PnpDevice -InstanceId $id
 $entity=Get-CimInstance Win32_PnPEntity|Where-Object DeviceID -eq $id
 $driver=Get-CimInstance Win32_PnPSignedDriver|Where-Object DeviceID -eq $id
 [ordered]@{time_utc=[DateTime]::UtcNow.ToString('o');pnp=($pnp|Select-Object Status,Class,FriendlyName,InstanceId,Problem,Present);entity=($entity|Select-Object Name,Status,ConfigManagerErrorCode,Service,PNPDeviceID);driver=($driver|Select-Object DeviceID,DriverVersion,InfName,DriverProviderName);properties=@(Get-PnpDeviceProperty -InstanceId $id|Select-Object KeyName,Type,Data);driver_sha256=(Get-FileHash -LiteralPath 'C:\Windows\System32\drivers\XDMA.sys' -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$before=Snapshot
[IO.File]::WriteAllText((Join-Path $root 'environment\pnp_recovery_before.json'),($before|ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))
$restartOutput=(& pnputil /restart-device $id 2>&1|Out-String)
$restartExit=[int]$LASTEXITCODE
Start-Sleep -Seconds 3
$after=Snapshot
[IO.File]::WriteAllText((Join-Path $root 'environment\pnp_recovery_after.json'),($after|ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))
$receipt=[ordered]@{schema='scalellm_exact_xdma_restart_v1';instance_id=$id;native_exitcode=$restartExit;stdout=$restartOutput;driver_sha256_before=$before.driver_sha256;driver_sha256_after=$after.driver_sha256;before=$before.pnp;after=$after.pnp;board_owner_pid=$owner.owner_pid;whole_host_reboot=$false;driver_installed_or_modified=$false}
[IO.File]::WriteAllText((Join-Path $root 'environment\pnp_recovery_receipt.json'),($receipt|ConvertTo-Json -Depth 6),(New-Object Text.UTF8Encoding($false)))
$receipt|ConvertTo-Json -Depth 6
exit $restartExit
