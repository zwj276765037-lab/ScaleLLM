$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$r=[ordered]@{schema=1;utc=[DateTime]::UtcNow.ToString('o');scope='read-only inspection of existing power tooling and logs';usb=@();processes=@();directories=@();sources=@();recent_logs=@();errors=@()}
$r.usb=@(Get-PnpDevice -PresentOnly|Where-Object {$_.InstanceId -like 'USB\VID_0B6A&PID_5300*'}|Select-Object Status,FriendlyName,InstanceId,Problem)
$r.processes=@(Get-CimInstance Win32_Process|Where-Object {$_.Name -match 'maxim|powertool|pmbus' -or $_.ExecutablePath -match 'MaximPowerTool'}|Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate)
$roots=@('C:\Users\dell\Documents\MaximPowerToolReadonly','C:\Users\dell\Documents\powertoollogs')
foreach($root in $roots){
 if(-not [IO.Directory]::Exists($root)){continue}
 try{
  $items=@(Get-ChildItem -LiteralPath $root -ErrorAction Stop|Select-Object -First 100)
  $r.directories+=[ordered]@{root=$root;items=@($items|Select-Object Name,FullName,Length,PSIsContainer,LastWriteTimeUtc)}
  if($root -like '*Readonly'){
   $files=@($items|Where-Object {-not $_.PSIsContainer -and $_.Length -le 65536 -and $_.Extension -match '^\.(ps1|py|cs|json|md|config)$'}|Select-Object -First 16)
   foreach($file in $files){$r.sources+=[ordered]@{path=$file.FullName;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower();content=[IO.File]::ReadAllText($file.FullName)}}
  }else{
   foreach($file in @($items|Where-Object {-not $_.PSIsContainer}|Sort-Object LastWriteTimeUtc -Descending|Select-Object -First 5)){
    $tail=@(Get-Content -LiteralPath $file.FullName -Tail 8 -ErrorAction SilentlyContinue|ForEach-Object {$_.ToString()})
    $r.recent_logs+=[ordered]@{path=$file.FullName;bytes=$file.Length;last_write_utc=$file.LastWriteTimeUtc;tail=$tail}
   }
  }
 }catch{$r.errors+=$root+': '+$_.Exception.Message}
}
$trace='C:\Users\dell\Documents\MaximDevice_Trace.txt.zip'
if([IO.File]::Exists($trace)){$r.trace_archive=Get-Item -LiteralPath $trace|Select-Object FullName,Length,LastWriteTimeUtc}
$r|ConvertTo-Json -Depth 8 -Compress
