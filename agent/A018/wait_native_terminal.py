"""Block on a single owned-job terminal file with inotify; never poll logs or control EDA."""
from pathlib import Path
import argparse, ctypes, datetime, json, os, struct

p = argparse.ArgumentParser()
p.add_argument('--status', type=Path, required=True)
p.add_argument('--receipt', type=Path, required=True)
p.add_argument('--result', type=Path, required=True)
a = p.parse_args()
os.sched_setaffinity(0, set(range(8)))
os.setpriority(os.PRIO_PROCESS, 0, 5)
libc = ctypes.CDLL(None, use_errno=True)
fd = libc.inotify_init1(os.O_CLOEXEC)
if fd < 0:
    raise OSError(ctypes.get_errno(), 'inotify_init1')
# Observe only terminal-file creation/atomic replacement or close-after-write.
wd = libc.inotify_add_watch(fd, os.fsencode(a.status.parent), 0x00000008 | 0x00000080 | 0x00000100)
if wd < 0:
    raise OSError(ctypes.get_errno(), 'inotify_add_watch')
ticks = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
receipt = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               pid=os.getpid(), start_ticks=ticks, mechanism='Linux inotify blocking read',
               status=str(a.status.resolve()), logs_read=False, EDA_control=False,
               no_periodic_model_or_log_polling=True,
               lifecycle='only this active tool wait; no independent agent wakeup promised')
with a.receipt.open('x') as stream:
    json.dump(receipt, stream, indent=2); stream.write('\n')
print(json.dumps(dict(waiter_started=True, **receipt)), flush=True)
while True:
    if a.status.is_file():
        value = json.loads(a.status.read_text())
        if value.get('execution_state') in {'completed', 'failed'}:
            result = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          status=str(a.status.resolve()), terminal=value,
                          waiter_pid=os.getpid(), waiter_start_ticks=ticks)
            with a.result.open('x') as stream:
                json.dump(result, stream, indent=2); stream.write('\n')
            print(json.dumps(result), flush=True)
            os.close(fd)
            break
    # No timers: remain in the kernel until a file event occurs.
    data = os.read(fd, 65536)
    offset = 0
    while offset < len(data):
        descriptor, mask, cookie, length = struct.unpack_from('iIII', data, offset)
        name = data[offset + 16:offset + 16 + length].split(b'\0', 1)[0]
        offset += 16 + length
        if name == os.fsencode(a.status.name):
            break
