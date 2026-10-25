"""Read only the verified XDMA IRQ/config allowlist; never open DMA nodes.

Windows Python 3.6 compatible. The installed driver maps \\control to its
identified configuration BAR (sys/file_io.c:167-169). Identifier validation
precedes IRQ telemetry. This module intentionally contains no register writes.
"""
import argparse
import ctypes as C
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--transport', required=True)
    p.add_argument('--result', required=True)
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('verified_windows_xdma', a.transport)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    s = adapter.WindowsXdmaSession(timeout_ms=5000, open_dma=False)
    result = {'utc': datetime.datetime.utcnow().isoformat()+'Z',
              'transport_sha256': hashlib.sha256(Path(a.transport).read_bytes()).hexdigest(),
              'probe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'operation': 'control_irq_readonly', 'register_writes': 0,
              'opened_nodes': [], 'reads': [], 'handles_closed': False,
              'verdict': 'NOT_COMPLETED'}
    def persist():
        Path(a.result).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    persist()
    try:
        candidates = [x for x in s.enumerate() if 'ven_10ee&dev_9018' in x.lower()]
        if len(candidates) != 1:
            raise RuntimeError('Expected exactly one VEN10EE DEV9018 interface')
        path = candidates[0]+'\\control'
        h = s.kernel.CreateFileW(path, 0x80000000, 0, None, 3, 0x40000000, None)
        if h == adapter.INVALID_HANDLE:
            raise C.WinError(C.get_last_error())
        s.handles['control'] = h
        result['opened_nodes'] = [path]
        def read(offset, name):
            value = struct.unpack('<I', s._io('control', offset, 4))[0]
            item = {'offset': offset, 'offset_hex': hex(offset), 'name': name,
                    'value': value, 'value_hex': '0x%08x'%value,
                    'utc': datetime.datetime.utcnow().isoformat()+'Z'}
            result['reads'].append(item)
            persist()
            print(json.dumps(item), flush=True)
            return value
        irq_id = read(0x2000, 'irq_identifier')
        config_id = read(0x3000, 'config_identifier')
        if irq_id & 0xffff0000 != 0x1fc20000 or config_id & 0xffff0000 != 0x1fc30000:
            raise RuntimeError('Control mapping identifier mismatch; no further read')
        for offset, name in [(0x2004, 'user_interrupt_enable'),
                             (0x2010, 'channel_interrupt_enable'),
                             (0x2040, 'user_interrupt_request'),
                             (0x2044, 'channel_interrupt_request'),
                             (0x2048, 'user_interrupt_pending'),
                             (0x204c, 'channel_interrupt_pending'),
                             (0x3014, 'msi_enable')]:
            read(offset, name)
        result['verdict'] = 'PASS_READ_ONLY'
    except BaseException as e:
        result['verdict'] = 'FAILED'
        result['error'] = repr(e)
        raise
    finally:
        s.close()
        result['handles_closed'] = not s.handles
        result['ended_utc'] = datetime.datetime.utcnow().isoformat()+'Z'
        persist()


if __name__ == '__main__':
    main()
