# Executes only the recorder/statistics fragments with synthetic CPU data.
# No vendor assembly, USB, PMBus or FPGA access.
$ErrorActionPreference='Stop'
$text=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'sample_power.ps1') -Raw
$temp=Join-Path ([IO.Path]::GetTempPath()) ('ScaleLLM stream CPU '+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp|Out-Null
try {
    $JsonlPath=Join-Path $temp 'all sweeps.jsonl'
    $result=[ordered]@{timestamp=(Get-Date).ToString('o');samples=@();in_progress_sample=$null;complete_sample_count=0}
    $start=$text.IndexOf('    $sampleCountDone=0;')
    $end=$text.IndexOf('    for ($sampleIndex', $start)
    Invoke-Expression $text.Substring($start,$end-$start)
    $start=$text.IndexOf('        $sample["sweep_ended_utc"]')
    $end=$text.IndexOf('        # Recorder lifetime', $start)
    $record=[ScriptBlock]::Create($text.Substring($start,$end-$start))
    for($i=0;$i-lt3000;$i++){
        $sample=[ordered]@{index=$i;timestamp=(Get-Date).ToString('o');rails=@();monitored_power_w=12.5;monitored_power_quantization_half_step_bound_w=3}
        $result.in_progress_sample=$sample
        . $record
    }
    $start=$text.IndexOf('    $result.summary = [ordered]@{')
    $end=$text.IndexOf('    $result.pass = $true', $start)
    Invoke-Expression $text.Substring($start,$end-$start)
    $bytes=($result|ConvertTo-Json -Depth 9).Length
    $lines=[IO.File]::ReadAllLines($JsonlPath)
    if($result.samples.Count-ne0-or$null-ne$result.in_progress_sample-or$result.complete_sample_count-ne3000-or$result.summary.sample_count-ne3000-or$result.summary.monitored_power_mean_w-ne12.5-or$lines.Count-ne3000-or$bytes-gt2048){throw 'Streaming retention/summary mismatch'}
    $partial=[ordered]@{index=3000;rails=@(@{raw='retained-failed-read'})}
    $result.in_progress_sample=$partial
    if(($result|ConvertTo-Json -Depth 9)-notmatch'retained-failed-read'){throw 'Failed partial sweep lost'}
    @{status='PASS';synthetic_sweeps=3000;jsonl_lines=$lines.Count;retained_samples=$result.samples.Count;final_summary_characters=$bytes;partial_failure_retained=$true;board_io=$false}|ConvertTo-Json
}finally{Remove-Item -LiteralPath $temp -Recurse}
