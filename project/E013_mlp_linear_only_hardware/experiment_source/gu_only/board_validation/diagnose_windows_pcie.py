"""Bounded read-only comparison of XDMA configuration BAR and application BAR.

Configuration BAR values are never treated as application CSR identity.
"""
import ctypes as C
import json
import struct
import traceback
from scalellm_windows_xdma import WindowsXdmaSession,INVALID_HANDLE


def main():
    result={'scope':'read-only diagnostic; control BAR is XDMA configuration, user BAR is application','control':{},'user':{},'errors':[]}
    try:
        with WindowsXdmaSession(open_dma=False) as session:
            result['base']=session.base
            for offset in (0,4,0x100,0x104):result['user'][hex(offset)]=session.read32(offset)
            control=session.kernel.CreateFileW(session.base+'\\control',0x80000000,0,None,3,0x40000000,None)
            if control==INVALID_HANDLE:raise C.WinError(C.get_last_error())
            session.handles['control']=control
            for offset in (0,0x1000,0x2000,0x3000):result['control'][hex(offset)]=struct.unpack('<I',session._io('control',offset,4))[0]
    except Exception as error:result['errors'].append(type(error).__name__+': '+str(error));result['traceback']=traceback.format_exc()
    print(json.dumps(result))


if __name__=='__main__':main()
