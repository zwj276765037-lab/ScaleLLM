$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$result = [ordered]@{ schema = 1; utc = [DateTime]::UtcNow.ToString('o'); probe = 'device'; errors = @() }
try {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem
    $cs = Get-CimInstance -ClassName Win32_ComputerSystem
    $result.system = [ordered]@{ computer = $env:COMPUTERNAME; user = $env:USERNAME; ps_version = $PSVersionTable.PSVersion.ToString(); caption = $os.Caption; version = $os.Version; build = $os.BuildNumber; architecture = $os.OSArchitecture; manufacturer = $cs.Manufacturer; model = $cs.Model }
} catch { $result.errors += 'system: ' + $_.Exception.Message }
try {
    $devices = @(Get-CimInstance -ClassName Win32_PnPEntity)
    $result.pcie_xilinx = @($devices | Where-Object { $_.PNPDeviceID -like 'PCI\VEN_10EE*' } | Select-Object Name, PNPDeviceID, Status, ConfigManagerErrorCode, Service, Manufacturer, HardwareID, ClassGuid)
    $result.usb_jtag_candidates = @($devices | Where-Object { $_.PNPDeviceID -like 'USB\*' -and ($_.PNPDeviceID -match 'VID_(03FD|0403|1443)' -or $_.Name -match 'Xilinx|Digilent|JTAG|Platform Cable|FTDI') } | Select-Object Name, PNPDeviceID, Status, ConfigManagerErrorCode, Service, Manufacturer, HardwareID, ClassGuid)
    $result.named_fpga_devices = @($devices | Where-Object { $_.Name -match 'Xilinx|Digilent|JTAG|XDMA|FPGA|DMA/Bridge' } | Select-Object Name, PNPDeviceID, Status, ConfigManagerErrorCode, Service, Manufacturer, HardwareID, ClassGuid)
} catch { $result.errors += 'PnP CIM: ' + $_.Exception.Message }
try {
    $result.present_pcie_xilinx = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'PCI\VEN_10EE*' } | Select-Object Status, Class, FriendlyName, InstanceId, Problem, ConfigManagerErrorCode)
    $result.present_usb_jtag_candidates = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\*' -and ($_.InstanceId -match 'VID_(03FD|0403|1443)' -or $_.FriendlyName -match 'Xilinx|Digilent|JTAG|Platform Cable|FTDI') } | Select-Object Status, Class, FriendlyName, InstanceId, Problem)
} catch { $result.errors += 'PnP present: ' + $_.Exception.Message }
$result | ConvertTo-Json -Depth 8 -Compress
