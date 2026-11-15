$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$RunRoot='D:\ScaleLLM_final_model\dsp_all_board_20261115_001'
$owner=Get-Content -LiteralPath (Join-Path $RunRoot 'board_owner.json') -Raw|ConvertFrom-Json
$guard=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid)
if($owner.state -ne 'LEASE_HELD' -or -not $guard -or $guard.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){throw 'Board lease is not live'}
Start-Sleep -Seconds 3
$updated=Get-Content -LiteralPath (Join-Path $RunRoot 'board_owner.json') -Raw|ConvertFrom-Json
if($updated.state -ne 'LEASE_HELD' -or $updated.updated_utc -eq $owner.updated_utc){throw 'Resource guardian did not progress'}
$bit=Join-Path $RunRoot 'bitstream\ScaleLLM_Final_Decode16_80MHz.bit'
$expected='5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7'
if((Get-Item -LiteralPath $bit).Length -ne 80159263 -or (Get-FileHash -LiteralPath $bit -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected){throw 'Candidate bit identity differs'}
$target='localhost:3121/xilinx_tcf/Digilent/210308B76D50';$device='xcvu9p_0'
$roots=@();$ownedServer=$null
$listening=@(Get-NetTCPConnection -LocalPort 3121 -State Listen -ErrorAction SilentlyContinue)
if(-not $listening.Count){
 $server=Start-Process -FilePath $env:ComSpec -ArgumentList '/c D:\Xilinx\Vivado\2022.2\bin\hw_server.bat -s tcp::3121' -WorkingDirectory $RunRoot -RedirectStandardOutput (Join-Path $RunRoot 'program\hw_server.stdout.txt') -RedirectStandardError (Join-Path $RunRoot 'program\hw_server.stderr.txt') -PassThru
 $serverHandle=$server.Handle
 for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 500;$listening=@(Get-NetTCPConnection -LocalPort 3121 -State Listen -ErrorAction SilentlyContinue);if($listening.Count){break}}
 if(-not $listening.Count){throw 'Owned hw_server did not listen within communication startup timeout'}
 $serverNative=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listening[0].OwningProcess)
 if($serverNative.Name -notmatch '^hw_server'){throw 'Unexpected listener on hardware-server port'}
 $ownedServer=@{pid=[int]$serverNative.ProcessId;birth=$serverNative.CreationDate.ToUniversalTime().ToString('o');command=$serverNative.CommandLine;phase='owned_hw_server'}
 $roots+=$ownedServer
 [IO.File]::WriteAllText((Join-Path $RunRoot 'program\hw_server_owner.json'),($ownedServer|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
}
$started=[DateTime]::UtcNow
$arguments='/c D:\Xilinx\Vivado\2022.2\bin\vivado.bat -mode batch -notrace -source '+(Join-Path $RunRoot 'scripts\program_sram.tcl')+' -log '+(Join-Path $RunRoot 'program\vivado.log')+' -journal '+(Join-Path $RunRoot 'program\vivado.jou')+' -tclargs localhost:3121 '+$target+' '+$device+' '+$bit
$p=Start-Process -FilePath $env:ComSpec -ArgumentList $arguments -WorkingDirectory $RunRoot -RedirectStandardOutput (Join-Path $RunRoot 'program\stdout.txt') -RedirectStandardError (Join-Path $RunRoot 'program\stderr.txt') -PassThru
$handle=$p.Handle;$birth=(Get-CimInstance Win32_Process -Filter ('ProcessId='+$p.Id)).CreationDate.ToUniversalTime().ToString('o');$roots+=@{pid=$p.Id;birth=$birth;phase='candidate_sram_program'}
[IO.File]::WriteAllText((Join-Path $RunRoot 'active_processes.next.json'),(ConvertTo-Json -InputObject $roots),(New-Object Text.UTF8Encoding($false)));Move-Item -LiteralPath (Join-Path $RunRoot 'active_processes.next.json') -Destination (Join-Path $RunRoot 'active_processes.json') -Force
'PROGRAM_PID='+$p.Id;$p.WaitForExit();$p.Refresh();$exit=[int]$p.ExitCode
$log=Get-Content -LiteralPath (Join-Path $RunRoot 'program\stdout.txt') -Raw
$receipt=[ordered]@{schema='scalellm_dsp_candidate_sram_program_v1';status='FAIL';host=$env:COMPUTERNAME;server='localhost:3121';target=$target;device=$device;part='xcvu9p';bit_path=$bit;bit_sha256=$expected;bit_bytes=80159263;started_utc=$started.ToString('o');finished_utc=[DateTime]::UtcNow.ToString('o');native_pid=$p.Id;native_birth=$birth;exitcode=$exit;volatile_sram=$true;configuration_flash_written=$false;board_owner_pid=$owner.owner_pid}
if($exit -eq 0 -and $log.Contains('FINAL_SRAM_PROGRAM_COMPLETED')){$receipt.status='PASS'}
[IO.File]::WriteAllText((Join-Path $RunRoot 'program\receipt.json'),($receipt|ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
$receipt|ConvertTo-Json -Depth 8
$log
Get-Content -LiteralPath (Join-Path $RunRoot 'program\stderr.txt') -Raw
if($ownedServer){$live=Get-CimInstance Win32_Process -Filter ('ProcessId='+$ownedServer.pid) -ErrorAction SilentlyContinue;if($live -and $live.CreationDate.ToUniversalTime().ToString('o') -eq $ownedServer.birth){Stop-Process -Id $ownedServer.pid -Force}}
if($receipt.status -ne 'PASS'){throw 'Candidate SRAM programming failed'}
