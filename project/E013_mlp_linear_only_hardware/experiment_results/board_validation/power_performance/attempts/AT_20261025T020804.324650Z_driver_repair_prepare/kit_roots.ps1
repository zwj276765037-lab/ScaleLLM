$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);

$root='C:/pcie_demo/hap_tools/xdma_driver_win_9018_src'
$registry=@(foreach($p in @('HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots')){if(Test-Path -LiteralPath $p){[ordered]@{path=$p;values=(Get-ItemProperty -LiteralPath $p|Select-Object KitsRoot,KitsRoot81,KitsRoot10)}}})
$toolset='C:/Program Files (x86)/Microsoft Visual Studio/2019/BuildTools/MSBuild/Microsoft/VC/v160/Platforms/x64/PlatformToolsets/WindowsKernelModeDriver10.0'
$files=@(Get-ChildItem -LiteralPath $toolset -File -ErrorAction SilentlyContinue|ForEach-Object {[ordered]@{path=$_.FullName;content=[IO.File]::ReadAllText($_.FullName)}})
$paths=@(foreach($entry in $registry){foreach($p in @($entry.values.KitsRoot10,$entry.values.KitsRoot81)){if($p -and (Test-Path -LiteralPath $p)){[ordered]@{root=$p;children=@(Get-ChildItem -LiteralPath $p -Directory|Select-Object Name);versions=@(foreach($name in @('Include','Lib','bin','build')){$dir=Join-Path $p $name;if(Test-Path -LiteralPath $dir){[ordered]@{path=$dir;children=@(Get-ChildItem -LiteralPath $dir -Directory|Select-Object Name)}}})}}}})
[ordered]@{utc=[DateTime]::UtcNow.ToString('o');is_64bit=[Environment]::Is64BitProcess;registry=$registry;kit_paths=$paths;toolset_files=$files;inx=[IO.File]::ReadAllText((Join-Path $root 'sys/XDMA.inx'));root_children=@(Get-ChildItem -LiteralPath $root|Select-Object Name,Length,Mode)}|ConvertTo-Json -Depth 10
