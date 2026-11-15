$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$root='D:\ScaleLLM_final_model\dsp_all_board_20261115_001'
$owner=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json
$guard=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid)
if($owner.state -ne 'LEASE_HELD' -or -not $guard -or $guard.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){throw 'Exclusive board lease unavailable'}
$replay=Get-Content -LiteralPath (Join-Path $root 'replay\report.json') -Raw|ConvertFrom-Json
if($replay.status -ne 'PASS' -or $replay.commands.Count -ne 12 -or -not $replay.handles_closed -or -not $replay.final_quiescent){throw 'Twelve operator replays must finish successfully'}
$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$started=[DateTime]::UtcNow.ToString('o')
$p=Start-Process -FilePath 'D:\ScaleLLM_inference\py312_20261025T042311\python\python.exe' -ArgumentList @((Join-Path $root 'scripts\launch_inference.py')) -WorkingDirectory $root -RedirectStandardOutput (Join-Path $root 'environment\inference.stdout.txt') -RedirectStandardError (Join-Path $root 'environment\inference.stderr.txt') -PassThru
$handle=$p.Handle
$birth=(Get-CimInstance Win32_Process -Filter ('ProcessId='+$p.Id)).CreationDate.ToUniversalTime().ToString('o')
$roots=@(@{pid=$p.Id;birth=$birth;phase='full_original_16_request_inference'})
[IO.File]::WriteAllText((Join-Path $root 'active_processes.next.json'),(ConvertTo-Json -InputObject $roots),(New-Object Text.UTF8Encoding($false)))
Move-Item -LiteralPath (Join-Path $root 'active_processes.next.json') -Destination (Join-Path $root 'active_processes.json') -Force
'INFERENCE_PID='+$p.Id
$p.WaitForExit();$p.Refresh();$ec=[int]$p.ExitCode
$receipt=[ordered]@{schema='scalellm_dsp_inference_process_v1';pid=$p.Id;birth=$birth;started_utc=$started;finished_utc=[DateTime]::UtcNow.ToString('o');exitcode=$ec;fixed_wall_time_termination=$false;board_owner_pid=$owner.owner_pid}
[IO.File]::WriteAllText((Join-Path $root 'environment\inference_process_receipt.json'),($receipt|ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding($false)))
$receipt|ConvertTo-Json -Depth 5
Get-Content -LiteralPath (Join-Path $root 'environment\inference.stdout.txt') -Raw
Get-Content -LiteralPath (Join-Path $root 'environment\inference.stderr.txt') -Raw
exit $ec
