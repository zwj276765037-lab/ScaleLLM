#!/usr/bin/env python3
"""Offline timing membership audit; raw arguments were not separately captured."""
import argparse,collections,csv,datetime,hashlib,json,os,re,subprocess
from pathlib import Path

def rows(p):
 with p.open(newline='') as f:yield from csv.DictReader(f,delimiter='\t')
def identity(p):return dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def path_membership(block,scope):
 # All captured paths have registered C/CLK sources. Separate launch clock,
 # data path, and capture clock by the report table boundaries; additionally
 # reject launch C/CLK inferred from the source clock-to-Q arc.
 lines=block.splitlines()
 loc=next(i for i,line in enumerate(lines) if re.match(r'^\s*Location\s+Delay type',line))
 separators=[i for i,line in enumerate(lines) if i>loc and re.fullmatch(r'\s*-{10,}(?:\s+-{5,})?\s*',line)]
 assert len(separators)>=3,'unqualified timing resource table shape'
 data=lines[separators[1]+1:separators[2]]
 def parse(part):
  explicit=set();inferred=set();pending=None
  for line in part:
   arc=re.search(r'\((Prop_[^)]+)\)',line)
   if arc:
    pieces=arc.group(1).rsplit('_',2);pending=pieces[-2:] if len(pieces)==3 else None
   tokens=re.findall(r'(?<!\S)(scalellm_[^\s]+)',line);explicit.update(tokens)
   if pending and tokens:
    for token in tokens:
     owner,sep,pin=token.rpartition('/')
     if sep and pin==pending[1]:inferred.add(owner+'/'+pending[0])
    pending=None
  return explicit,inferred
 direct_all,arc_all=parse(lines);direct_data,arc_data=parse(data)
 source=re.search(r'^\s*Source:\s*(.*?)\s*$',block,re.M).group(1)
 destination=re.search(r'^\s*Destination:\s*(.*?)\s*$',block,re.M).group(1)
 assert destination in direct_data,'data-table boundaries did not include native Destination pin'
 direct_data.discard(source);arc_data.discard(source)
 return dict(explicit_scope_pins=sorted(scope&direct_data),scope_pins_reconstructed_from_primitive_arc=sorted(scope&arc_data),scope_pins_only_outside_data_path=sorted((scope&(direct_all|arc_all))-(direct_data|arc_data)),native_source=source,native_destination=destination,data_table_qualified=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--attempt',type=Path,required=True);at=ap.parse_args().attempt.resolve();out=at/'evidence/native'
 assert json.loads((at/'status.json').read_text())['exit_code']==0
 os.sched_setaffinity(0,set(range(8)));os.setpriority(os.PRIO_PROCESS,0,5)
 target=at/'timing_scope_offline_audit_v2.json';assert not target.exists()
 bytag=collections.defaultdict(list)
 for r in rows(out/'deep_selected.tsv'):
  for tag in r['tags'].split(','):bytag[tag].append(r['canonical'])
 expected_nets={tag:sorted(set(ns))[:16] for tag,ns in bytag.items()}
 # Execute only generated data declarations in CPU tclsh to recover the exact
 # saved timing_groups. No Vivado commands or DCP are invoked.
 fixture='source {'+str(out/'deep_targets.tcl')+'}\ndict for {tag ns} $timing_groups {foreach n $ns {puts [join [list $tag $n] "\\t"]}}\n'
 check=subprocess.run(['tclsh'],input=fixture,text=True,capture_output=True,check=True);assert not check.stderr
 actual_nets=collections.defaultdict(list)
 for line in check.stdout.splitlines():tag,net=line.split('\t');actual_nets[tag].append(net)
 assert dict(actual_nets)==expected_nets,'saved native timing_groups differs from exact deep tag selection'
 net_tags=collections.defaultdict(set)
 for tag,ns in expected_nets.items():
  for net in ns:net_tags[net].add(tag)
 pins={tag:set() for tag in expected_nets};qualifying_rows=collections.Counter()
 for r in rows(out/'candidate_endpoints.tsv'):
  if r['kind']!='LEAF_PIN' or r['DIRECTION']!='IN':continue
  for tag in net_tags.get(r['canonical'],()):
   qualifying_rows[tag]+=1;s=pins[tag];name=r['name']
   if name in s:continue
   if len(s)<16:s.add(name)
   elif name<max(s):s.remove(max(s));s.add(name)
 receipts=list(rows(out/'timing_receipts.tsv'));assert len(receipts)==2*len(expected_nets)
 results=[];header_values=set();all_membership=True
 for receipt in receipts:
  tag=receipt['group'];scope=pins[tag];assert len(scope)==int(receipt['endpoints'])
  report=Path(receipt['output_or_error']);text=report.read_text();assert receipt['native_code']=='0'
  header=next(line for line in text.splitlines() if line.startswith('| Command'))
  header_values.add(re.split(r' -delay_type ',header,1)[0]);paths=[]
  for block in re.split(r'(?=^Slack \()',text,flags=re.M)[1:]:
   membership=path_membership(block,scope)
   direct=membership['explicit_scope_pins'];inferred=membership['scope_pins_reconstructed_from_primitive_arc'];matched=bool(direct or inferred)
   all_membership=all_membership and matched
   def field(label):
    m=re.search(r'^\s*'+re.escape(label)+r':\s*(.*?)\s*$',block,re.M);return m.group(1) if m else None
   slack=re.match(r'Slack \(([^)]+)\)\s*:\s*([-+0-9.]+)ns',block)
   paths.append(dict(slack_ns=float(slack.group(2)) if slack else None,slack_verdict=slack.group(1) if slack else None,source=field('Source'),destination=field('Destination'),data_path_delay=field('Data Path Delay'),path_type=field('Path Type'),path_group=field('Path Group'),explicit_scope_pins=direct,scope_pins_reconstructed_from_primitive_arc=inferred,scope_membership_supported=matched,data_table_qualified=membership['data_table_qualified'],scope_pins_only_outside_data_path=membership['scope_pins_only_outside_data_path']))
  no_paths=not paths
  assert len(paths)<=2
  results.append(dict(group=tag,delay_type=receipt['delay_type'],report=identity(report),header=header,reconstructed_net_IDs=expected_nets[tag],reconstructed_group_IN_pin_scope=sorted(scope),qualifying_derived_leaf_IN_rows=qualifying_rows[tag],reported_path_count=len(paths),native_no_reported_paths=no_paths,paths=paths,scope_verdict='NO_REPORTED_PATHS' if no_paths else ('MEMBERSHIP_SUPPORTED' if all(p['scope_membership_supported'] for p in paths) else 'MEMBERSHIP_NOT_CLOSED')))
 summary=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='CPU-only saved timing_groups and native-derived endpoint membership reconstruction, no new EDA query',actual_generated_timing_groups_match_deep_ID_tags=True,data_path_only_membership=True,source_launch_C_CLK_excluded=True,group_IN_pin_cap=16,net_cap_per_tag=16,pin_scope_is_union_then_total_cap=True,reports=len(results),reports_with_paths=sum(bool(r['paths']) for r in results),reported_paths=sum(len(r['paths']) for r in results),reports_with_unmatched_paths=[dict(group=r['group'],delay_type=r['delay_type']) for r in results if r['scope_verdict']=='MEMBERSHIP_NOT_CLOSED'],reports_with_no_paths=[dict(group=r['group'],delay_type=r['delay_type']) for r in results if r['native_no_reported_paths']],all_reported_paths_have_scope_membership=all_membership,distinct_header_through_prefixes=sorted(header_values),limitations=['Actual native through-argument values were not separately dumped; this reconstructs archived Tcl algorithm and checks DATA-table resource/primitive arc membership, excluding launch clock C/CLK, command header, source/capture clock paths.', 'Header text is preserved as printed; matching body does not retroactively replace native header or prove full timing acceptance.', 'Candidate endpoint rows are native-derived aggregate output; raw audit v3 independently verified native classifications/deep ID-tag scope, not a second full native path query.', 'Representative query only; no full cut TNS or physical success claim.'],inputs=[identity(p) for p in [out/'timing_receipts.tsv',out/'deep_selected.tsv',out/'deep_targets.tcl',at/'independent_raw_attribution_audit_v3.json']],producer=identity(Path(__file__)),results=results,G1='PENDING_REVIEW')
 with target.open('x') as f:f.write(json.dumps(summary,indent=2)+'\n')
 print(json.dumps({k:v for k,v in summary.items() if k not in ['results','inputs','producer','limitations','distinct_header_through_prefixes']},indent=2))
if __name__=='__main__':main()
