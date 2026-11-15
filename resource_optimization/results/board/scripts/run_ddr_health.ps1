$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$root='D:\ScaleLLM_final_model\dsp_all_board_20261115_001'
$owner=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json
if($owner.state -ne 'LEASE_HELD'){throw 'Exclusive board lease unavailable'}
$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$p=Start-Process -FilePath 'D:\ScaleLLM_inference\py312_20261025T042311\python\python.exe' -ArgumentList @((Join-Path $root 'scripts\check_ddr.py')) -WorkingDirectory $root -RedirectStandardOutput (Join-Path $root 'environment\ddr_health.stdout.txt') -RedirectStandardError (Join-Path $root 'environment\ddr_health.stderr.txt') -PassThru
$handle=$p.Handle
$birth=(Get-CimInstance Win32_Process -Filter ('ProcessId='+$p.Id)).CreationDate.ToUniversalTime().ToString('o')
$roots=@(@{pid=$p.Id;birth=$birth;phase='post_program_ddr_health'})
[IO.File]::WriteAllText((Join-Path $root 'active_processes.next.json'),(ConvertTo-Json -InputObject $roots),(New-Object Text.UTF8Encoding($false)))
Move-Item -LiteralPath (Join-Path $root 'active_processes.next.json') -Destination (Join-Path $root 'active_processes.json') -Force
$p.WaitForExit();$p.Refresh();$ec=[int]$p.ExitCode
Get-Content -LiteralPath (Join-Path $root 'environment\ddr_health.stdout.txt') -Raw
Get-Content -LiteralPath (Join-Path $root 'environment\ddr_health.stderr.txt') -Raw
[IO.File]::WriteAllText((Join-Path $root 'environment\ddr_health.exitcode.txt'),[string]$ec)
exit $ec
