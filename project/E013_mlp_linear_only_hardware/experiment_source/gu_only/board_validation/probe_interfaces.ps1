$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$result = [ordered]@{ schema = 1; utc = [DateTime]::UtcNow.ToString('o'); probe = 'interfaces'; errors = @() }
try {
    $result.drivers = @(Get-CimInstance Win32_SystemDriver | Where-Object { $_.Name -match 'xdma|xpc|windrvr|libusb|digilent|ftdi|ftdibus|jungo|xilinx|xocl|xclmgmt' -or $_.DisplayName -match 'Xilinx|Digilent|XDMA|FTDI|Jungo' } | Select-Object Name, DisplayName, State, Started, StartMode, PathName, ServiceType)
    $result.signed_device_drivers = @(Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceID -like 'PCI\VEN_10EE*' -or ($_.DeviceID -like 'USB\*' -and $_.DeviceID -match 'VID_(03FD|0403|1443)') } | Select-Object DeviceName, DeviceID, DriverProviderName, DriverVersion, DriverDate, InfName, IsSigned, Signer)
} catch { $result.errors += 'drivers: ' + $_.Exception.Message }
try {
    $classes = @(Get-ChildItem -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceClasses')
    $result.device_interface_registry = @(foreach ($class in $classes) {
        Get-ChildItem -LiteralPath $class.PSPath -ErrorAction SilentlyContinue | Where-Object { $_.PSChildName -match 'VEN_10EE|VID_03FD|VID_0403|VID_1443|XDMA|XILINX|DIGILENT' } | Select-Object PSChildName, Name
    })
    $result.interface_scope = 'Registry symbolic interface entries only; this does not prove CreateFile access or a working DMA channel.'
} catch { $result.errors += 'device-interface-registry: ' + $_.Exception.Message }
try {
    if (Get-Command wsl.exe -ErrorAction SilentlyContinue) {
        $lines = @(& wsl.exe --list --verbose 2>&1 | ForEach-Object { $_.ToString().Replace([string][char]0, '') })
        $result.wsl_list = [ordered]@{ exit_code = $LASTEXITCODE; lines = $lines }
        $running = @(& wsl.exe --list --running --quiet 2>&1 | ForEach-Object { $_.ToString().Replace([string][char]0, '').Trim() } | Where-Object { $_ })
        $result.wsl_running = [ordered]@{ exit_code = $LASTEXITCODE; lines = $running }
        if ($LASTEXITCODE -eq 0) {
            $result.wsl_device_probes = @(foreach ($distro in $running) {
                $shell = 'uname -a; for p in /dev/xdma* /dev/xvc* /dev/bus/usb; do if [ -e "$p" ]; then ls -ld "$p"; fi; done; if command -v lspci >/dev/null 2>&1; then lspci -Dnn -d 10ee:; fi'
                $native = @(& wsl.exe -d $distro --exec sh -lc $shell 2>&1 | ForEach-Object { $_.ToString().Replace([string][char]0, '') })
                [ordered]@{ distribution = $distro; exit_code = $LASTEXITCODE; lines = $native }
            })
        }
    } else { $result.wsl_list = 'wsl.exe not found' }
} catch { $result.errors += 'WSL: ' + $_.Exception.Message }
try {
    if (Get-Command usbipd.exe -ErrorAction SilentlyContinue) {
        $usbip = @(& usbipd.exe list 2>&1 | ForEach-Object { $_.ToString() })
        $result.usbipd_list = [ordered]@{ exit_code = $LASTEXITCODE; lines = $usbip }
    } else { $result.usbipd_list = 'usbipd.exe not found' }
} catch { $result.errors += 'usbipd: ' + $_.Exception.Message }
$result | ConvertTo-Json -Depth 9 -Compress
