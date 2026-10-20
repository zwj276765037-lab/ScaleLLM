"""Apply exact reviewed working delta only after the sole diagnostic lane drained."""
from pathlib import Path
import argparse,datetime,fcntl,hashlib,json,shutil,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[5];HW=ROOT/'project/hardware'
def identity(p):
 p=Path(p).resolve();return dict(path=str(p),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--diagnostic-attempt',type=Path,required=True);ap.add_argument('--check-only',action='store_true');a=ap.parse_args()
 delivery=json.loads((HERE/'candidate_delivery.json').read_text())
 for row in delivery['working_sources']+delivery['v2_test_sources']+[delivery['cpu_receipt'],delivery['baseline_manifest']]:assert identity(row['path'])==row,'Candidate identity drift'
 old=json.loads(Path(delivery['baseline_manifest']['path']).read_text());manifest=HW/'vivado/constraints/m003_entry_manifest.json';assert identity(manifest)['sha256']==delivery['baseline_manifest']['sha256'],'Production manifest already changed'
 for row in old['sources']:assert identity(row['path'])==dict(path=row['path'],bytes=row['bytes'],sha256=row['sha256']),'Production input changed'
 cpu=json.loads(Path(delivery['cpu_receipt']['path']).read_text());assert cpu['passed'] is True
 status=a.diagnostic_attempt/'evidence/jobs/native_grouped_clock/status.json';s=json.loads(status.read_text());assert s['native_exit_code']==0 and s['stop_reason'] is None and not s['owned_survivors'],'Successful drained grouped diagnostic required'
 started=json.loads((status.parent/'started.json').read_text());report=Path(started['report']);q=json.loads((report/'grouped_clock_qualification.json').read_text());assert q['passed'] is True and q['endpoint_count']==80,'Actual exact80 source/membership qualification required'
 sys.path.insert(0,str(HW/'vivado/scripts'));import run_managed_eda as owned
 tracked={int(k):v for k,v in s['tracked_PID_start_identities'].items()};assert not owned.owned_processes(owned.process_table(),started['leader_pid'],tracked)
 lock=(HW/'vivado/.m002_eda.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  if a.check_only:print(json.dumps(dict(preflight=True,production_sources_after=len(delivery['planned_manifest']['sources']),new_EDA=False)));return 0
  archive=HERE/'application_evidence';archive.mkdir()
  preserved=[]
  for row in delivery['delta']+delivery['test_delta']:
   dest=Path(row['destination'])
   if dest.exists():
    prev=identity(dest);target=archive/(prev['sha256']+'_'+dest.name);shutil.copyfile(dest,target);preserved.append(dict(original=prev,preserved=identity(target)))
   assert identity(row['source'])['sha256']==row['sha256'];shutil.copyfile(row['source'],dest)
  preserved.append(dict(original=identity(manifest),preserved=identity(Path(delivery['baseline_manifest']['path']))))
  manifest.write_text(json.dumps(delivery['planned_manifest'],indent=2)+'\n')
  import m003_entry;m003_entry.check_sources()
  receipt=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),before_manifest=delivery['baseline_manifest'],after_manifest=identity(manifest),production_sources=len(delivery['planned_manifest']['sources']),preserved=preserved,delta=delivery['delta'],diagnostic_status=identity(status),diagnostic_qualification=identity(report/'grouped_clock_qualification.json'),G2_and_3RTL_unchanged=True,no_new_EDA=True,scope='Entry-only effective_memory v2 plus actual clock connectivity grouping and row emission; G4/physical still pending')
  (archive/'application_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
 finally:fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
 return 0
if __name__=='__main__':sys.exit(main())
