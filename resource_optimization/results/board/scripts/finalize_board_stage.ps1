$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$root='D:\ScaleLLM_final_model\dsp_all_board_20261115_001'
$encoding=New-Object Text.UTF8Encoding($false)
$owner=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json
$guard=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid)
if($owner.state -ne 'LEASE_HELD' -or -not $guard -or $guard.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){throw 'Board guardian is not live'}
$run=Get-Content -LiteralPath (Join-Path $root 'inference\run.json') -Raw|ConvertFrom-Json
$process=Get-Content -LiteralPath (Join-Path $root 'environment\inference_process_receipt.json') -Raw|ConvertFrom-Json
$regression=Get-Content -LiteralPath (Join-Path $root 'inference\regression.json') -Raw|ConvertFrom-Json
$replay=Get-Content -LiteralPath (Join-Path $root 'replay\report.json') -Raw|ConvertFrom-Json
if($run.execution -ne 'COMPLETE' -or -not $run.handles_closed -or -not $run.final_quiescent -or $process.exitcode -ne 0 -or $regression.status -ne 'PASS' -or $regression.hardware_commands -ne 3200 -or $replay.status -ne 'PASS' -or $replay.commands.Count -ne 12){throw 'Required board tests have not completed successfully'}
$roots=Get-Content -LiteralPath (Join-Path $root 'active_processes.json') -Raw|ConvertFrom-Json
foreach($entry in $roots){$live=Get-CimInstance Win32_Process -Filter ('ProcessId='+$entry.pid) -ErrorAction SilentlyContinue;if($live -and $live.CreationDate.ToUniversalTime().ToString('o') -eq $entry.birth){throw 'Native test process remains live'}}
$treeFile=Join-Path $root 'environment\inference_owned_tree.json'
if(Test-Path -LiteralPath $treeFile){$tree=Get-Content -LiteralPath $treeFile -Raw|ConvertFrom-Json;foreach($entry in $tree){$live=Get-CimInstance Win32_Process -Filter ('ProcessId='+$entry.pid) -ErrorAction SilentlyContinue;if($live -and $live.CreationDate.ToUniversalTime().ToString('o') -eq $entry.birth){throw 'Owned inference descendant remains live'}}}
$bit=Join-Path $root 'bitstream\ScaleLLM_Final_Decode16_80MHz.bit'
$expected='5d78519aa10695be564f668d5a41a0e5554e282c31d39f648534a7dc01ab72f7'
if((Get-FileHash -LiteralPath $bit -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected){throw 'Last-programmed candidate bit file changed'}
$program=Get-Content -LiteralPath (Join-Path $root 'program\receipt.json') -Raw|ConvertFrom-Json
if($program.status -ne 'PASS' -or $program.bit_sha256 -ne $expected -or -not $program.volatile_sram -or $program.configuration_flash_written){throw 'Candidate programming receipt differs'}
$serverOwner=Get-Content -LiteralPath (Join-Path $root 'program\hw_server_owner.json') -Raw|ConvertFrom-Json
$serviceOwners=@(@{pid=$program.native_pid;birth=$program.native_birth;phase='candidate_program_root'},$serverOwner)
$allProcesses=@(Get-CimInstance Win32_Process)
$serviceSurvivors=@()
foreach($entry in $serviceOwners){$live=$allProcesses|Where-Object{[int]$_.ProcessId -eq [int]$entry.pid -and $_.CreationDate.ToUniversalTime().ToString('o') -eq $entry.birth}|Select-Object -First 1;if($live){$serviceSurvivors+=$entry}}
$hardwareServices=@($allProcesses|Where-Object{$_.Name -match '^(vivado|hw_server|cs_server)\.exe$'}|ForEach-Object{[ordered]@{pid=[int]$_.ProcessId;parent_pid=[int]$_.ParentProcessId;name=$_.Name;birth=$_.CreationDate.ToUniversalTime().ToString('o');command=$_.CommandLine}})
$candidateServiceSurvivors=@($hardwareServices|Where-Object{$_.command -and $_.command.Contains($root)})
$serviceReceipt=[ordered]@{schema='scalellm_dsp_owned_service_closure_v1';verified_utc=[DateTime]::UtcNow.ToString('o');original_ownership=$serviceOwners;owned_service_survivors=$serviceSurvivors;candidate_path_service_survivors=$candidateServiceSurvivors;observed_hardware_services=$hardwareServices}
[IO.File]::WriteAllText((Join-Path $root 'environment\owned_services_final_audit.json'),($serviceReceipt|ConvertTo-Json -Depth 7),$encoding)
if($serviceSurvivors.Count -or $candidateServiceSurvivors.Count){throw 'Task-owned programming service remains live'}
$candidate=Get-Content -LiteralPath (Join-Path $root 'runtime\candidate_source_identity.json') -Raw|ConvertFrom-Json
$verifiedFiles=[ordered]@{}
foreach($entry in $candidate.candidate_files.PSObject.Properties){$path=Join-Path (Join-Path $root 'runtime') $entry.Name;$size=(Get-Item -LiteralPath $path).Length;$hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant();if($size -ne $entry.Value.bytes -or $hash -ne $entry.Value.sha256){throw ('Candidate source changed '+$entry.Name)};$verifiedFiles[$entry.Name]=@{bytes=$size;sha256=$hash}}
$runtimeReceipt=[ordered]@{schema='scalellm_dsp_runtime_identity_after_v1';status='PASS';verified_utc=[DateTime]::UtcNow.ToString('o');file_count=$verifiedFiles.Count;files=$verifiedFiles}
[IO.File]::WriteAllText((Join-Path $root 'environment\runtime_identity_after.json'),($runtimeReceipt|ConvertTo-Json -Depth 6),$encoding)
$p=Start-Process -FilePath 'D:\ScaleLLM_inference\py312_20261025T042311\python\python.exe' -ArgumentList @((Join-Path $root 'scripts\read_only_device.py')) -WorkingDirectory $root -RedirectStandardOutput (Join-Path $root 'environment\final_identity.stdout.txt') -RedirectStandardError (Join-Path $root 'environment\final_identity.stderr.txt') -PassThru
$handle=$p.Handle
$birth=$p.StartTime.ToUniversalTime().ToString('o')
$finalRoots=@(@{pid=$p.Id;birth=$birth;phase='final_read_only_identity'})
[IO.File]::WriteAllText((Join-Path $root 'active_processes.next.json'),(ConvertTo-Json -InputObject $finalRoots),$encoding)
Move-Item -LiteralPath (Join-Path $root 'active_processes.next.json') -Destination (Join-Path $root 'active_processes.json') -Force
$p.WaitForExit();$p.Refresh();$exit=[int]$p.ExitCode
[IO.File]::WriteAllText((Join-Path $root 'environment\final_identity.exitcode.txt'),[string]$exit,$encoding)
if($exit -ne 0){Get-Content -LiteralPath (Join-Path $root 'environment\final_identity.stderr.txt') -Raw;throw 'Final board identity/idle check failed'}
[IO.File]::WriteAllText((Join-Path $root 'active_processes.json'),'[]',$encoding)
Start-Sleep -Seconds 3
$latest=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json
if($latest.state -ne 'LEASE_HELD' -or @($latest.active_owned_pids).Count -ne 0 -or $latest.stop_reason){throw 'Board guardian not quiescent before lease release'}
[IO.File]::WriteAllText((Join-Path $root 'guardian.stop'),[DateTime]::UtcNow.ToString('o'),$encoding)
for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 500;$closed=Get-Content -LiteralPath (Join-Path $root 'board_owner.json') -Raw|ConvertFrom-Json;if($closed.state -eq 'CLOSED' -and $closed.lease_released){break}}
if($closed.state -ne 'CLOSED' -or -not $closed.lease_released){throw 'Board lease closure receipt unavailable'}
for($i=0;$i -lt 20;$i++){$guardLive=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid) -ErrorAction SilentlyContinue;if(-not $guardLive -or $guardLive.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){break};Start-Sleep -Milliseconds 250}
if($guardLive -and $guardLive.CreationDate.ToUniversalTime().ToString('o') -eq $owner.owner_birth){throw 'Closed guardian process did not exit'}
$receipt=[ordered]@{schema='scalellm_dsp_board_stage_closure_v1';status='PASS';closed_utc=[DateTime]::UtcNow.ToString('o');host=$env:COMPUTERNAME;program_status=$program.status;last_programmed_bit_sha256=$expected;candidate_left_resident_in_volatile_sram=$true;configuration_flash_written=$false;whole_host_reboot=$false;driver_installed_or_modified=$false;operator_replays=12;operator_byte_exact='PASS';original_requests=16;generated_tokens=512;complete_rounds=50;hardware_commands=3200;token_id_regression='PASS';whole_model_independent_numerical_oracle='NOT_ESTABLISHED';native_inference_exitcode=$process.exitcode;final_identity_exitcode=$exit;handles_closed=$true;final_quiescent=$true;owned_survivors=@();guardian=$closed}
[IO.File]::WriteAllText((Join-Path $root 'board_stage_closure.json'),($receipt|ConvertTo-Json -Depth 8),$encoding)
$receipt|ConvertTo-Json -Depth 8
