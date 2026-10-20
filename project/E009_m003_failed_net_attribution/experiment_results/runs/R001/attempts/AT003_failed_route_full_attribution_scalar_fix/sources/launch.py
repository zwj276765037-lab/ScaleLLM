#!/usr/bin/env python3
"""Detach the single approved SM013 supervisor, preserving actual receipt."""
import json,subprocess,time
import prepare as p
def main():
    receipt=p.AT/'detached_launch.json';log=p.AT/'supervisor.log'
    assert not receipt.exists() and not log.exists()
    argv=['taskset','-c','0-7','nice','-n','5','/usr/bin/python3',str(p.HERE/'supervise.py')]
    with log.open('xb') as f:
        child=subprocess.Popen(argv,cwd=p.ROOT,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
    time.sleep(.3)
    value=dict(argv=argv,supervisor=p.proc(child.pid),poll=child.poll(),log=str(log),limitation='Launcher receipt only; verify native_start and lock separately.')
    p.save(receipt,value);print(json.dumps(value,indent=2))
if __name__=='__main__':main()
