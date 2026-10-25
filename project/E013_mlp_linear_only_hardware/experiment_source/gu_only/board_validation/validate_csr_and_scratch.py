#!/usr/bin/env python3
"""Validate actual application CSR identity, optionally test reserved DDR pages."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import traceback

from scalellm_windows_xdma import create_session

IDENTITY={0x000:0x48384103,0x004:0x00020000,0x100:0x48384605,0x104:0x00070000,0x2b8:0x4d303032,0x300:0x4d4c0002,0x304:0x1d,0x308:1}
STATE=(0x10c,0x14c,0x178,0x260,0x2a8,0x324,0x350,0x370)


def save(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def snapshot(session):
    return {'0x%03x'%offset:session.read32(offset) for offset in tuple(IDENTITY)+STATE}


def check(snapshot):
    for offset,expected in IDENTITY.items():
        actual=snapshot['0x%03x'%offset]
        if actual!=expected:raise RuntimeError('Application CSR identity mismatch0x%03x: actual0x%08x expected0x%08x'%(offset,actual,expected))
    if snapshot['0x324']&31!=8:raise RuntimeError('GU status is not idle/quiescent/fault-free')
    if not snapshot['0x10c']&32:raise RuntimeError('Shared owner not ready')
    if snapshot['0x2a8']&3:raise RuntimeError('GU maintenance active/pending')
    if snapshot['0x260']&0x1c:raise RuntimeError('Paired fault/active state')
    if snapshot['0x350'] or snapshot['0x370']:raise RuntimeError('DONE error or admission error retained')


def csr(session,path):
    snapshots=[]
    for index in range(3):
        item=snapshot(session);snapshots.append(item);save(path/'csr_snapshots.json',snapshots)
        check(item)
        if index: 
            if item!=snapshots[0]:raise RuntimeError('CSR identity/state snapshots are not stable')
        time.sleep(.1)
    return snapshots


def scratch(session,path):
    address=0x7fff0000;size=4096;backups={};modified=set();result={'scope':'dual DDR reserved local page; restore original data','local_address':address,'host_addresses':[address,0x80000000+address],'size':size,'checks':[],'restoration':{},'error':None}
    for channel in (0,1):
        backups[channel]=session.c2h_read_local(channel,size,address,size)
        (path/('ddr%d_original.bin'%channel)).write_bytes(backups[channel])
    patterns={channel:bytes(((i*37+(i>>4)*13+0x51+channel*0x76)&255) for i in range(size)) for channel in (0,1)}
    for channel in (0,1):(path/('ddr%d_pattern.bin'%channel)).write_bytes(patterns[channel])
    try:
        for channel in (0,1):
            check(snapshot(session))
            modified.add(channel)
            written=session.h2c_write_local(channel,patterns[channel],address,size)
            if written!=size:raise IOError('Short scratch write')
            readbacks={c:session.c2h_read_local(c,size,address,size) for c in (0,1)}
            for c in (0,1):
                (path/('after_ddr%d_write_ddr%d.bin'%(channel,c))).write_bytes(readbacks[c])
                expected=patterns[c] if c in modified else backups[c]
                if readbacks[c]!=expected:raise RuntimeError('DDR mismatch or alias after writing channel%d, reading%d'%(channel,c))
            result['checks'].append({'written_channel':channel,'bytes':written,'both_channels_match':True,'read_sha256':{str(c):hashlib.sha256(readbacks[c]).hexdigest() for c in (0,1)}})
            save(path/'scratch_result.json',result)
    except BaseException as error:
        result['error']=type(error).__name__+': '+str(error)
        raise
    finally:
        for channel in sorted(modified):
            try:
                count=session.h2c_write_local(channel,backups[channel],address,size)
                actual=session.c2h_read_local(channel,size,address,size)
                (path/('ddr%d_restored_readback.bin'%channel)).write_bytes(actual)
                result['restoration'][str(channel)]={'written':count,'match':actual==backups[channel],'sha256':hashlib.sha256(actual).hexdigest()}
                if count!=size or actual!=backups[channel]:result['restoration'][str(channel)]['error']='restoration mismatch'
            except BaseException as error:result['restoration'][str(channel)]={'error':type(error).__name__+': '+str(error)}
        save(path/'scratch_result.json',result)
    if any(not item.get('match') for item in result['restoration'].values()):raise RuntimeError('Scratch restoration failed; preserve backups')
    result['verdict']='PASS';save(path/'scratch_result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--result',type=Path,required=True);parser.add_argument('--scratch',action='store_true');args=parser.parse_args()
    args.result.mkdir(parents=True,exist_ok=False)
    report={'execution_state':'running','scope':'P3'+('/P4' if args.scratch else ''),'hardware_writes':bool(args.scratch),'csr':'NOT_RUN','scratch':'NOT_RUN'}
    save(args.result/'result.json',report)
    try:
        with create_session() as session:
            csr(session,args.result);report['csr']='PASS';save(args.result/'result.json',report)
            if args.scratch:scratch(session,args.result);report['scratch']='PASS'
        report['execution_state']='completed'
    except BaseException as error:
        report.update(execution_state='failed',error=type(error).__name__+': '+str(error),traceback=traceback.format_exc())
        save(args.result/'result.json',report);raise
    finally:save(args.result/'result.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
