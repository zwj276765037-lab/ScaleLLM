#!/usr/bin/env python3
"""Read-only snapshots of this one native E005 worker's transient XDC files."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time


def stamp():
    return datetime.now(timezone.utc).isoformat()


def main():
    runtime, destination = (Path(p).resolve() for p in sys.argv[1:3])
    native_pid, native_start = map(int,sys.argv[3:5])
    assert runtime.name == f'Vivado-{native_pid}-user'
    assert not destination.exists()
    os.sched_setaffinity(0,set(range(8)))
    os.setpriority(os.PRIO_PROCESS,0,5)
    destination.mkdir()
    metadata=dict(started_utc=stamp(),observer_pid=os.getpid(),runtime_root=str(runtime),
        native_pid=native_pid,native_start_ticks=native_start,
        scope='read-only snapshots of observed generated XDC versions; no tool process control',
        limitation='observed bytes do not independently establish what was read before the first observation')
    with (destination/'started.json').open('x') as out:json.dump(metadata,out,indent=2)
    seen=set();error=None
    try:
        with (destination/'observations.jsonl').open('x',buffering=1) as records:
            while True:
                for source in sorted(runtime.rglob('*.xdc')):
                    try:
                        before=source.stat();raw=source.read_bytes();after=source.stat()
                        if not raw or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):continue
                        digest=hashlib.sha256(raw).hexdigest();key=(str(source),digest)
                        if key in seen:continue
                        copy=destination/'versions'/digest/source.name
                        copy.parent.mkdir(parents=True,exist_ok=True)
                        if not copy.exists():
                            with copy.open('xb') as out:out.write(raw)
                        records.write(json.dumps(dict(observed_utc=stamp(),source_path=str(source),
                            source_mtime_ns=after.st_mtime_ns,path=str(copy),bytes=len(raw),sha256=digest))+'\n')
                        seen.add(key)
                    except (FileNotFoundError,ProcessLookupError):continue
                try:
                    fields=Path(f'/proc/{native_pid}/stat').read_text().rsplit(')',1)[1].split()
                    present=int(fields[19])==native_start and fields[0]!='Z'
                except FileNotFoundError:present=False
                if not present:break
                time.sleep(5)
    except BaseException as exc:error=f'{type(exc).__name__}:{exc}'
    finally:
        with (destination/'status.json').open('x') as out:
            json.dump(dict(**metadata,ended_utc=stamp(),observed_source_versions=len(seen),observer_error=error),out,indent=2)


if __name__=='__main__':main()
