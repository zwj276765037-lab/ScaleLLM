$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$stage = 'C:\Users\dell\ScaleLLM_board_validation\M006_GU_66a305348d30_20261025'
$logs = Join-Path $stage ('program_' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
New-Item -ItemType Directory -Path $logs -ErrorAction Stop | Out-Null
$tool = 'D:\Xilinx\Vivado\2022.2\bin'
$bit = Join-Path $stage 'ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit'
$port = 33121
$target = 'localhost:33121/xilinx_tcf/Digilent/210308B76D50'
$receipt = [ordered]@{schema=1;scope='Actual volatile SRAM programming followed by read-only JTAG and PnP';started_utc=[DateTime]::UtcNow.ToString('o');logs=$logs;bit=$bit;target=$target;device='xcvu9p_0';program_exit=$null;probe_exit=$null;error=$null;server_pid=$null;server_creation=$null}
$server = $null
try {
    $hash = (Get-FileHash -LiteralPath $bit -Algorithm SHA256).Hash.ToLower()
    $receipt.bit_sha256 = $hash
    $receipt.bit_bytes = (Get-Item -LiteralPath $bit).Length
    if ($hash -ne '66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47' -or $receipt.bit_bytes -ne 80159259) { throw 'Bit identity mismatch.' }
    $receipt.pnp_before = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'PCI\VEN_10EE*' -or $_.InstanceId -like 'USB\VID_0403&PID_6014*' } | Select-Object Status, Class, FriendlyName, InstanceId, Problem)
    $receipt.vendor_processes_before = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(vivado|hw_server|cs_server)(\.exe)?$' } | Select-Object ProcessId, ParentProcessId, Name, CreationDate, CommandLine)
    if ($receipt.vendor_processes_before.Count -ne 0) { throw 'Existing vendor processes found; exclusive board access unconfirmed.' }
    if (@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue).Count) { throw 'Port33121 occupied.' }
    $receipt | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath (Join-Path $logs 'started.json') -Encoding UTF8
    $server = Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /c ' + $tool + '\hw_server.bat -s tcp::33121') -WorkingDirectory $logs -RedirectStandardOutput (Join-Path $logs 'hw_server.stdout.txt') -RedirectStandardError (Join-Path $logs 'hw_server.stderr.txt') -WindowStyle Hidden -PassThru
    $receipt.server_pid = $server.Id
    $receipt.server_creation = $server.StartTime.ToUniversalTime().ToString('o')
    $ready = $false
    for ($i=0; $i -lt 80; $i++) {
        if (@(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue).Count) { $ready=$true; break }
        $server.Refresh(); if ($server.HasExited) { throw 'Owned server exited.' }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'Owned server startup failed.' }
    & (Join-Path $tool 'vivado.bat') -mode batch -nojournal -log (Join-Path $logs 'program.vivado.log') -source (Join-Path $stage 'program_sram.tcl') -tclargs 'localhost:33121' $target 'xcvu9p_0' $bit 1> (Join-Path $logs 'program.stdout.txt') 2> (Join-Path $logs 'program.stderr.txt')
    $receipt.program_exit = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0 -or [IO.File]::ReadAllText((Join-Path $logs 'program.stdout.txt')) -notmatch '(?m)^BOARD_PROGRAM_COMMAND_COMPLETED') { throw 'Programming command failed or completion marker missing.' }
    & (Join-Path $tool 'vivado.bat') -mode batch -nojournal -log (Join-Path $logs 'configuration.vivado.log') -source (Join-Path $stage 'probe_jtag.tcl') -tclargs 'localhost:33121' $target 1> (Join-Path $logs 'configuration.stdout.txt') 2> (Join-Path $logs 'configuration.stderr.txt')
    $receipt.probe_exit = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0 -or [IO.File]::ReadAllText((Join-Path $logs 'configuration.stdout.txt')) -notmatch '(?m)^BOARD_PREFLIGHT_PROBE_COMPLETE') { throw 'Post-program configuration probe failed.' }
    $receipt.pnp_after = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'PCI\VEN_10EE*' } | Select-Object Status, Class, FriendlyName, InstanceId, Problem)
} catch { $receipt.error=$_.Exception.Message }
finally {
    if ($server) {
        $server.Refresh()
        if (-not $server.HasExited -and $server.StartTime.ToUniversalTime().ToString('o') -eq $receipt.server_creation) {
            $all=@(Get-CimInstance Win32_Process);$owned=@([int]$server.Id)
            for ($i=0; $i -lt 12; $i++) { $new=@($all | Where-Object { [int]$_.ParentProcessId -in $owned -and [int]$_.ProcessId -notin $owned } | ForEach-Object {[int]$_.ProcessId});if(-not $new.Count){break};$owned+=$new }
            $receipt.owned_processes_before_cleanup=@($all | Where-Object {[int]$_.ProcessId -in $owned} | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine)
            $receipt.cleanup=@(& taskkill.exe /PID $server.Id /T /F 2>&1 | ForEach-Object {$_.ToString()});$receipt.cleanup_exit=$LASTEXITCODE
        }
    }
    $receipt.ended_utc=[DateTime]::UtcNow.ToString('o')
    $receipt | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $logs 'receipt.json') -Encoding UTF8
}
$receipt | ConvertTo-Json -Depth 10 -Compress
if ($receipt.error) { exit 1 }
