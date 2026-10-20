from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys
report=Path(os.environ['HAP_REPORT_DIR']);report.mkdir()
raw=Path(sys.argv[2]);assert hashlib.sha256(raw.read_bytes()).hexdigest()=='2b43590a2e36204c6628780ba077e9e030f6e10d0f7e579430cce602d8b41e64'
x=json.loads(raw.read_text());rows=[r for r in x['run_records'] if r['run']=='scalellm_vcu118_f05_bd_core_0_synth_1'];assert len(rows)==1
row=rows[0];cp=Path(row['checkpoint']['path'])
def fid(p):return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
assert fid(cp)==row['checkpoint'] and fid(Path(row['end']['path']))==row['end'];assert not(cp.parent/'.vivado.error.rst').exists()
(report/'original_core_consumption_binding.json').write_text(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),raw_original_lineage=fid(raw),core_original_produced_checkpoint=row['checkpoint'],core_original_native_completion=row['end'],scope='Read-only same-version new core graph role names; no board-wide graph/constraint application/new synthesis'),indent=2)+'\n')
cmd=['/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado','-mode','batch','-notrace','-source',sys.argv[1],'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou'),'-tclargs',str(cp)]
sys.exit(subprocess.run(cmd,cwd=report).returncode)
