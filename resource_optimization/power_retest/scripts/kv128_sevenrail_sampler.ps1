# Read-only, seven-rail PMBus capture. Run with 32-bit Windows PowerShell on the
# Dell host under a board-owning launcher. No regulator configuration is changed.
param(
    [Parameter(Mandatory=$true)][string]$RuntimeRoot,
    [Parameter(Mandatory=$true)][string]$ExpectedAdapterSerial,
    [Parameter(Mandatory=$true)][string]$EvidencePath,
    [Parameter(Mandatory=$true)][string]$JsonlPath,
    [ValidateRange(0,400000)][int]$MaxSweeps = 400000,
    [ValidateRange(0,14400)][int]$MaxSeconds = 600,
    [ValidateRange(0,60000)][int]$IntervalMs = 0,
    [ValidateRange(0,60000)][int]$TargetPeriodMs = 0,
    [string]$PhasePath = '',
    [string]$ReadyPath = '',
    [string]$StopFile = ''
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
if ([Environment]::Is64BitProcess) { throw 'PowerTool requires 32-bit Windows PowerShell' }
foreach ($path in @($EvidencePath,$JsonlPath)) {
    if (-not [IO.Path]::IsPathRooted($path) -or [IO.File]::Exists($path)) {
        throw ('Evidence path must be absolute and new: '+$path)
    }
}
if ($ReadyPath -and (-not [IO.Path]::IsPathRooted($ReadyPath) -or [IO.File]::Exists($ReadyPath))) {
    throw 'Ready path must be absolute and new'
}
if ($StopFile -and -not [IO.Path]::IsPathRooted($StopFile)) { throw 'Stop path must be absolute' }
if ($PhasePath -and -not [IO.Path]::IsPathRooted($PhasePath)) { throw 'Phase path must be absolute' }
if ($TargetPeriodMs -and $IntervalMs) { throw 'Choose either sweep start period or after-sweep interval' }
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SevenRailQpc {
    [DllImport("kernel32.dll")] public static extern bool QueryPerformanceCounter(out long value);
    [DllImport("kernel32.dll")] public static extern bool QueryPerformanceFrequency(out long value);
}
'@
$frequency=[long]0; $nativeBefore=[long]0; $nativeAfter=[long]0
if (-not [SevenRailQpc]::QueryPerformanceFrequency([ref]$frequency) -or
    -not [SevenRailQpc]::QueryPerformanceCounter([ref]$nativeBefore)) { throw 'Native QPC unavailable' }
$between=[Diagnostics.Stopwatch]::GetTimestamp()
if (-not [SevenRailQpc]::QueryPerformanceCounter([ref]$nativeAfter) -or
    -not [Diagnostics.Stopwatch]::IsHighResolution -or
    [Diagnostics.Stopwatch]::Frequency -ne $frequency -or
    $between -lt ($nativeBefore-2) -or $between -gt ($nativeAfter+2)) {
    throw 'Cross-process QPC tick domain differs'
}
if (@(Get-Process -Name MaximDigitalPower -ErrorAction SilentlyContinue).Count) {
    throw 'PowerTool GUI owns the adapter'
}
$officialSha='d5749e5ebb80b4ad7c81c73cc9863467bb988915922a9337da75bb304fc23f31'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'powertool_runtime_manifest.json') -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'scalellm_powertool_external_runtime_v1') { throw 'Runtime manifest schema differs' }
foreach ($entry in $manifest.files.PSObject.Properties) {
    $file=Join-Path $RuntimeRoot $entry.Name
    if ((Get-Item -LiteralPath $file).Length -ne $entry.Value.bytes -or
        (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value.sha256) {
        throw ('Official runtime identity differs: '+$entry.Name)
    }
}
$exe=Join-Path $RuntimeRoot 'MaximDigitalPower.exe'
if ((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant() -ne $officialSha) {
    throw 'Official executable identity differs'
}
$rails=@(
    @{address='0x70';name='VCCINT_FPGA';regulator='MAX20751';xml='MAX20751.xml'},
    @{address='0x11';name='VCC1V8_FPGA';regulator='MAX15301';xml='004328.xml'},
    @{address='0x12';name='VADJ_1V8_FPGA';regulator='MAX15301';xml='004328.xml'},
    @{address='0x15';name='VCCINTIO_BRAM_FPGA';regulator='MAX15301';xml='004328.xml'},
    @{address='0x14';name='VCC1V2_FPGA';regulator='MAX15301';xml='004328.xml'},
    @{address='0x72';name='MGTAVCC_FPGA';regulator='MAX20751';xml='MAX20751.xml'},
    @{address='0x73';name='MGTAVTT_FPGA';regulator='MAX20751';xml='MAX20751.xml'}
)
$codes=@{VOUT_MODE=0x20;READ_VOUT=0x8B;READ_IOUT=0x8C;READ_POUT=0x96;
    IOUT_CAL_GAIN=0x38;IOUT_CAL_OFFSET=0x39}
function Raw-Hex([byte[]]$Bytes) { return (($Bytes | ForEach-Object {'{0:X2}' -f $_}) -join ' ') }
function Linear11([int]$Word) {
    $e=($Word -shr 11) -band 31; if ($e -band 16) { $e-=32 }
    $m=$Word -band 2047; if ($m -band 1024) { $m-=2048 }
    return [ordered]@{exponent=$e;mantissa=$m;value=[double]$m*[Math]::Pow(2.0,$e)}
}
function Append-Record($Record) {
    $line=($Record | ConvertTo-Json -Depth 9 -Compress)+[Environment]::NewLine
    [IO.File]::AppendAllText($JsonlPath,$line,(New-Object Text.UTF8Encoding($false)))
}
function Read-Fresh($Memory,[string]$Command) {
    if (-not $codes.ContainsKey($Command)) { throw ('Command outside allowlist: '+$Command) }
    $before=[Diagnostics.Stopwatch]::GetTimestamp()
    $raw=$null; $errorText=$null
    try { $raw=[byte[]]$Memory.getByte([uint32]$codes[$Command],$true) }
    catch { $errorText=$_.Exception.Message }
    $after=[Diagnostics.Stopwatch]::GetTimestamp()
    $expected=if($Command -eq 'VOUT_MODE'){1}else{2}
    if ($null -ne $raw -and $raw.Length -ne $expected) {
        $errorText=('Expected '+$expected+' bytes, got '+$raw.Length)
    }
    $word=$null; $hex=$null
    if ($null -ne $raw) {
        $hex=Raw-Hex $raw
        if ($raw.Length -eq $expected) {
            $word=[int]$raw[0]
            if ($expected -eq 2) { $word=$word -bor ([int]$raw[1] -shl 8) }
        }
    }
    $script:readId++
    $record=[ordered]@{record='bus_read';read_id=$script:readId;
        run_id=$env:SCALELLM_RUN_ID;block_id=$script:currentBlockId;repeat_id=$script:currentRepeatId;
        phase=$script:currentPhase;sweep=$script:currentSweep;position=$script:currentPosition;
        address=$script:currentAddress;name=$script:currentName;regulator=$script:currentRegulator;
        qpc_frequency=$frequency;utc_after=[DateTime]::UtcNow.ToString('o');
        command=$Command;command_code=$codes[$Command];
        before_ticks=$before;after_ticks=$after;raw_hex=$hex;word_le=$word;
        byte_count=$(if($null -ne $raw){$raw.Length}else{$null});
        expected_bytes=$expected;api_status=$(if($null -eq $errorText){'returned'}else{'error'});
        native_ack_status='NOT_EXPOSED_BY_OFFICIAL_API';
        error=$errorText;fresh_hardware_read=$true}
    Append-Record $record
    return $record
}
function Assert-XmlReadOnly($Node,[string]$Command) {
    $entry=$Node.SelectSingleNode('Memory/'+$Command)
    if ($null -eq $entry -or [int]$entry.GetAttribute('command') -ne $codes[$Command] -or
        $entry.GetAttribute('readOnly').ToLowerInvariant() -ne 'true') {
        throw ('XML read-only command gate failed: '+$Command)
    }
}
$result=[ordered]@{schema='scalellm_kv128_sevenrail_pmbus_v1';status='RUNNING';
    started_utc=[DateTime]::UtcNow.ToString('o');host=[Environment]::MachineName;
    boot_utc=$env:SCALELLM_BOOT_UTC;run_id=$env:SCALELLM_RUN_ID;
    qpc_frequency=$frequency;qpc_validation=@{native_before_ticks=$nativeBefore;
        stopwatch_ticks=$between;native_after_ticks=$nativeAfter;margin_ticks=2};
    started_ticks=[Diagnostics.Stopwatch]::GetTimestamp();
    official_executable_sha256=$officialSha;
    adapter_serial_sha256=([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($ExpectedAdapterSerial)))).Replace('-','').ToLowerInvariant();
    adapter_serial_recorded=$false;read_only=$true;writes=$false;address_scan=$false;
    sensor_aperture_and_lag='UNKNOWN';rail_addresses=@($rails|ForEach-Object{$_.address});
    max_sweeps=$MaxSweeps;max_seconds=$MaxSeconds;interval_ms=$IntervalMs;
    target_period_ms=$TargetPeriodMs;phase_path=$PhasePath;missed_deadlines=0;
    configuration=@();complete_sweeps=0;complete_rail_points=0;read_errors=0;
    error=$null;pass=$false}
$packetizer=$null; $disconnect=$null
$script:readId=0;$script:currentBlockId=$null;$script:currentRepeatId=$null
$script:currentPhase='configuration';$script:currentSweep=-1;$script:currentPosition=-1
$script:currentAddress=$null;$script:currentName=$null;$script:currentRegulator=$null
$stream=[IO.File]::Open($JsonlPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$stream.Dispose()
try {
    Set-Location -LiteralPath $RuntimeRoot
    $assembly=[Reflection.Assembly]::LoadFrom($exe)
    $type=$assembly.GetType('MaximGUI.DonglePacketizer',$true)
    $memoryType=$assembly.GetType('MaximGUI.MemoryDescriptor',$true)
    $binding=[Reflection.BindingFlags]'Public,NonPublic,Instance,Static'
    $packetizer=$type.GetMethod('getI2CPacketizer',$binding).Invoke($null,@())
    $devices=@($type.GetMethod('getDeviceList',$binding).Invoke($packetizer,@()))
    if ($devices.Count -ne 1 -or $devices[0] -ne $ExpectedAdapterSerial) { throw 'Adapter enumeration differs' }
    $type.GetMethod('initComm',$binding).Invoke($packetizer,@($ExpectedAdapterSerial))
    if (-not $type.GetMethod('checkConnection',$binding).Invoke($packetizer,@())) { throw 'Adapter connection failed' }
    $disconnect=$type.GetMethod('disconnect',$binding)
    $readers=@()
    foreach ($rail in $rails) {
        $script:currentAddress=$rail.address;$script:currentName=$rail.name
        $script:currentRegulator=$rail.regulator
        $xml=New-Object System.Xml.XmlDocument
        $xml.Load((Join-Path $RuntimeRoot $rail.xml))
        $node=$xml.DocumentElement.SelectSingleNode('PMBusCommands')
        if ($null -eq $node) { throw ('PMBusCommands absent for '+$rail.address) }
        $names=@('VOUT_MODE','READ_VOUT','READ_IOUT')
        if ($rail.regulator -eq 'MAX20751') { $names+=@('READ_POUT') }
        foreach ($name in $names) { Assert-XmlReadOnly $node $name }
        $memory=[Activator]::CreateInstance($memoryType,@($true))
        $memory.loadXML($node,[byte][Convert]::ToUInt32($rail.address.Substring(2),16))
        $mode=Read-Fresh $memory 'VOUT_MODE'
        $result.configuration+=@{address=$rail.address;name=$rail.name;regulator=$rail.regulator;read=$mode}
        Append-Record ([ordered]@{record='configuration';address=$rail.address;name=$rail.name;
            regulator=$rail.regulator;read=$mode})
        if ($mode.api_status -ne 'returned') { throw ('VOUT_MODE failed on '+$rail.address) }
        if ($rail.regulator -eq 'MAX20751' -and $mode.word_le -ne 0x20) {
            throw ('MAX20751 VID mode differs on '+$rail.address)
        }
        if ($rail.regulator -eq 'MAX15301' -and $mode.word_le -ne 0x14) {
            throw ('MAX15301 VOUT mode is not 0x14 on '+$rail.address)
        }
        $cal=@()
        foreach ($name in @('IOUT_CAL_GAIN','IOUT_CAL_OFFSET')) {
            $entry=$node.SelectSingleNode('Memory/'+$name)
            if ($null -ne $entry -and [int]$entry.GetAttribute('command') -eq $codes[$name]) {
                $cal+=,(Read-Fresh $memory $name)
            }
        }
        $result.configuration[-1]['calibration']=$cal
        $readers+=@{rail=$rail;memory=$memory;mode=[int]$mode.word_le}
    }
    $result.sampling_started_ticks=[Diagnostics.Stopwatch]::GetTimestamp()
    $result.sampling_started_utc=[DateTime]::UtcNow.ToString('o')
    $nextDue=[long]$result.sampling_started_ticks
    $periodTicks=[long]([Math]::Round($TargetPeriodMs*$frequency/1000.0))
    for ($sweep=0;($MaxSweeps -eq 0 -or $sweep -lt $MaxSweeps);$sweep++) {
        if ($StopFile -and (Test-Path -LiteralPath $StopFile)) { break }
        if ($MaxSeconds -gt 0 -and ([Diagnostics.Stopwatch]::GetTimestamp()-$result.sampling_started_ticks)/$frequency -ge $MaxSeconds) { break }
        if ($TargetPeriodMs -gt 0) {
            while ([Diagnostics.Stopwatch]::GetTimestamp() -lt $nextDue) {
                if ($StopFile -and (Test-Path -LiteralPath $StopFile)) { break }
                $remainingMs=($nextDue-[Diagnostics.Stopwatch]::GetTimestamp())*1000.0/$frequency
                if ($remainingMs -gt 2) { Start-Sleep -Milliseconds ([int][Math]::Min(10,[Math]::Floor($remainingMs))) }
            }
        }
        if ($StopFile -and (Test-Path -LiteralPath $StopFile)) { break }
        if ($MaxSeconds -gt 0 -and ([Diagnostics.Stopwatch]::GetTimestamp()-$result.sampling_started_ticks)/$frequency -ge $MaxSeconds) { break }
        $sweepStart=[Diagnostics.Stopwatch]::GetTimestamp()
        $lateTicks=[long][Math]::Max([long]0,[long]($sweepStart-$nextDue))
        if ($TargetPeriodMs -gt 0 -and $lateTicks -gt $frequency/500) { $result.missed_deadlines++ }
        $script:currentSweep=$sweep;$script:currentPhase='unassigned'
        $script:currentBlockId=$null;$script:currentRepeatId=$null
        if ($PhasePath -and (Test-Path -LiteralPath $PhasePath)) {
            $phase=Get-Content -LiteralPath $PhasePath -Raw | ConvertFrom-Json
            $script:currentPhase=[string]$phase.phase
            $script:currentBlockId=$phase.block_id
            $script:currentRepeatId=$phase.repeat_id
        }
        for ($position=0;$position -lt 7;$position++) {
            # Rotate rail order independently of observed telemetry values.
            $reader=$readers[($sweep+$position)%7]
            $rail=$reader.rail; $memory=$reader.memory
            $script:currentPosition=$position;$script:currentAddress=$rail.address
            $script:currentName=$rail.name;$script:currentRegulator=$rail.regulator
            $v=Read-Fresh $memory 'READ_VOUT'
            $i=Read-Fresh $memory 'READ_IOUT'
            $p=$null
            if ($rail.regulator -eq 'MAX20751') { $p=Read-Fresh $memory 'READ_POUT' }
            $bad=@(@($v,$i,$p) | Where-Object { $null -ne $_ -and $_.api_status -ne 'returned' })
            $voltage=$null; $current=$null; $pout=$null;$iout=$null;$decodedP=$null
            $voltageStatus='invalid_raw_or_mode';$currentStatus='invalid_raw';$poutStatus='NOT_SUPPORTED_BY_DOCUMENTED_COMMAND_SET'
            if ($v.api_status -eq 'returned') {
                if ($rail.regulator -eq 'MAX20751' -and $v.word_le -ge 1 -and $v.word_le -le 255) {
                    $voltage=0.25+($v.word_le-1)/200.0;$voltageStatus='MAX20751_VID_VR12_EQUATION28'
                } elseif ($rail.regulator -eq 'MAX15301') {
                    $exponent=$reader.mode -band 31; if ($exponent -band 16) { $exponent-=32 }
                    $voltage=[double]$v.word_le*[Math]::Pow(2.0,$exponent)
                    $voltageStatus='PMBUS_LINEAR16'
                }
            }
            if ($i.api_status -eq 'returned') {
                $iout=Linear11 ([int]$i.word_le)
                if ($rail.regulator -eq 'MAX15301' -or $iout.exponent -eq -1) {
                    $current=$iout.value;$currentStatus='PMBUS_LINEAR11'
                } else { $currentStatus='MAX20751_UNEXPECTED_IOUT_EXPONENT' }
            }
            if ($null -ne $p) {
                $poutStatus='invalid_raw'
                if ($p.api_status -eq 'returned') {
                    $decodedP=Linear11 ([int]$p.word_le)
                    if ($decodedP.exponent -eq 1) { $pout=$decodedP.value;$poutStatus='PMBUS_LINEAR11' }
                    else { $poutStatus='MAX20751_UNEXPECTED_POUT_EXPONENT' }
                }
            }
            $point=[ordered]@{record='rail_point';sweep=$sweep;position=$position;
                run_id=$env:SCALELLM_RUN_ID;block_id=$script:currentBlockId;
                repeat_id=$script:currentRepeatId;phase=$script:currentPhase;
                address=$rail.address;name=$rail.name;regulator=$rail.regulator;
                mode_word=$reader.mode;read_vout=$v;read_iout=$i;read_pout=$p;
                read_vout_id=$v.read_id;read_iout_id=$i.read_id;
                read_pout_id=$(if($null -ne $p){$p.read_id}else{$null});
                pout_status=$poutStatus;voltage_v=$voltage;voltage_status=$voltageStatus;
                current_a=$current;current_status=$currentStatus;pout_w=$pout;
                current_exponent=$(if($null -ne $iout){$iout.exponent}else{$null});
                pout_exponent=$(if($null -ne $decodedP){$decodedP.exponent}else{$null});
                vi_w=$(if($null -ne $voltage -and $null -ne $current){$voltage*$current}else{$null});
                vi_before_ticks=$v.before_ticks;vi_after_ticks=$i.after_ticks;
                point_after_ticks=$(if($null -ne $p){$p.after_ticks}else{$i.after_ticks});
                physical_aperture_contained_busy=$null;
                sensor_aperture_and_lag='UNKNOWN'}
            Append-Record $point
            if ($bad.Count) { $result.read_errors+=$bad.Count;throw ('PMBus read error on '+$rail.address) }
            $result.complete_rail_points++
        }
        $result.complete_sweeps++
        $sweepEnd=[Diagnostics.Stopwatch]::GetTimestamp()
        Append-Record ([ordered]@{record='sweep';run_id=$env:SCALELLM_RUN_ID;
            block_id=$script:currentBlockId;repeat_id=$script:currentRepeatId;phase=$script:currentPhase;
            sweep=$sweep;start_ticks=$sweepStart;end_ticks=$sweepEnd;
            target_due_ticks=$nextDue;late_ticks=$lateTicks;rail_order=@(
                0..6 | ForEach-Object {$readers[($sweep+$_)%7].rail.address});
            complete_rail_points=7})
        if ($TargetPeriodMs -gt 0) { $nextDue=[long]($sweepStart+$periodTicks) }
        if ($sweep -eq 0 -and $ReadyPath) {
            [IO.File]::WriteAllText($ReadyPath,(@{utc=[DateTime]::UtcNow.ToString('o');
                ticks=[Diagnostics.Stopwatch]::GetTimestamp();complete_sweeps=1}|ConvertTo-Json),
                (New-Object Text.UTF8Encoding($false)))
        }
        if ($IntervalMs -gt 0) { Start-Sleep -Milliseconds $IntervalMs }
    }
    $result.pass=($result.complete_sweeps -gt 0)
    $result.status=$(if($result.pass){'COMPLETE'}else{'NO_COMPLETE_SWEEP'})
} catch {
    $result.status='FAIL';$result.error=$_.Exception.Message
    Append-Record ([ordered]@{record='sampler_error';ticks=[Diagnostics.Stopwatch]::GetTimestamp();error=$result.error})
    throw
} finally {
    if ($null -ne $packetizer -and $null -ne $disconnect) {
        try { $disconnect.Invoke($packetizer,@()) } catch { $result.disconnect_error=$_.Exception.Message }
    }
    $result.finished_utc=[DateTime]::UtcNow.ToString('o')
    $result.finished_ticks=[Diagnostics.Stopwatch]::GetTimestamp()
    $result.elapsed_seconds=($result.finished_ticks-$result.started_ticks)/$frequency
    if ($result.Contains('sampling_started_ticks')) {
        $result.sampling_seconds=($result.finished_ticks-$result.sampling_started_ticks)/$frequency
    }
    [IO.File]::WriteAllText($EvidencePath,($result|ConvertTo-Json -Depth 10),
        (New-Object Text.UTF8Encoding($false)))
}
