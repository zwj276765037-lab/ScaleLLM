"""Pinned read-only grouped clock diagnostic. Execute only in the owned EDA lane."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,subprocess,sys

def identity(path):
 p=Path(path).resolve();h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--archive-source',type=Path,action='append',default=[]);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
 package=json.loads(a.package.read_text());assert package['schema']=='M003_grouped_clock_launch_v1'
 for row in package['sources']+package['unchanged_inputs']:assert identity(row['path'])==row,'Pinned input changed: '+row['path']
 assert {str(p.resolve()) for p in a.archive_source}=={r['path'] for r in package['sources']},'Supervisor source archive closure missing'
 cpu=json.loads(Path(package['cpu_receipt']['path']).read_text());assert identity(package['cpu_receipt']['path'])==package['cpu_receipt'] and cpu['passed'] is True
 root=Path(__file__).resolve().parents[5];sys.path.insert(0,str(root/'project/hardware/vivado/scripts'));import m003_entry
 source_check=m003_entry.check_sources();assert source_check['sources']
 raw=json.loads(Path(package['lineage']['path']).read_text());rows=[r for r in raw['run_records'] if r['run']=='scalellm_vcu118_f05_bd_core_0_synth_1'];assert len(rows)==1
 row=rows[0];assert identity(row['checkpoint']['path'])==row['checkpoint']==package['fresh_core'];assert identity(row['end']['path'])==row['end'];assert not (Path(row['checkpoint']['path']).parent/'.vivado.error.rst').exists()
 if a.check_only:print(json.dumps(dict(preflight=True,sources=len(package['sources']),production_sources=len(source_check['sources']),native_started=False)));return 0
 assert os.environ.get('HAP_M003_ACTIVE')=='1','Owned supervisor environment required'
 report=Path(os.environ['HAP_REPORT_DIR']);report.mkdir()
 binding=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),package=identity(a.package),fresh_core=package['fresh_core'],original_lineage=package['lineage'],source_closure=package['sources'],scope='Read-only exact80 direct CLK membership, one full group/leaf and canonical top/ports per actual group; no synthesis/apply/G4')
 (report/'grouped_clock_core_consumption_binding.json').write_text(json.dumps(binding,indent=2)+'\n')
 cmd=[package['vivado'],'-mode','batch','-notrace','-source',str(Path(__file__).with_name('read_grouped_clock.tcl')),'-log',str(report/'vivado.log'),'-journal',str(report/'vivado.jou'),'-tclargs',package['fresh_core']['path']]
 native=subprocess.run(cmd,cwd=report).returncode
 if native:return native
 return subprocess.run([sys.executable,str(Path(__file__).with_name('clock_group_evidence.py')),'--report',str(report)]).returncode
if __name__=='__main__':sys.exit(main())
