# CPU-only parsing, argument construction and PID/birth cleanup checks.
# Never loads the vendor tool, opens XDMA, or accesses the board.
$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue'
$launcher=Join-Path $PSScriptRoot 'measure_full_run.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($launcher,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
$function=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name-eq'Join-NativeArguments'},$true)
Invoke-Expression $function.Extent.Text
$actual=Join-NativeArguments @('a b','C:\path with space\','say"hi','')
$expected=@('"a b"','"C:\path with space\\"','"say\"hi"','""') -join ' '
if($actual-ne$expected){throw ('Windows argument escaping mismatch: '+$actual)}
$temp=Join-Path ([IO.Path]::GetTempPath()) ('ScaleLLM power CPU '+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp|Out-Null
try {
    $config=Join-Path $temp 'config with spaces.json';$requests=Join-Path $temp 'requests with spaces.json';$output=Join-Path $temp 'new output with spaces'
    [IO.File]::WriteAllText($config,'{"schema":"scalellm_final_deploy_v1","wall_seconds":30,"command_timeout_seconds":10}')
    [IO.File]::WriteAllText($requests,'[{"slot":0,"prompt_token_ids":[9906],"max_new_tokens":1}]')
    $native=Join-Path $PSHOME 'powershell.exe'
    $plan=& $native -NoProfile -NonInteractive -File $launcher -RuntimeRoot 'C:\vendor path with spaces' -AdapterSerial 'CPU_ONLY' -Config $config -Requests $requests -Output $output -BoardLease (Join-Path $temp 'lease file') -Python 'C:\python path\python.exe' -WholeSeconds 60 -PlanOnly
    if($LASTEXITCODE-ne0){throw 'Plan-only native child failed'}
    $plan=$plan|ConvertFrom-Json
    if($plan.board_io-or$plan.launcher_board_tested-or$plan.command[2]-ne'--config'-or$plan.command[3]-ne$config-or$plan.command[4]-ne'run'-or$plan.command[6]-ne$requests-or(Test-Path -LiteralPath $output)){throw 'Plan command or no-I/O contract failed'}
} finally {Remove-Item -LiteralPath $temp -Recurse}
# Execute the production finally body against mocked PID identities. A reused
# PID must never be stopped. These fake identifiers cannot reach Stop-Process.
function Observe-Owned {}
function Start-Sleep {param($Milliseconds)}
function Save-Receipt {$script:saved=$true}
$script:births=@{'9876501'='OWNED';'9876502'='UNRELATED_NEW_BIRTH'}
function Cim-Birth([int]$ProcessId){return $script:births[[string]$ProcessId]}
$script:stopped=@()
function Stop-Process {param([int]$Id,[switch]$Force,$ErrorAction);$script:stopped+=$Id;$script:births.Remove([string]$Id)}
$owned=@{'9876501'='OWNED';'9876502'='OLD_BIRTH'}
$receipt=@{owned_cleanup=@()};$sampler=$null;$lock=New-Object IO.MemoryStream
$main=@($ast.EndBlock.Statements|Where-Object{$_ -is [Management.Automation.Language.TryStatementAst]})[-1]
$body=$main.Finally.Extent.Text
& ([ScriptBlock]::Create($body.Substring(1,$body.Length-2)))
if($script:stopped.Count-ne1-or$script:stopped[0]-ne9876501-or$receipt.survivors.Count-or-not$receipt.lease_released-or-not$script:saved){throw 'PID/birth failure cleanup mock did not preserve unrelated PID'}
@{status='PASS';checks=@('PS parse','Windows quoting','spaces in plan-only CLI','no output or board I/O','failure PID/birth cleanup');board_tested=$false}|ConvertTo-Json -Depth 4
