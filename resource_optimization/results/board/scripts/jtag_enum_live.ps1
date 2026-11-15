$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$RunRoot='D:\ScaleLLM_final_model\dsp_all_board_20261115_001'
$owner=Get-Content -LiteralPath (Join-Path $RunRoot 'board_owner.json') -Raw|ConvertFrom-Json
$guard=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid)
if($owner.state -ne 'LEASE_HELD' -or -not $guard -or $guard.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){throw 'Board lease owner is not live'}
$py='D:\ScaleLLM_inference\py312_20261025T042311\python\python.exe'
$p=Start-Process -FilePath $py -ArgumentList @((Join-Path $RunRoot 'scripts\read_only_device_observe.py')) -WorkingDirectory $RunRoot -RedirectStandardOutput (Join-Path $RunRoot 'environment\preprogram_csr.json') -RedirectStandardError (Join-Path $RunRoot 'environment\preprogram_csr.stderr.txt') -PassThru
$handle=$p.Handle;$p.WaitForExit();$p.Refresh();'PREPROGRAM_OBSERVATION_EXIT='+$p.ExitCode
Get-Content -LiteralPath (Join-Path $RunRoot 'environment\preprogram_csr.json') -Raw
$existing=@(Get-NetTCPConnection -LocalPort 3121 -State Listen -ErrorAction SilentlyContinue)
$roots=@()
if(-not $existing.Count){
 $server=Start-Process -FilePath $env:ComSpec -ArgumentList '/c D:\Xilinx\Vivado\2022.2\bin\hw_server.bat -s tcp::3121' -WorkingDirectory $RunRoot -RedirectStandardOutput (Join-Path $RunRoot 'environment\hw_server.stdout.txt') -RedirectStandardError (Join-Path $RunRoot 'environment\hw_server.stderr.txt') -PassThru
 $serverHandle=$server.Handle;$birth=(Get-CimInstance Win32_Process -Filter ('ProcessId='+$server.Id)).CreationDate.ToUniversalTime().ToString('o')
 $roots+=@{pid=$server.Id;birth=$birth;phase='owned_hw_server'}
 [IO.File]::WriteAllText((Join-Path $RunRoot 'owned_hw_server.json'),(@{pid=$server.Id;birth=$birth;started_by_this_task=$true}|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
 for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 500;if(@(Get-NetTCPConnection -LocalPort 3121 -State Listen -ErrorAction SilentlyContinue).Count){break}}
}
$v=Start-Process -FilePath $env:ComSpec -ArgumentList ('/c D:\Xilinx\Vivado\2022.2\bin\vivado.bat -mode batch -notrace -source '+(Join-Path $RunRoot 'scripts\jtag_inventory.tcl')+' -log '+(Join-Path $RunRoot 'environment\jtag_inventory.log')+' -journal '+(Join-Path $RunRoot 'environment\jtag_inventory.jou')) -WorkingDirectory $RunRoot -RedirectStandardOutput (Join-Path $RunRoot 'environment\jtag_inventory.stdout.txt') -RedirectStandardError (Join-Path $RunRoot 'environment\jtag_inventory.stderr.txt') -PassThru
$handle=$v.Handle;$birth=(Get-CimInstance Win32_Process -Filter ('ProcessId='+$v.Id)).CreationDate.ToUniversalTime().ToString('o');$roots+=@{pid=$v.Id;birth=$birth;phase='read_only_jtag_inventory'}
[IO.File]::WriteAllText((Join-Path $RunRoot 'active_processes.json'),(ConvertTo-Json -InputObject $roots),(New-Object Text.UTF8Encoding($false)))
'JTAG_INVENTORY_PID='+$v.Id;$v.WaitForExit();$v.Refresh();'JTAG_INVENTORY_EXIT='+$v.ExitCode
[IO.File]::WriteAllText((Join-Path $RunRoot 'environment\jtag_inventory.exitcode.txt'),[string]$v.ExitCode)
Get-Content -LiteralPath (Join-Path $RunRoot 'environment\jtag_inventory.stdout.txt') -Raw
Get-Content -LiteralPath (Join-Path $RunRoot 'environment\jtag_inventory.stderr.txt') -Raw
if($v.ExitCode -ne 0){throw 'JTAG inventory failed'}
