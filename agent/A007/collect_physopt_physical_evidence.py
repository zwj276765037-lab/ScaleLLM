from pathlib import Path
import hashlib,json,re,collections,datetime
R=Path('project/hardware/vivado/reports/m002_E003_R002_AT002_closed_place_POST_physopt')
A=Path('project/E003_m002_full_implementation/experiment_results/runs/R002/attempts/AT002_closed_place_POST_physopt')
OUT=Path('agent/A007/report_20261016_E003_physopt_physical_review_evidence.json')
def read(n):
 p=R/n;b=p.read_bytes();return b.decode().splitlines(),{'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def tables(lines,pred):
 out=[]
 for i,l in enumerate(lines):
  c=[x.strip() for x in l.strip('|').split('|')]
  if pred(c):out.append({'line':i+1,'cells':c})
 return out
out={'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'bounded physopt physical/PW/bus/top32 report review; full POST and actual current reset graph not yet assessed','identities':{}}
for n in ['pulse_width_physopt.rpt','bus_skew_physopt.rpt','utilization_slr_physopt.rpt','congestion_physopt.rpt','slr_crossing_physopt.rpt','paths_setup_physopt.rpt','paths_hold_physopt.rpt']:
 ls,identity=read(n);out['identities'][n]=identity
 if n.startswith('pulse'):out['pulse_width']={'lines':ls,'header_only':len(ls)==15}
 if n.startswith('bus'):
  rows=[];active=False
  for i,l in enumerate(ls):
   if i>19 and l=='2. Bus Skew Report Per Constraint':break
   m=re.fullmatch(r'\s*(Slow|Fast)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*',l)
   if m:rows.append({'line':i+1,'corner':m[1],'requirement_ns':float(m[2]),'actual_ns':float(m[3]),'slack_ns':float(m[4])})
  out['bus_skew']={'count':len(rows),'negative':sum(x['slack_ns']<0 for x in rows),'minimum':min(rows,key=lambda x:x['slack_ns']),'summary_rows':rows}
 if n.startswith('utilization_slr'):
  wanted=['SLR2 <-> SLR1','SLR1 <-> SLR0','Total SLLs Used','CLB','CLB LUTs','CLB Registers','Unique Control Sets']
  out['SLR_utilization']=tables(ls,lambda c:len(c)>1 and c[0] in wanted)
 if n.startswith('congestion'):
  rows=tables(ls,lambda c:len(c)==16 and c[0] in ['North','South','East','West'])
  oldls,oldid=read('congestion_place.rpt');out['identities']['congestion_place.rpt']=oldid
  old=tables(oldls,lambda c:len(c)==16 and c[0] in ['North','South','East','West'])
  diffs=[{'key':a['cells'][:3],'old':a,'new':b} for a,b in zip(old,rows) if a['cells']!=b['cells']]
  out['congestion']={'rows':rows,'row_count':len(rows),'level6_rows':[x for x in rows if x['cells'][2]=='6'],'place_rows_same':len(old)==len(rows) and not diffs,'changed_rows':diffs}
 if n.startswith('slr_crossing'):
  rows=tables(ls[114:151],lambda c:len(c)==6 and c[0].isdigit())
  for row in rows:row['line']+=114
  prior=json.loads(Path('agent/A007/report_20261015_E003_place_physical_bounded_review_evidence.json').read_text())['SLR_fanout']
  expected={x['net']:x for x in prior['exact_overlaps']}
  overlaps=[]
  for row in rows:
   c=row['cells']
   if c[-1] in expected:
    old=expected[c[-1]];overlaps.append({'current':row,'previous':old,'same':int(c[0])==old['fanout'] and c[1]==old['driver_type'] and c[2:5]==[old[k] for k in ['SLR0','SLR1','SLR2']]})
  out['SLR_fanout']={'rows':rows,'count':len(rows),'skipped_BUFG_exact_overlaps':overlaps,'logic_level_section_header_only':not any(l.startswith('|') and not l.startswith('| Clock') for l in ls[100:105])}
 if n.startswith('paths_'):
  paths=[];starts=[i for i,l in enumerate(ls) if l.startswith('Slack (')]+[len(ls)]
  for a,b in zip(starts,starts[1:]):
   block=ls[a:b];record={'line':a+1,'slack':float(re.search(r':\s*([-\d.]+)ns',block[0])[1]),'header':[],'estimated_net_max':None,'slr_crossings':[]};nets=[]
   for k,l in enumerate(block):
    if k<26 and re.match(r'\s*(Source:|Destination:|Path Group:|Path Type:|Requirement:|Data Path Delay:|Logic Levels:|Clock Path Skew:|Inter-SLR Compensation:|Timing Exception:)',l):record['header'].append({'line':a+k+1,'text':l.strip()})
    if 'SLR Crossing[' in l:record['slr_crossings'].append({'line':a+k+1,'text':l.strip()})
    m=re.search(r'net \(fo=(\d+), estimated\)\s+([-\d.]+)\s+([-\d.]+)\s+(.*)',l)
    if m:nets.append({'line':a+k+1,'fanout':int(m[1]),'increment_ns':float(m[2]),'path_ns':float(m[3]),'net':m[4]})
   if nets:record['estimated_net_max']=max(nets,key=lambda x:x['increment_ns'])
   for key,pattern in [('source',r'\s*Source:\s+(.*)'),('destination',r'\s*Destination:\s+(.*)'),('path_group',r'\s*Path Group:\s+(.*)'),('logic_levels',r'\s*Logic Levels:\s+(\d+)')]:
    values=[m[1] for l in block if (m:=re.match(pattern,l))];record[key]=values[0] if values else None
   for l in block:
    m=re.match(r'\s*Data Path Delay:\s+([-\d.]+)ns\s+\(logic ([-\d.]+)ns \(([-\d.]+)%\)\s+route ([-\d.]+)ns \(([-\d.]+)%\)',l)
    if m:record['data_ns'],record['logic_ns'],record['logic_pct'],record['route_ns'],record['route_pct']=map(float,m.groups())
   paths.append(record)
  out[n]={'count':len(paths),'slack_range':[min(x['slack'] for x in paths),max(x['slack'] for x in paths)],'group_counts':dict(collections.Counter(x['path_group'] for x in paths)),'source_counts':dict(collections.Counter(x['source'] for x in paths)),'destinations':[x['destination'] for x in paths],'logic_level_counts':dict(collections.Counter(x['logic_levels'] for x in paths)),'route_pct_range':[min(x['route_pct'] for x in paths),max(x['route_pct'] for x in paths)],'paths':paths}
facts=json.loads((A/'physopt_physical_reports_facts.json').read_text());out['engineering_identity_checks']={n:out['identities'][n]['sha256']==v['sha256'] and out['identities'][n]['bytes']==v['bytes'] for n,v in facts['reports'].items() if n in out['identities']}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'output':str(OUT),'identities':out['identities'],'bus':{k:v for k,v in out['bus_skew'].items() if k!='summary_rows'},'congestion':{'rows':out['congestion']['row_count'],'same_as_place':out['congestion']['place_rows_same'],'changes':len(out['congestion']['changed_rows'])},'slr':{'count':out['SLR_fanout']['count'],'overlap_same':[x['same'] for x in out['SLR_fanout']['skipped_BUFG_exact_overlaps']]},'top32':{n:{k:v for k,v in out[n].items() if k not in ['paths','destinations']} for n in ['paths_setup_physopt.rpt','paths_hold_physopt.rpt']},'engineering_identity_checks':out['engineering_identity_checks']},ensure_ascii=False,indent=2))
