#!/usr/bin/env python3
"""One guarded read-only native process; no wall/no-output stop."""
import datetime,fcntl,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
import prepare as p
sys.path.insert(0,str(p.ROOT/'project/hardware/vivado/scripts'))
import run_m002_no_wall as guard
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,value):
    t=path.with_suffix(path.suffix+'.tmp');t.write_text(json.dumps(value,indent=2)+'\n');t.replace(path)
def interrupted(sig,frame):raise KeyboardInterrupt(f'signal {sig}')
def main():
    at=p.AT;out=at/'evidence/native';assert not out.exists(),'Never overwrite a native attempt'
    manifest=json.loads((p.HERE/'prepared_manifest.json').read_text())
    for r in manifest['files']:assert p.ident(r['path'])==r,'prepared source changed'
    assert (at/'independent_prelaunch_accepted.json').is_file(),'Independent prelaunch evidence missing'
    review=json.loads((at/'independent_prelaunch_accepted.json').read_text())
    assert review['no_substantive_blocker'] is True
    assert p.ident(review['review_evidence']['path'])==review['review_evidence']
    assert review['prepared_manifest']==p.ident(p.HERE/'prepared_manifest.json')
    os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
    lock=(p.ROOT/'project/hardware/vivado/.m002_eda.lock').open('r');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    before=p.check_baseline(json.loads((p.HERE/'baseline.json').read_text()))
    out.mkdir(parents=True);archive=at/'sources';archive.mkdir()
    for r in manifest['files']:shutil.copy2(r['path'],archive/Path(r['path']).name)
    shutil.copy2(p.HERE/'prepared_manifest.json',archive/'prepared_manifest.json')
    bindings=dict(prepared_manifest=p.ident(p.HERE/'prepared_manifest.json'),archive=[p.ident(x) for x in archive.iterdir()],baseline=p.ident(p.HERE/'baseline.json'),review=p.ident(at/'independent_prelaunch_accepted.json'),preflight=before)
    save(at/'input_bindings.json',bindings)
    env={k:v for k,v in os.environ.items() if not k.startswith(('HAP_','E005_','E006_','SLR2_','M003_'))}
    env.update(M003_DCP=str(p.DCP),M003_OUT=str(out),M003_TARGETS=str(archive/'targets.tcl'),M003_AGGREGATE=str(archive/'aggregate.py'),M003_PLAN=str(archive/'query_plan.json'),OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    cmd=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace','-source',str(archive/'attribution.tcl'),'-log',str(out/'vivado.log'),'-journal',str(out/'vivado.jou')]
    meta=dict(stage='SM013_readonly_failed_net_attribution',started_utc=utc(),argv=cmd,cwd=str(out),supervisor_pid=os.getpid(),supervisor_start_ticks=p.proc(os.getpid())['start_ticks'],cpu_affinity=list(range(8)),nice=5,max_threads=8,timeout_seconds=None,no_output_timeout_seconds=None,wall_clock_stop_disabled=True,inputs=p.ident(at/'input_bindings.json'),limits=json.loads((archive/'query_plan.json').read_text())['limits'])
    save(at/'command.json',meta)
    proc=None;tracked={};stop=None;peak=0;low_since=None;minmem=guard.mem_available();mindisk=shutil.disk_usage(p.ROOT).free;begin=time.monotonic()
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        with (at/'launcher.log').open('x') as log,(at/'resources.jsonl').open('x',buffering=1) as resources:
            proc=subprocess.Popen(cmd,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            meta.update(leader_pid=proc.pid,leader_start_ticks=p.proc(proc.pid)['start_ticks'],process_group=proc.pid)
            save(at/'started.json',meta);print(json.dumps(meta),flush=True)
            while True:
                owned=guard.owned_processes(guard.process_table(),proc.pid,tracked)
                for pid in owned:
                    try:os.sched_setaffinity(pid,set(range(8)))
                    except ProcessLookupError:pass
                rss=sum(r['rss_bytes'] for r in owned.values());mem=guard.mem_available();disk=shutil.disk_usage(p.ROOT).free
                peak=max(peak,rss);minmem=min(minmem,mem);mindisk=min(mindisk,disk)
                resources.write(json.dumps(dict(utc=utc(),rss_bytes=rss,MemAvailable=mem,disk_free=disk,processes=owned))+'\n')
                low_since=(low_since if low_since is not None else time.monotonic()) if mem<48*guard.GIB else None
                if rss>192*guard.GIB:stop='tree_RSS_above_192GiB'
                elif low_since is not None and time.monotonic()-low_since>=30:stop='MemAvailable_below_48GiB_30s'
                elif disk<30*guard.GIB:stop='disk_free_below_30GiB'
                if proc.poll() is not None or stop:break
                time.sleep(5)
    except BaseException as ex:stop=f'{type(ex).__name__}:{ex}'
    finally:
        natural=proc is not None and proc.poll() is not None
        owned_before=guard.owned_processes(guard.process_table(),proc.pid,tracked) if proc else {}
        cleanup=bool(proc and (stop or not natural or owned_before))
        if cleanup:
            stop=stop or 'unexpected_owned_process_after_native_exit'
            native,before,remain=guard.terminate_and_reap(proc,tracked)
        else:native,before,remain=(proc.wait(),[],[]) if proc else (None,[],[])
        while remain:
            save(at/'cleanup_pending.json',dict(utc=utc(),owned_survivors=remain,lane_lock_held=True))
            native,before,remain=guard.terminate_and_reap(proc,tracked)
        rc=native if stop is None and native is not None else 125
        integrity=None
        try:
            for r in json.loads((archive/'baseline.json').read_text())['identities']:assert p.ident(r['path'])==r
            for r in json.loads((archive/'baseline.json').read_text())['production_inputs']:assert p.ident(r['path'])==r
            for r in bindings['archive']:assert p.ident(r['path'])==r
        except Exception as ex:integrity=str(ex);rc=rc or 1
        status=dict(**meta,ended_utc=utc(),execution_state='completed' if rc==0 else 'failed',native_exit_code=native,exit_code=rc,stop_reason=stop,native_natural_terminal_observed=natural,cleanup_was_required=cleanup,owned_before_cleanup=owned_before,owned_survivors=remain,tracked_identities=tracked,max_tree_rss_bytes=peak,minimum_mem_available_bytes=minmem,minimum_disk_free_bytes=mindisk,post_integrity_error=integrity,physical_commands_executed=False,checkpoint_write_executed=False)
        save(at/'status.json',status);fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        print(json.dumps(dict(terminal=True,native_exit_code=native,exit_code=rc,stop_reason=stop)),flush=True)
    return rc
if __name__=='__main__':raise SystemExit(main())
