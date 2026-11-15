function Assert-BoardOwner([string]$StageRoot) {
    $owner=Get-Content -LiteralPath (Join-Path $StageRoot 'board_owner.json') -Raw|ConvertFrom-Json
    $live=Get-CimInstance Win32_Process -Filter ('ProcessId='+$owner.owner_pid)
    if($owner.state -ne 'LEASE_HELD' -or -not $live -or $live.CreationDate.ToUniversalTime().ToString('o') -ne $owner.owner_birth){throw 'External exclusive board lease unavailable'}
    return $owner
}
