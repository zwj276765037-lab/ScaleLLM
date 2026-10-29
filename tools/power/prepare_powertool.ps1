# Prepare a separate read-only telemetry runtime from a user-owned vendor install.
# This script does not connect to USB/PMBus or launch the vendor GUI.
param(
    [Parameter(Mandatory=$true)][string]$SourceRoot,
    [Parameter(Mandatory=$true)][string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
if ([Environment]::Is64BitProcess) { throw 'Use 32-bit Windows PowerShell (SysWOW64).' }
$source = (Resolve-Path -LiteralPath $SourceRoot).Path
$output = [IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $output) { throw 'OutputRoot must be a new directory.' }
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'powertool_runtime_manifest.json') -Raw | ConvertFrom-Json
$executable = Join-Path $source 'MaximDigitalPower.exe'
if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.official_executable_sha256) {
    throw 'Vendor executable differs from the observed official 2.32.27 input. No files were changed.'
}
# Verify only the explicit DLL closure. Never copy an entire user directory.
foreach ($entry in $manifest.files.PSObject.Properties) {
    if (-not $entry.Name.EndsWith('.dll')) { continue }
    $path = Join-Path $source $entry.Name
    if ((Get-Item -LiteralPath $path).Length -ne $entry.Value.bytes -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.sha256) {
        throw ('Vendor DLL identity differs: ' + $entry.Name)
    }
}
New-Item -ItemType Directory -Path $output -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath $executable -Destination (Join-Path $output 'MaximDigitalPower.exe')
foreach ($entry in $manifest.files.PSObject.Properties) {
    if ($entry.Name.EndsWith('.dll')) {
        Copy-Item -LiteralPath (Join-Path $source $entry.Name) -Destination (Join-Path $output $entry.Name)
    }
}
# Read embedded strings directly; do not initialize MainWindow or device scans.
$assembly = [Reflection.Assembly]::ReflectionOnlyLoadFrom($executable)
$stream = $assembly.GetManifestResourceStream('MaximDigitalPower.Properties.Resources.resources')
if ($null -eq $stream) { throw 'Expected embedded vendor resources are missing.' }
$reader = New-Object System.Resources.ResourceReader($stream)
$resources = @{}
try {
    $enumerator = $reader.GetEnumerator()
    while ($enumerator.MoveNext()) {
        $name = [string]$enumerator.Key
        if ($name -eq '004328' -or $name -eq 'MAX20751') { $resources[$name] = [string]$enumerator.Value }
    }
} finally { $reader.Close(); $stream.Dispose() }
$enc = New-Object Text.UTF8Encoding($false)
$extracted = @()
foreach ($name in @('004328', 'MAX20751')) {
    if (-not $resources.ContainsKey($name)) { throw ('Embedded XML missing: ' + $name) }
    $expected = $manifest.files.($name + '.xml')
    $original = [string]$resources[$name]
    $lf = $original.Replace("`r`n", "`n")
    $candidates = @($original, $lf, $lf.Replace("`n", "`r`n"))
    $matched = $false
    foreach ($text in $candidates) {
        foreach ($withBom in @($false, $true)) {
            [byte[]]$bytes = $enc.GetBytes($text)
            if ($withBom) { $bytes = [byte[]](@(0xEF,0xBB,0xBF) + $bytes) }
            $hasher = [Security.Cryptography.SHA256]::Create()
            try { $digest = ([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
            finally { $hasher.Dispose() }
            if ($digest -eq $expected.sha256 -and $bytes.Length -eq $expected.bytes) {
                [IO.File]::WriteAllBytes((Join-Path $output ($name + '.xml')), $bytes)
                $extracted += @{ name=($name + '.xml'); sha256=$digest; bytes=$bytes.Length }
                $matched = $true
                break
            }
        }
        if ($matched) { break }
    }
    if (-not $matched) { throw ('Embedded XML does not reproduce the measured identity: ' + $name) }
}
$result = [ordered]@{status='PREPARED';gui_started=$false;device_opened=$false;
    executable_sha256=$manifest.official_executable_sha256;xml=$extracted;
    note='Official executable, explicit original DLLs and hash-identical embedded XML. No hardware test is implied.'}
[IO.File]::WriteAllText((Join-Path $output 'preparation.json'), ($result | ConvertTo-Json -Depth 8), $enc)
$result | ConvertTo-Json -Depth 8
