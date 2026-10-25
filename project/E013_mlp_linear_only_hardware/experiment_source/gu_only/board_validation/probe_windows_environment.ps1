$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$r=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');project_directories=@();known_script=$null;python=$null;inf=$null}
if([IO.Directory]::Exists('D:\project')) {$r.project_directories=@([IO.Directory]::GetDirectories('D:\project') | Where-Object {$_ -match 'dma|pcie|fpga|vcu|scalellm|hap|test'})}
$p='C:\Users\dell\Desktop\hap_check_pcie_link.ps1'
if([IO.File]::Exists($p)){$r.known_script=[IO.File]::ReadAllText($p)}
$p='C:\Windows\INF\oem113.inf'
if([IO.File]::Exists($p)){$r.inf=[IO.File]::ReadAllText($p)}
$python='D:\software\Anaconda3\python.exe'
if([IO.File]::Exists($python)){
    $r.python=@(& $python -c 'import sys;print(sys.version);print(sys.executable)' 2>&1 | ForEach-Object {$_.ToString()});$r.python_exit=$LASTEXITCODE
    try {$r.numpy=@(& $python -c 'import numpy;print(numpy.__version__)' 2>&1 | ForEach-Object {$_.ToString()});$r.numpy_exit=$LASTEXITCODE} catch {$r.numpy_error=$_.Exception.Message}
}
$r|ConvertTo-Json -Depth 5 -Compress
