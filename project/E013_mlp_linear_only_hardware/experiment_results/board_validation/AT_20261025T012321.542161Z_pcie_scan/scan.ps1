param([ValidateSet('scan','restart')][string]$Action='scan')
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$OutputEncoding=[Console]::OutputEncoding
$id='PCI\VEN_10EE&DEV_9018&SUBSYS_000710EE&REV_00\4&3533FCBB&0&0008'
function Snapshot {
    $memory=@(Get-CimInstance Win32_PnPAllocatedResource | Where-Object {$_.Dependent -like '*VEN_10EE*'} | ForEach-Object {$_.Antecedent.ToString()})
    [ordered]@{utc=[DateTime]::UtcNow.ToString('o');pnp=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'PCI\VEN_10EE*'} | Select-Object Status,Class,FriendlyName,InstanceId,Problem);memory_references=$memory;memory_ranges=@(Get-CimInstance Win32_DeviceMemoryAddress | Where-Object {$memory -contains $_.ToString()} | Select-Object StartingAddress,EndingAddress,Name);driver=@(Get-CimInstance Win32_SystemDriver -Filter "Name='XDMA'" | Select-Object Name,State,Started)}
}
$r=[ordered]@{schema=1;action=$Action;instance=$id;before=(Snapshot);exit_code=$null;native_output=@();after=$null}
if(@($r.before.pnp | Where-Object {$_.InstanceId -eq $id}).Count -ne 1){throw 'Exact unique active9018 device missing; no action performed.'}
$ErrorActionPreference='Continue'
if($Action -eq 'scan'){$r.native_output=@(& pnputil.exe /scan-devices 2>&1 | ForEach-Object {$_.ToString()})}
else{$r.native_output=@(& pnputil.exe /restart-device $id 2>&1 | ForEach-Object {$_.ToString()})}
$r.exit_code=$LASTEXITCODE
$ErrorActionPreference='Stop'
$r.after=Snapshot
$r|ConvertTo-Json -Depth 9 -Compress
