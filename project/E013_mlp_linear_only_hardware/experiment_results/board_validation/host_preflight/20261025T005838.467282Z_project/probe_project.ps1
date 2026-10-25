$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$result = [ordered]@{ schema = 1; utc = [DateTime]::UtcNow.ToString('o'); probe = 'project'; errors = @(); listings = @(); selected_project_files = @() }
$roots = @((Join-Path $env:USERPROFILE 'Desktop'), (Join-Path $env:USERPROFILE 'Documents'), (Join-Path $env:USERPROFILE 'Downloads'), (Join-Path $env:USERPROFILE 'source\repos'), 'C:\FPGA', 'D:\FPGA', 'C:\work', 'D:\work', 'C:\projects', 'D:\projects', 'D:\')
foreach ($root in ($roots | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    try {
        $children = @(Get-ChildItem -LiteralPath $root -ErrorAction Stop)
        $result.listings += [ordered]@{ root = $root; children = @($children | Select-Object Name, FullName, PSIsContainer, Length) }
        foreach ($child in $children) {
            if ($child.PSIsContainer -and $child.Name -match 'Xilinx|Vivado|VCU|FPGA|PCI|XDMA|ScaleLLM|DMA|JTAG') {
                $inner = @(Get-ChildItem -LiteralPath $child.FullName -ErrorAction SilentlyContinue)
                $result.listings += [ordered]@{ root = $child.FullName; children = @($inner | Select-Object Name, FullName, PSIsContainer, Length) }
                foreach ($leaf in $inner) {
                    if (-not $leaf.PSIsContainer -and $leaf.Name -match '\.(exe|bat|ps1|inf|sln|vcxproj|py|tcl|md|txt)$') {
                        $result.selected_project_files += [ordered]@{ path = $leaf.FullName; length = $leaf.Length; sha256 = (Get-FileHash -LiteralPath $leaf.FullName -Algorithm SHA256).Hash }
                    }
                }
            }
        }
    } catch { $result.errors += $root + ': ' + $_.Exception.Message }
}
$result | ConvertTo-Json -Depth 8 -Compress
