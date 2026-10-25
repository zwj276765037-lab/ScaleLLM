"""Portable read-only device identity; no instance, INF or host path is baked in."""
import base64
import ctypes
import json
import os
import subprocess

CONFIG={}
def configure(value):
    global CONFIG
    CONFIG=dict(value)


def system_identity():
    if os.name!='nt':raise RuntimeError('Windows XDMA execution requires Windows')
    requested=CONFIG.get('pci_instance_id')
    encoded=base64.b64encode(json.dumps(requested).encode()).decode()
    script=r"""$ErrorActionPreference='Stop';[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
$requested=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('REQUEST'))|ConvertFrom-Json
$devices=@(Get-PnpDevice -PresentOnly|Where-Object{$_.InstanceId -like 'PCI\VEN_10EE&DEV_9018*'})
if($requested){$devices=@($devices|Where-Object{$_.InstanceId-eq$requested})}
if($devices.Count-ne1){throw 'Expected exactly one present VEN10EE DEV9018, or configure its exact instance'}
$d=$devices[0];$i=$d.InstanceId;$p=@(Get-CimInstance Win32_PnPSignedDriver|Where-Object{$_.DeviceID-eq$i})
if($p.Count-ne1){throw 'Installed signed-driver identity is ambiguous'}
$b=Get-CimInstance Win32_OperatingSystem;$sys=Join-Path $env:SystemRoot 'System32/drivers/XDMA.sys'
$poll=Get-ItemPropertyValue 'HKLM:/SYSTEM/CurrentControlSet/Services/XDMA/Parameters' -Name POLL_MODE
[ordered]@{boot_utc=$b.LastBootUpTime.ToUniversalTime().ToString('o');driver=[ordered]@{instance_id=$i;published_inf=$p[0].InfName;version=$p[0].DriverVersion;sys_sha256=(Get-FileHash $sys -Algorithm SHA256).Hash.ToLower();pnp_status=$d.Status;poll_mode=[int]$poll}}|ConvertTo-Json -Depth 6
""".replace('REQUEST',encoded)
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],capture_output=True,timeout=30)
    if result.returncode:raise RuntimeError('Device identity query failed: '+result.stderr.decode('utf-8',errors='replace'))
    value=json.loads(result.stdout.decode('utf-8-sig'));driver=value['driver']
    if driver['pnp_status']!='OK' or driver['poll_mode']!=1:raise RuntimeError('Driver requires PnP OK and original DMA POLL_MODE1: '+repr(driver))
    for config_key,field in [('expected_driver_sha256','sys_sha256'),('expected_driver_inf','published_inf'),('expected_driver_version','version')]:
        if CONFIG.get(config_key) and str(driver[field]).lower()!=str(CONFIG[config_key]).lower():raise RuntimeError('Configured driver identity mismatch: '+field)
    return value


def control_snapshot(raw):
    name='control'
    if name not in raw.handles:
        h=raw.kernel.CreateFileW(raw.base+'\\control',0x80000000,0,None,3,0x40000000,None)
        if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        raw.handles[name]=h;raw.paths[name]=raw.base+'\\control'
    addresses=(0x2000,0x3000,0x2004,0x2010,0x2040,0x2044,0x2048,0x204c,0x3014)
    values={'0x%04x'%a:int.from_bytes(raw._io(name,a,4),'little') for a in addresses}
    expected={'0x2000':0x1fc20006,'0x3000':0x1fc30006,'0x2004':0,'0x2010':0,'0x2040':0,'0x2044':0,'0x2048':0,'0x204c':0,'0x3014':1}
    if values!=expected:raise RuntimeError('Read-only post-DMA-open control policy mismatch: '+repr(values))
    return values


def csr_snapshots(session):
    att={'0x%03x'%a:session.read32(a) for a in (0,4,0xc,0x38,0x4c,0x78,0x7c,0x80,0x84,0x88)}
    gu={'0x%03x'%a:session.read32(a) for a in (0x100,0x104,0x10c,0x144,0x178,0x260,0x2a8,0x2b8,0x300,0x304,0x308,0x324,0x350,0x368,0x370)}
    # A freshly programmed board is clean MODE_IDLE (20/20). The unchanged
    # production stage_gu_layer legally selects SHARED before any Attention
    # work. A subsequent/final snapshot in this session must be SHARED.
    initial=not getattr(session,'_deploy_initial_snapshot_done',False)
    owners=(gu['0x10c'],gu['0x260'])
    # owner_done bit6 is historical sticky state, cleared by safe maintenance;
    # owner_request_ready bit5 and both launch-allowed bits remain required.
    owner_ok=(owners[0]&0x3f==0x3b and owners[0]&~0x7f==0 and owners[1]==0x23) or (initial and owners==(0x20,0x20))
    abi_ok=tuple(gu[a] for a in ('0x100','0x104','0x300','0x304','0x308','0x2b8'))==(0x48384605,0x70000,0x4d4c0002,0x1d,1,0x4d303032)
    if att['0x000']!=0x48384103 or att['0x004']!=0x20000 or not abi_ok or att['0x00c']&0x27 or att['0x04c'] or gu['0x324']!=8 or (gu['0x324']&2 and gu['0x350']) or gu['0x370'] or gu['0x178'] or gu['0x2a8'] or not owner_ok:raise RuntimeError('Non-idle or incompatible device: '+repr((att,gu)))
    session._deploy_initial_snapshot_done=True
    return att,gu
