"""Pinned exact51 reset provenance diagnostic; only the existing owner supervisor runs it."""
from pathlib import Path
import argparse,json,hashlib,os,subprocess,sys,datetime
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM');HERE=Path(__file__).resolve().parent

def identity(p):
 p=Path(p);return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--archive-source',action='append',default=[]);p.add_argument('--check-only',action='store_true');a=p.parse_args();pkg=json.loads(a.package.read_text())
 for row in pkg['sources']+pkg['unchanged_inputs']:assert identity(row['path'])==row,'Pinned diagnostic source/input changed'
 assert set(a.archive_source)=={x['path'] for x in pkg['sources']}
 assert identity(pkg['fresh_core']['path'])==pkg['fresh_core']
 lineage=json.loads(Path(pkg['original_lineage']['path']).read_text());row=next(z for z in lineage['run_records'] if z['run']=='scalellm_vcu118_f05_bd_core_0_synth_1');assert row['checkpoint']==pkg['fresh_core'];assert identity(row['end']['path'])==row['end'];assert not (Path(row['checkpoint']['path']).parent/'.vivado.error.rst').exists()
 sys.path.insert(0,str(ROOT/'project/hardware/vivado/scripts'));import m003_entry;m003_entry.check_sources()
 if a.check_only:print(json.dumps(dict(passed=True,preflight=True,new_EDA=False,scope='exact51/bounded16nodes/64pins/depth4')));return 0
 assert os.environ.get('HAP_M003_ACTIVE')=='1'
 report=Path(os.environ['HAP_REPORT_DIR']);report.mkdir();(report/'diagnostic_input_binding.json').write_text(json.dumps(dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),package=identity(a.package),fresh_core=pkg['fresh_core'],AT025_source_archive=pkg['AT025_source_archive'],original_lineage=pkg['original_lineage'],scope='Fresh core original completed producer used by AT025, relative inst/ scope. Not fulltop revalidation; exact17+34 CLR and bounded actual combinational reset source facts only; no synthesis/apply/G4.'),indent=2)+'\n')
 cmd=[pkg['vivado'],'-mode','batch','-notrace','-source',str(HERE/'read_reset_provenance.tcl'),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou'),'-tclargs',pkg['fresh_core']['path']]
 code=subprocess.run(cmd,cwd=report).returncode
 if code:return code
 rows=[json.loads(line) for line in (report/'reset_provenance.jsonl').read_text().splitlines()];assert rows[-1]['kind']=='complete' and int(rows[-1]['endpoints'])==51
 (report/'diagnostic_complete.json').write_text(json.dumps(dict(execution='completed',native_exit=0,endpoints=51,new_synthesis=False,production_mutation=False,G4=False),indent=2)+'\n');return 0
if __name__=='__main__':sys.exit(main())
