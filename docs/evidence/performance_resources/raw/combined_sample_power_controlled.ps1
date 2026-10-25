# Measurement copy: original source SHA dffb1bde825a2d65dcdce3c3c852a9626ecb0eb6e677cb4fd7e6d4a27eb891d9.
# Only adds UTC/Stopwatch timestamp fields; PMBus command list/conversion/gates unchanged.
param(
    [string[]]$RailAddress = @("0x70", "0x11", "0x12", "0x15", "0x14", "0x72", "0x73"),
    [ValidateRange(1, 3600)]
    [int]$SampleCount = 1,
    [ValidateRange(100, 60000)]
    [int]$IntervalMs = 1000,
    [string]$StopFile = "",
    [string]$ReadyPath = "",
    [string]$Label = "manual",
    [string]$RuntimeRoot = "C:\Users\dell\Documents\MaximPowerToolReadonly\runtime_stable",
    [string]$EvidencePath = "C:\Users\dell\Documents\MaximPowerToolReadonly\evidence\vcu118_pmbus_telemetry.json"
)

$ErrorActionPreference = "Stop"

$expectedExecutableSha256 = "CA0CEBC63364312C56C3949655B40352758177B243B56EADC1C7BFFF30F08E68"
$expectedAdapterSerial = "MXA4UQLZ"
$executable = Join-Path $RuntimeRoot "MaximDigitalPower.exe"
$binding = [Reflection.BindingFlags]"Public,NonPublic,Instance,Static"

# These are the seven VCU118 FPGA rails listed in UG1224 Table 3-34.  The
# addresses are direct regulator PMBus addresses on J39, not INA226 addresses.
$railTable = @{
    "0x70" = [ordered]@{ name = "VCCINT_FPGA"; regulator = "MAX20751"; xml = "MAX20751.xml"; nominal_v = 0.85; power_source = "READ_POUT" }
    "0x11" = [ordered]@{ name = "VCC1V8_FPGA"; regulator = "MAX15301"; xml = "004328.xml"; nominal_v = 1.80; power_source = "VOUT_X_IOUT" }
    "0x12" = [ordered]@{ name = "VADJ_1V8_FPGA"; regulator = "MAX15301"; xml = "004328.xml"; nominal_v = 1.80; power_source = "VOUT_X_IOUT" }
    "0x15" = [ordered]@{ name = "VCCINTIO_BRAM_FPGA"; regulator = "MAX15301"; xml = "004328.xml"; nominal_v = 0.85; power_source = "VOUT_X_IOUT" }
    "0x14" = [ordered]@{ name = "VCC1V2_FPGA"; regulator = "MAX15301"; xml = "004328.xml"; nominal_v = 1.20; power_source = "VOUT_X_IOUT" }
    "0x72" = [ordered]@{ name = "MGTAVCC_FPGA"; regulator = "MAX20751"; xml = "MAX20751.xml"; nominal_v = 0.90; power_source = "READ_POUT" }
    "0x73" = [ordered]@{ name = "MGTAVTT_FPGA"; regulator = "MAX20751"; xml = "MAX20751.xml"; nominal_v = 1.20; power_source = "READ_POUT" }
}

$allowedCommands = @{
    "VOUT_MODE" = 0x20
    "READ_VOUT" = 0x8B
    "READ_IOUT" = 0x8C
    "READ_POUT" = 0x96
}

function Convert-Address {
    param([Parameter(Mandatory = $true)][string]$Text)

    $normalized = $Text.Trim().ToLowerInvariant()
    if (-not $railTable.ContainsKey($normalized)) {
        throw "Address $Text is not in the fixed VCU118 telemetry allowlist."
    }
    return [byte][Convert]::ToUInt32($normalized.Substring(2), 16)
}

function Assert-ReadOnlyCommand {
    param(
        [Parameter(Mandatory = $true)][System.Xml.XmlNode]$PmbusNode,
        [Parameter(Mandatory = $true)][string]$Name
    )

    if (-not $allowedCommands.ContainsKey($Name)) {
        throw "PMBus command $Name is outside the telemetry command allowlist."
    }
    $node = $PmbusNode.SelectSingleNode("Memory/$Name")
    if ($null -eq $node) {
        throw "Missing $Name in the regulator XML."
    }
    $command = [int]$node.GetAttribute("command")
    if ($command -ne $allowedCommands[$Name]) {
        throw ("Unexpected command for {0}: XML=0x{1:X2}, allowlist=0x{2:X2}" -f $Name, $command, $allowedCommands[$Name])
    }
    if ($node.GetAttribute("readOnly").ToLowerInvariant() -ne "true") {
        throw "$Name is not marked readOnly=true in the regulator XML."
    }
}

function Convert-Linear11 {
    param([Parameter(Mandatory = $true)][uint16]$Word)

    $exponent = [int](($Word -shr 11) -band 0x1F)
    if ($exponent -band 0x10) { $exponent -= 0x20 }
    $mantissa = [int]($Word -band 0x07FF)
    if ($mantissa -band 0x0400) { $mantissa -= 0x0800 }
    return [double]$mantissa * [Math]::Pow(2.0, $exponent)
}

function Get-Linear11Resolution {
    param([Parameter(Mandatory = $true)][uint16]$Word)

    $exponent = [int](($Word -shr 11) -band 0x1F)
    if ($exponent -band 0x10) { $exponent -= 0x20 }
    return [Math]::Pow(2.0, $exponent)
}

function Convert-RawWord {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)

    if ($Bytes.Length -ne 2) {
        throw "Expected a two-byte PMBus word, got $($Bytes.Length) bytes."
    }
    # PMBus word data is transferred least-significant byte first.
    return [uint16](([uint16]$Bytes[1] -shl 8) -bor [uint16]$Bytes[0])
}

function Format-RawBytes {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)
    return (($Bytes | ForEach-Object { "{0:X2}" -f $_ }) -join " ")
}

function Test-FiniteNumber {
    param([Parameter(Mandatory = $true)][double]$Value)
    return (-not [double]::IsNaN($Value) -and -not [double]::IsInfinity($Value))
}

if ([Environment]::Is64BitProcess) {
    throw "Run this script with 32-bit Windows PowerShell (SysWOW64)."
}
if (@(Get-Process -Name MaximDigitalPower -ErrorAction SilentlyContinue).Count -ne 0) {
    throw "MaximDigitalPower is running; refusing concurrent PMBus access."
}
if (-not (Test-Path -LiteralPath $executable)) {
    throw "Missing stable PowerTool runtime: $executable"
}
if ((Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash -ne $expectedExecutableSha256) {
    throw "Stable PowerTool executable SHA256 mismatch."
}

$requestedRails = @()
foreach ($text in $RailAddress) {
    $address = Convert-Address $text
    $key = "0x{0:X2}" -f $address
    if ($requestedRails.address_key -contains $key) {
        throw "Duplicate rail address: $key"
    }
    $requestedRails += [pscustomobject]@{ address = $address; address_key = $key; metadata = $railTable[$key] }
}

$evidenceDir = Split-Path -Parent $EvidencePath
if (-not (Test-Path -LiteralPath $evidenceDir)) {
    New-Item -ItemType Directory -Path $evidenceDir -Force | Out-Null
}

$packetizer = $null
$disconnect = $null
$result = [ordered]@{
    schema_version = "hap_vcu118_direct_pmbus_telemetry_v2_timed"
    stopwatch_frequency = [Diagnostics.Stopwatch]::Frequency
    process_started_utc = [DateTime]::UtcNow.ToString("o")
    process_started_ticks = [Diagnostics.Stopwatch]::GetTimestamp()
    timestamp = (Get-Date).ToString("o")
    label = $Label
    process_bitness = 32
    measurement_scope = "seven UG1224 FPGA regulator rails via J39; not whole-board 12 V input power"
    executable = $executable
    executable_sha256 = $expectedExecutableSha256
    adapter_serial = $null
    read_contract = [ordered]@{
        fixed_addresses_only = $true
        address_scan = $false
        writes = $false
        clear_faults = $false
        allowed_commands = @($allowedCommands.Keys | Sort-Object)
    }
    samples = @()
    pass = $false
}

try {
    Set-Location $RuntimeRoot
    $assembly = [Reflection.Assembly]::LoadFrom($executable)
    $packetizerType = $assembly.GetType("MaximGUI.DonglePacketizer", $true)
    $memoryType = $assembly.GetType("MaximGUI.MemoryDescriptor", $true)
    $getPacketizer = $packetizerType.GetMethod("getI2CPacketizer", $binding)
    $getDeviceList = $packetizerType.GetMethod("getDeviceList", $binding)
    $initComm = $packetizerType.GetMethod("initComm", $binding)
    $checkConnection = $packetizerType.GetMethod("checkConnection", $binding)
    $disconnect = $packetizerType.GetMethod("disconnect", $binding)
    $packetizer = $getPacketizer.Invoke($null, @())

    $deviceList = @($getDeviceList.Invoke($packetizer, @()))
    if ($deviceList.Count -ne 1 -or $deviceList[0] -ne $expectedAdapterSerial) {
        throw "Unexpected adapter list: $($deviceList -join ',')"
    }
    $result.adapter_serial = $deviceList[0]
    $initComm.Invoke($packetizer, @($expectedAdapterSerial))
    if (-not $checkConnection.Invoke($packetizer, @())) {
        throw "Adapter connection check failed."
    }

    $railReaders = @()
    foreach ($rail in $requestedRails) {
        $xmlPath = Join-Path $RuntimeRoot $rail.metadata.xml
        if (-not (Test-Path -LiteralPath $xmlPath)) {
            throw "Missing regulator XML: $xmlPath"
        }
        $document = New-Object System.Xml.XmlDocument
        $document.Load($xmlPath)
        $pmbusNode = $document.DocumentElement.SelectSingleNode("PMBusCommands")
        if ($null -eq $pmbusNode) {
            throw "Missing PMBusCommands in $xmlPath"
        }

        Assert-ReadOnlyCommand $pmbusNode "VOUT_MODE"
        Assert-ReadOnlyCommand $pmbusNode "READ_VOUT"
        Assert-ReadOnlyCommand $pmbusNode "READ_IOUT"
        if ($rail.metadata.power_source -eq "READ_POUT") {
            Assert-ReadOnlyCommand $pmbusNode "READ_POUT"
        }

        $memory = [Activator]::CreateInstance($memoryType, @($true))
        $memory.loadXML($pmbusNode, $rail.address)
        $railReaders += [pscustomobject]@{ rail = $rail; memory = $memory }
    }

    for ($sampleIndex = 0; $sampleIndex -lt $SampleCount; $sampleIndex++) {
        $sample = [ordered]@{
            index = $sampleIndex
            sweep_started_utc = [DateTime]::UtcNow.ToString("o")
            sweep_started_ticks = [Diagnostics.Stopwatch]::GetTimestamp()
            timestamp = (Get-Date).ToString("o")
            rails = @()
            monitored_power_w = 0.0
            monitored_power_quantization_half_step_bound_w = 0.0
        }
        # Publish the in-progress sample before rail gates so a failure still
        # leaves the raw bytes that caused it in the evidence JSON.
        $result.samples += $sample

        foreach ($reader in $railReaders) {
            $railReadStartedUtc = [DateTime]::UtcNow.ToString("o")
            $railReadStartedTicks = [Diagnostics.Stopwatch]::GetTimestamp()
            $rail = $reader.rail
            $memory = $reader.memory

            # VOUT_MODE is read first because VLinear READ_VOUT conversion uses it.
            $voutModeParsed = [double]$memory.getValueAsDouble("VOUT_MODE", $true)
            $voutParsed = [double]$memory.getValueAsDouble("READ_VOUT", $true)
            $ioutParsed = [double]$memory.getValueAsDouble("READ_IOUT", $true)
            $voutRaw = [byte[]]$memory.getByte([uint32]$allowedCommands.READ_VOUT, $false)
            $ioutRaw = [byte[]]$memory.getByte([uint32]$allowedCommands.READ_IOUT, $false)

            $powerResolution = $null
            $currentResolution = $null
            $coarseVoltage = $null
            $measurementState = "active"
            $gateNotes = @()

            if ($rail.metadata.regulator -eq "MAX20751") {
                # MAX20751 READ_VOUT reports its feedback-node voltage and the
                # PowerTool GUI applies a board-specific divider ratio.  The
                # regulator's READ_IOUT and READ_POUT values are already physical
                # Linear11 quantities, so use P/I as the measured rail voltage.
                $feedbackVoltage = [double](Convert-RawWord $voutRaw) / 512.0
                $poutParsed = [double]$memory.getValueAsDouble("READ_POUT", $true)
                $poutRaw = [byte[]]$memory.getByte([uint32]$allowedCommands.READ_POUT, $false)
                $poutWord = Convert-RawWord $poutRaw
                $ioutWord = Convert-RawWord $ioutRaw
                $power = Convert-Linear11 $poutWord
                $powerResolution = Get-Linear11Resolution $poutWord
                $currentResolution = Get-Linear11Resolution $ioutWord
                if ([Math]::Abs($power - $poutParsed) -gt 0.01) {
                    throw "$($rail.address_key) READ_POUT parser mismatch: manual=$power parsed=$poutParsed"
                }
                $current = $ioutParsed
                if ([Math]::Abs($current) -gt ($currentResolution / 2.0) -and [Math]::Abs($power) -ge ($powerResolution / 2.0)) {
                    $coarseVoltage = $power / $current
                }
                $voltage = $null
                $dividerRatio = $null
                if ($null -ne $coarseVoltage -and [Math]::Abs($coarseVoltage) -gt 1.0e-12) {
                    $dividerRatio = $feedbackVoltage / $coarseVoltage
                }
                $powerRawText = Format-RawBytes $poutRaw
                $voltageSource = "UNAVAILABLE_DIRECT_FEEDBACK_ONLY"
                if ([Math]::Abs($power) -lt ($powerResolution / 2.0)) {
                    if ([Math]::Abs($current) -ge ($currentResolution / 2.0)) {
                        $measurementState = "active_below_power_resolution"
                    }
                    else {
                        $measurementState = "below_current_and_power_resolution"
                    }
                }
                else {
                    $measurementState = "active_quantized"
                }
                $gateNotes += ("READ_POUT Linear11 step is {0:F6} W; reported power has an approximate +/-{1:F6} W half-step quantization bound." -f $powerResolution, ($powerResolution / 2.0))
                $gateNotes += "READ_VOUT is the regulator feedback-node value; no unverified board divider is applied."
            }
            else {
                $feedbackVoltage = $null
                $dividerRatio = $null
                $voltage = $voutParsed
                $current = $ioutParsed
                $power = $voltage * $current
                $powerRawText = $null
                $voltageSource = "READ_VOUT"
                if ([Math]::Abs($current) -le 0.05 -and [Math]::Abs($power) -le 0.05 -and $voltage -lt ([double]$rail.metadata.nominal_v * 0.50)) {
                    $measurementState = "disabled"
                    $gateNotes += "Rail is treated as disabled because voltage, current, and power are all below the active-rail thresholds."
                }
            }

            $railResult = [ordered]@{
                read_started_utc = $railReadStartedUtc
                read_started_ticks = $railReadStartedTicks
                read_finished_utc = [DateTime]::UtcNow.ToString("o")
                read_finished_ticks = [Diagnostics.Stopwatch]::GetTimestamp()
                address = $rail.address_key
                name = $rail.metadata.name
                regulator = $rail.metadata.regulator
                nominal_voltage_v = $rail.metadata.nominal_v
                voltage_v = $voltage
                current_a = $current
                power_w = $power
                power_source = $rail.metadata.power_source
                voltage_source = $voltageSource
                measurement_state = $measurementState
                quantization = [ordered]@{
                    power_step_w = $powerResolution
                    power_half_step_bound_w = if ($null -eq $powerResolution) { $null } else { $powerResolution / 2.0 }
                    current_step_a = $currentResolution
                }
                raw = [ordered]@{
                    vout_mode = $voutModeParsed
                    read_vout = Format-RawBytes $voutRaw
                    read_iout = Format-RawBytes $ioutRaw
                    read_pout = $powerRawText
                }
                parser = [ordered]@{
                    read_vout = $voutParsed
                    read_iout = $ioutParsed
                    feedback_voltage_v = $feedbackVoltage
                    coarse_read_pout_div_read_iout_voltage_v = $coarseVoltage
                    inferred_feedback_divider_ratio = $dividerRatio
                }
                gate_notes = $gateNotes
                gate_pass = $false
            }
            $sample.rails += $railResult

            if ($rail.metadata.regulator -eq "MAX15301" -and $measurementState -ne "disabled") {
                $minVoltage = [double]$rail.metadata.nominal_v * 0.85
                $maxVoltage = [double]$rail.metadata.nominal_v * 1.15
                if (-not (Test-FiniteNumber $voltage) -or $voltage -lt $minVoltage -or $voltage -gt $maxVoltage) {
                    throw ("{0} voltage gate failed: {1:F6} V, expected {2:F3}..{3:F3} V" -f $rail.address_key, $voltage, $minVoltage, $maxVoltage)
                }
            }
            if ($rail.metadata.regulator -eq "MAX20751" -and (-not (Test-FiniteNumber $feedbackVoltage) -or $feedbackVoltage -lt 0.0 -or $feedbackVoltage -gt 1.0)) {
                throw "$($rail.address_key) feedback-node voltage gate failed: $feedbackVoltage V"
            }
            if (-not (Test-FiniteNumber $current) -or $current -lt -0.25 -or $current -gt 100.0) {
                throw "$($rail.address_key) current gate failed: $current A"
            }
            if (-not (Test-FiniteNumber $power) -or $power -lt -0.25 -or $power -gt 100.0) {
                throw "$($rail.address_key) power gate failed: $power W"
            }
            $railResult.gate_pass = $true
            $sample.monitored_power_w += $power
            if ($null -ne $powerResolution) {
                $sample.monitored_power_quantization_half_step_bound_w += $powerResolution / 2.0
            }
        }

        $sample["sweep_ended_utc"] = [DateTime]::UtcNow.ToString("o")
        $sample["sweep_ended_ticks"] = [Diagnostics.Stopwatch]::GetTimestamp()
        # Recorder lifetime only: all rail reads/conversions above are unchanged.
        if ($sampleIndex -eq 0 -and $ReadyPath) {
            [IO.File]::WriteAllText($ReadyPath, (([ordered]@{utc=[DateTime]::UtcNow.ToString("o");ticks=[Diagnostics.Stopwatch]::GetTimestamp();complete_sweeps=1}) | ConvertTo-Json), (New-Object Text.UTF8Encoding($false)))
        }
        if ($StopFile -and (Test-Path -LiteralPath $StopFile)) { break }
        if ($sampleIndex + 1 -lt $SampleCount) {
            Start-Sleep -Milliseconds $IntervalMs
        }
    }

    $powerSamples = @($result.samples | ForEach-Object { [double]$_.monitored_power_w })
    $result.summary = [ordered]@{
        sample_count = $powerSamples.Count
        first_sample_timestamp = $result.samples[0].timestamp
        last_sample_timestamp = $result.samples[-1].timestamp
        elapsed_s = ((Get-Date) - [datetime]$result.timestamp).TotalSeconds
        monitored_power_mean_w = [double](($powerSamples | Measure-Object -Average).Average)
        monitored_power_min_w = [double](($powerSamples | Measure-Object -Minimum).Minimum)
        monitored_power_max_w = [double](($powerSamples | Measure-Object -Maximum).Maximum)
        quantization_half_step_bound_w = [double](($result.samples | ForEach-Object { $_.monitored_power_quantization_half_step_bound_w } | Measure-Object -Maximum).Maximum)
        scope_note = "Sum of seven direct J39 regulator telemetry values; this is not whole-board 12 V input power."
    }
    $result.pass = $true
}
finally {
    if ($null -ne $packetizer -and $null -ne $disconnect) {
        try { $disconnect.Invoke($packetizer, @()) } catch {}
    }
    $result | ConvertTo-Json -Depth 9 | Set-Content -LiteralPath $EvidencePath -Encoding UTF8
}

$result | ConvertTo-Json -Depth 9
