"""One finite qualification supervisor, then automatic independent CPU postcheck."""
from pathlib import Path
import argparse,json,os,subprocess,sys
from run_numerical_fidelity import identity,timestamp,write_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--command-file',type=Path,required=True);a=p.parse_args();root=a.root;run=root/'project/E012_multistage_rounding_precision/experiment_results/runs/R006';ready=json.loads(a.command_file.read_text());source=json.loads(Path(ready['source_ready']['path']).read_text())
    if identity(ready['source_ready']['path'])!=ready['source_ready']:raise ValueError('source readiness identity changed')
    for item in source['source_identities']:
        if identity(item['path'])!=item:raise ValueError('qualification source changed')
    logs=run/'logs/two_group_cost_supervisor_v4';logs.mkdir(parents=True,exist_ok=True);started=timestamp()
    with (logs/'stdout.log').open('x') as stdout,(logs/'stderr.log').open('x') as stderr:gpu=subprocess.run(ready['argv'],cwd=ready['cwd'],stdout=stdout,stderr=stderr)
    post=None
    if gpu.returncode==0:
        environment=dict(os.environ,CUDA_VISIBLE_DEVICES='')
        command=[sys.executable,'-B',str(Path(__file__).with_name('finalize_tv_two_group_cost_v4.py')),'--root',str(root)]
        with (logs/'postcheck_stdout.log').open('x') as stdout,(logs/'postcheck_stderr.log').open('x') as stderr:post=subprocess.run(command,stdout=stdout,stderr=stderr,env=environment,timeout=90)
    write_json(run/'qualification/two_group_cost_driver_receipt_v4.json',dict(started_at=started,ended_at=timestamp(),gpu_supervisor_native_exit_code=gpu.returncode,postcheck_native_exit_code=None if post is None else post.returncode,driver=identity(__file__),command=identity(a.command_file),scope='One bounded originalB001+B00232doc cost qualification,oneassembly,two genuine16doc segments; no formal full1024 counted'))
    return gpu.returncode if gpu.returncode else (post.returncode if post else 1)

if __name__=='__main__':raise SystemExit(main())
