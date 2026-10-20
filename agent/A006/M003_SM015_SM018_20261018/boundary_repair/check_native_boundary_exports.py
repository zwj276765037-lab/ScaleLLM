"""Validate actual AT025 NAME vectors against same-call native segment counts."""
import argparse,base64,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'project/hardware/vivado/scripts'))
from m003_snapshot_decode import decode
CORE='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention';META=CORE+'/u_meta'
ANCHORS={'S':CORE+'/engine_soft_clear','L':CORE+'/input_load_start','R':META+'/rsp_fire','reset':CORE+'/core_rst_n','read_enable':META+'/rd_fire','write_enable':CORE+'/meta_wr_valid'}
def names(value):
 if not isinstance(value,str):raise ValueError('NAME vector is not raw Tcl list text')
 b=base64.b64encode(value.encode()).decode();script='set value [encoding convertfrom utf-8 [binary decode base64 {'+b+'}]]\nputs [llength $value]\nforeach name $value {puts [binary encode base64 -maxlen 0 [encoding convertto utf-8 $name]]}\n'
 p=subprocess.run(['tclsh'],input=script,text=True,capture_output=True)
 if p.returncode or p.stderr:raise ValueError('Invalid raw Tcl NAME list: '+p.stderr)
 lines=p.stdout.splitlines();n=int(lines[0]);result=[base64.b64decode(x).decode() for x in lines[1:]]
 if len(result)!=n:raise ValueError('Tcl NAME count decode mismatch')
 return result
def verify(raw,events):
 cs=raw['control_sources'];selected=[x for x in events if x.get('event')=='boundary_source_selected']
 if len(selected)!=6 or {x.get('tag') for x in selected}!=set(ANCHORS):raise ValueError('Exact six native source count events required')
 result=[]
 for event in selected:
  tag=event['tag'];ns=names(cs[tag]);anchor=ANCHORS[tag]
  if event.get('anchor')!=anchor or int(event['segment_count'])!=len(ns) or not ns or any(not n for n in ns) or len(ns)!=len(set(ns)) or anchor not in ns:raise ValueError('Actual exported NAME vector incomplete or misbound: '+tag)
  result.append(dict(tag=tag,actual_segment_count=int(event['segment_count']),exported_NAME_count=len(ns),anchor=anchor,sorted_NAME_sha256=hashlib.sha256('\n'.join(sorted(ns)).encode()).hexdigest()))
 decoded=decode(raw);clockevents=[x for x in events if x.get('event')=='boundary_clock_source']
 if len(clockevents)!=1:raise ValueError('Actual clock source event required')
 event=clockevents[0];anchor=CORE+'/core_clk'
 if event.get('anchor')!=anchor or event['endpoint']!=cs['clock_pin'] or event['group']!=cs['clock_group'] or anchor not in names(decoded['control_sources']['clock']):raise ValueError('Independent clock witness mismatch')
 group=next(g for g in raw['connection_groups'] if g['id']==cs['clock_group'])
 if cs['clock_pin'] not in group['leaf_drivers']+group['primary_ports']:raise ValueError('Clock endpoint is not actual exclusive source')
 for kind in ['segments','drivers','canonical','ports']:
  if raw['connection_api_counts'][kind]['calls']!=len(raw['connection_groups']):raise ValueError('Heavy clock query exceeds K groups: '+kind)
 return dict(passed=True,nonclock_sources=result,clock=dict(anchor=anchor,group=cs['clock_group'],actual_source_endpoint=cs['clock_pin'],aliases=len(group['nets'])),scope='Actual whole native snapshot exports equal native segment counts; independent source anchors and strict decoder/source exclusivity retained; no synthetic correction or production source mutation.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--report',type=Path,required=True);p.add_argument('--phase',default='synth');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 snapshot=a.report/f'm003_native_{a.phase}.json';trace=a.report/f'm003_connection_{a.phase}_trace.jsonl'
 raw=json.loads(snapshot.read_text());events=[json.loads(line) for line in trace.read_text().splitlines()];result=verify(raw,events)
 result['snapshot']=dict(path=str(snapshot),sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest());result['trace']=dict(path=str(trace),sha256=hashlib.sha256(trace.read_bytes()).hexdigest())
 with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps(result))
if __name__=='__main__':main()
