"""Evidence-preserving bounded PowerShell calls for preparation, never device I/O."""
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import zlib


def invoke(script, evidence, label, timeout=45):
    evidence=Path(evidence)
    evidence.mkdir(parents=True,exist_ok=True)
    path=evidence/(label+'.ps1')
    if path.exists():raise FileExistsError(path)
    script="$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false);\n"+script
    path.write_text(script,encoding='utf-8')
    compressor=zlib.compressobj(9,wbits=-15)
    payload=base64.b64encode(compressor.compress(script.encode())+compressor.flush()).decode()
    wrapper="$b=[Convert]::FromBase64String('"+payload+"');$m=New-Object IO.MemoryStream(,$b);$d=New-Object IO.Compression.DeflateStream($m,[IO.Compression.CompressionMode]::Decompress);$r=New-Object IO.StreamReader($d,[Text.Encoding]::UTF8);& ([ScriptBlock]::Create($r.ReadToEnd()))"
    argv=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=1','hap-dell-direct','powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(wrapper.encode('utf-16le')).decode()]
    identity={'host':'hap-dell-direct','started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'script_sha256':hashlib.sha256(script.encode()).hexdigest(),'timeout_s':timeout}
    (evidence/(label+'.started.json')).write_text(json.dumps(identity,indent=2)+'\n')
    try:
        result=subprocess.run(argv,capture_output=True,timeout=timeout)
        code=result.returncode;stdout=result.stdout;stderr=result.stderr
    except subprocess.TimeoutExpired as error:
        code=None;stdout=error.stdout or b'';stderr=error.stderr or b''
    for suffix,data in [('stdout',stdout),('stderr',stderr)]:
        (evidence/(label+'.'+suffix+'.bin')).write_bytes(data)
        (evidence/(label+'.'+suffix+'.txt')).write_text(data.decode('utf-8-sig',errors='replace'),encoding='utf-8')
    (evidence/(label+'.exit.json')).write_text(json.dumps({'exit_code':code,'timed_out':code is None,'ended_utc':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
    if code!=0:raise RuntimeError('Remote preparation failed: '+label+' exit='+str(code))
    return stdout.decode('utf-8-sig')
