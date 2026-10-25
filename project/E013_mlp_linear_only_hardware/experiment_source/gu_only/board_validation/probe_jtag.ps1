param([string]$StageDirectory = $PSScriptRoot, [int]$Port = 33121)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$tool = 'D:\Xilinx\Vivado\2022.2\bin'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$logs = Join-Path $StageDirectory ('jtag_probe_' + $stamp)
New-Item -ItemType Directory -Path $logs -ErrorAction Stop | Out-Null
$receipt = [ordered]@{ schema=1; scope='read-only JTAG enumeration'; utc=[DateTime]::UtcNow.ToString('o'); server_port=$Port; logs=$logs; server_pid=$null; server_creation=$null; target_exit=$null; device_exit=$null; selected_target=$null; error=$null; cleanup=@() }
$server = $null
try {
    if (@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue).Count) { throw "Port $Port is already in use; no existing server will be used or stopped." }
    $server = Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /c ' + $tool + '\hw_server.bat -s tcp::' + $Port) -WorkingDirectory $logs -RedirectStandardOutput (Join-Path $logs 'hw_server.stdout.txt') -RedirectStandardError (Join-Path $logs 'hw_server.stderr.txt') -WindowStyle Hidden -PassThru
    $receipt.server_pid = $server.Id
    $receipt.server_creation = $server.StartTime.ToUniversalTime().ToString('o')
    $ready = $false
    for ($i=0; $i -lt 80; $i++) {
        if (@(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue).Count) { $ready=$true; break }
        $server.Refresh()
        if ($server.HasExited) { throw 'Owned hw_server wrapper exited before listening.' }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'Owned hw_server did not listen within the startup probe.' }
    $source = Join-Path $StageDirectory 'probe_jtag.tcl'
    & (Join-Path $tool 'vivado.bat') -mode batch -nojournal -log (Join-Path $logs 'targets.vivado.log') -source $source -tclargs ('localhost:' + $Port) 1> (Join-Path $logs 'targets.stdout.txt') 2> (Join-Path $logs 'targets.stderr.txt')
    $receipt.target_exit = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'Hardware Manager target enumeration failed.' }
    $lines = @(Get-Content -LiteralPath (Join-Path $logs 'targets.stdout.txt') | Where-Object { $_ -match '^BOARD_PREFLIGHT_TARGET ' })
    $targets = @($lines | ForEach-Object { $_.Substring('BOARD_PREFLIGHT_TARGET '.Length).Trim().Trim('{','}') } | Where-Object { $_ -like '*/210308B76D50' })
    if ($targets.Count -ne 1) { throw ('Expected exactly one target with USB serial 210308B76D50; candidates=' + ($targets -join ',')) }
    $receipt.selected_target = $targets[0]
    & (Join-Path $tool 'vivado.bat') -mode batch -nojournal -log (Join-Path $logs 'devices.vivado.log') -source $source -tclargs ('localhost:' + $Port) $targets[0] 1> (Join-Path $logs 'devices.stdout.txt') 2> (Join-Path $logs 'devices.stderr.txt')
    $receipt.device_exit = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'Hardware Manager device enumeration failed.' }
    $deviceText = Get-Content -LiteralPath (Join-Path $logs 'devices.stdout.txt') -Raw
    if ($deviceText -notmatch '(?m)^BOARD_PREFLIGHT_PROBE_COMPLETE' -or $deviceText -notmatch '(?m)^BOARD_PREFLIGHT_DEVICE .*xcvu9p') { throw 'Device probe did not confirm an xcvu9p chain and completion marker.' }
} catch { $receipt.error = $_.Exception.Message }
finally {
    if ($server) {
        $server.Refresh()
        if (-not $server.HasExited -and $server.StartTime.ToUniversalTime().ToString('o') -eq $receipt.server_creation) {
            $all = @(Get-CimInstance Win32_Process)
            $ownedIds = @([int]$server.Id)
            for ($level=0; $level -lt 12; $level++) {
                $children = @($all | Where-Object { [int]$_.ParentProcessId -in $ownedIds -and [int]$_.ProcessId -notin $ownedIds } | ForEach-Object { [int]$_.ProcessId })
                if (-not $children.Count) { break }
                $ownedIds += $children
            }
            $receipt.owned_processes_before_cleanup = @($all | Where-Object { [int]$_.ProcessId -in $ownedIds } | Select-Object ProcessId, ParentProcessId, Name, CreationDate, ExecutablePath, CommandLine)
            $receipt.cleanup = @(& taskkill.exe /PID $server.Id /T /F 2>&1 | ForEach-Object { $_.ToString() })
            $receipt.cleanup_exit = $LASTEXITCODE
            $after = @(Get-CimInstance Win32_Process)
            $receipt.owned_survivors = @($after | Where-Object { [int]$_.ProcessId -in $ownedIds } | Select-Object ProcessId, ParentProcessId, Name, CreationDate)
        }
    }
    $receipt.remaining_listener = @(Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess)
    $receipt.ended_utc = [DateTime]::UtcNow.ToString('o')
    $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $logs 'receipt.json') -Encoding UTF8
}
$receipt | ConvertTo-Json -Depth 8 -Compress
if ($receipt.error) { exit 1 }
