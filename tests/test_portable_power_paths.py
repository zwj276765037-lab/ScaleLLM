"""Windows command line boundary regression without board or PowerTool access."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
LAUNCHER=ROOT/'resource_optimization/deployment/power/run_power.ps1'


class PortablePowerPathTests(unittest.TestCase):
    def test_every_child_start_uses_native_argument_encoding(self):
        script=LAUNCHER.read_text()
        self.assertEqual(script.count('Start-Process -FilePath'),1)
        self.assertIn('-ArgumentList (Native-Arguments $Arguments)',script)
        self.assertIn('$configBase=Split-Path -Parent $ConfigFile',script)
        self.assertIn('Join-Path $configBase $value',script)

    @unittest.skipUnless(os.name=='nt','Windows PowerShell native process boundary test')
    def test_spaces_unicode_quotes_and_terminal_slashes_round_trip(self):
        script=LAUNCHER.read_text()
        functions=script[script.index('function Quote-NativeArgument'):script.index('function Hash')]
        with tempfile.TemporaryDirectory(prefix='portable power paths ') as temporary:
            folder=Path(temporary)
            child=folder/'child probe.py'
            child.write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\n')
            arguments=['Stage Root with spaces','路径 含 空格','C:\\Power Tool\\','a"b','trailing slash \\','']
            payload=folder/'argument values.json';payload.write_text(__import__('json').dumps(arguments),encoding='utf-8')
            quote=lambda s:"'"+str(s).replace("'","''")+"'"
            output=folder/'native result.json'
            ps=folder/'argument test.ps1'
            ps.write_text(functions+f'''
$ErrorActionPreference='Stop'
$values=Get-Content -LiteralPath {quote(payload)} -Raw|ConvertFrom-Json
if($values.Count -ne {len(arguments)}){{throw 'Argument fixture array count differs'}}
$args=@({quote(child)})+$values
$p=Start-Process -FilePath {quote(sys.executable)} -ArgumentList (Native-Arguments $args) -Wait -PassThru -RedirectStandardOutput {quote(output)}
if($p.ExitCode -ne 0){{throw 'Native argument probe failed'}}
''',encoding='utf-8-sig')
            completed=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(ps)],capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual(__import__('json').loads(output.read_text()),arguments)


if __name__=='__main__':
    unittest.main()
