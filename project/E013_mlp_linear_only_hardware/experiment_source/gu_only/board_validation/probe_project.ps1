$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$result = [ordered]@{ schema = 1; utc = [DateTime]::UtcNow.ToString('o'); probe = 'project'; errors = @(); listings = @(); selected_project_files = @() }
$roots = @('D:\project', (Join-Path $env:USERPROFILE 'Desktop\zwj'), (Join-Path $env:USERPROFILE 'Documents\Python Scripts'))
foreach ($root in ($roots | Select-Object -Unique)) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
    try {
        $children = @(Get-ChildItem -LiteralPath $root -ErrorAction Stop | Select-Object -First 200)
        $result.listings += [ordered]@{ root = $root; children = @($children | Select-Object Name, FullName, PSIsContainer, Length) }
        foreach ($child in $children) {
            if ($child.PSIsContainer -and $child.Name -match 'Xilinx|Vivado|VCU|FPGA|PCI|XDMA|ScaleLLM|DMA|JTAG|test|hap') {
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
$known = Join-Path $env:USERPROFILE 'Desktop\hap_check_pcie_link.ps1'
if (Test-Path -LiteralPath $known -PathType Leaf) {
    $result.known_script = [ordered]@{ path=$known; sha256=(Get-FileHash -LiteralPath $known -Algorithm SHA256).Hash; content=(Get-Content -LiteralPath $known -Raw) }
}
$result | ConvertTo-Json -Depth 8 -Compress
