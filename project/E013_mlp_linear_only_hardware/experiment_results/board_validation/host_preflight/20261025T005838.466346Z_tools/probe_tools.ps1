$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$result = [ordered]@{ schema = 1; utc = [DateTime]::UtcNow.ToString('o'); probe = 'tools'; errors = @() }
$result.commands = @()
foreach ($name in @('vivado', 'vivado.bat', 'hw_server', 'hw_server.bat', 'hw_server.exe', 'xsdb', 'usbipd', 'wsl', 'python', 'python3', 'xdma_test')) {
    $result.commands += @(Get-Command $name -ErrorAction SilentlyContinue | Select-Object Name, Source, CommandType)
}
$result.vendor_path_entries = @($env:Path.Split(';') | Where-Object { $_ -match 'Xilinx|AMD|Vivado|Digilent|XRT|Vitis' })
$roots = @('C:\Xilinx', 'C:\AMD', 'D:\Xilinx', 'D:\AMD', 'E:\Xilinx', 'E:\AMD', 'C:\Program Files\Xilinx', 'C:\Program Files\AMD', 'C:\Program Files (x86)\Xilinx', 'C:\Program Files (x86)\Digilent', 'D:\FPGA', 'C:\tools', 'D:\tools')
$result.tool_root_listing = @()
$result.tool_files = @()
foreach ($root in $roots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    try {
        $children = @(Get-ChildItem -LiteralPath $root -Directory -ErrorAction Stop)
        $result.tool_root_listing += [ordered]@{ root = $root; children = @($children | Select-Object Name, FullName) }
        $bases = @($root)
        foreach ($child in $children) {
            $bases += $child.FullName
            if ($child.Name -match 'Vivado|Vitis|Lab|Hardware|20\d\d|Xilinx|AMD') {
                $bases += @(Get-ChildItem -LiteralPath $child.FullName -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
            }
        }
        foreach ($base in ($bases | Select-Object -Unique)) {
            foreach ($suffix in @('bin\vivado.bat', 'bin\hw_server.bat', 'bin\hw_server.exe', 'bin\unwrapped\win64.o\hw_server.exe', 'bin\unwrapped\win64.o\vivado.exe')) {
                $file = Join-Path $base $suffix
                if (Test-Path -LiteralPath $file -PathType Leaf) {
                    $result.tool_files += @(Get-Item -LiteralPath $file | Select-Object FullName, Length, LastWriteTimeUtc, @{Name='FileVersion';Expression={$_.VersionInfo.FileVersion}})
                }
            }
        }
    } catch { $result.errors += $root + ': ' + $_.Exception.Message }
}
try {
    $result.installed_vendor_products = @(foreach ($registry in @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
        Get-ItemProperty -Path $registry -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'Xilinx|Vivado|Vitis|Digilent|XDMA|XRT|Jungo|FTDI|USB Serial' } | Select-Object DisplayName, DisplayVersion, InstallLocation, Publisher
    })
} catch { $result.errors += 'installed-products: ' + $_.Exception.Message }
try { $result.vendor_processes = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(hw_server|vivado|xsdb|cs_server)(\.exe)?$' } | Select-Object ProcessId, Name, ExecutablePath, CommandLine) } catch { $result.errors += 'processes: ' + $_.Exception.Message }
try { $result.tcp_3121 = @(Get-NetTCPConnection -LocalPort 3121 -ErrorAction SilentlyContinue | Select-Object State, LocalAddress, LocalPort, OwningProcess) } catch { $result.errors += 'tcp3121: ' + $_.Exception.Message }
$result | ConvertTo-Json -Depth 8 -Compress
