$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$r=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');project_directories=@();known_script=$null;python=$null;inf=$null}
if([IO.Directory]::Exists('D:\project')) {$r.project_directories=@([IO.Directory]::GetDirectories('D:\project') | Where-Object {$_ -match 'dma|pcie|fpga|vcu|scalellm|hap|test'})}
$p='C:\Users\dell\Desktop\hap_check_pcie_link.ps1'
if([IO.File]::Exists($p)){$r.known_script=[IO.File]::ReadAllText($p)}
$p='C:\Windows\INF\oem113.inf'
if([IO.File]::Exists($p)){$r.inf=[IO.File]::ReadAllText($p)}
$python='D:\software\Anaconda3\python.exe'
if([IO.File]::Exists($python)){$r.python=@(& $python -c 'import sys,json,importlib.util;print(json.dumps({"version":sys.version,"executable":sys.executable,"numpy":importlib.util.find_spec("numpy") is not None}))' 2>&1 | ForEach-Object {$_.ToString()});$r.python_exit=$LASTEXITCODE}
$r|ConvertTo-Json -Depth 5 -Compress
