"""Offline independent audit of sealed main_004 evidence; never contacts hardware.
Run without Python -O; assertion checks are part of this audit.
"""
from pathlib import Path
from collections import Counter,defaultdict
from bisect import bisect_right,bisect_left
import json,math,statistics,hashlib,struct
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--base',type=Path,default=Path(__file__).resolve().parents[2])
parser.add_argument('--output',type=Path,default=None)
args=parser.parse_args()
B=args.base;M=B/'native/main_004'
meta=json.loads((M/'telemetry.json').read_text(encoding='utf-8-sig'));work=json.loads((M/'workload/workload.json').read_text());receipt=json.loads((M/'receipt.json').read_text(encoding='utf-8-sig'));windows=[json.loads(x) for x in (M/'workload/windows.jsonl').read_text().splitlines()]
F=10_000_000;G=4_200_000;R=['0x70','0x11','0x12','0x15','0x14','0x72','0x73'];HV={'0x70','0x72','0x73'}
assert meta['qpc_frequency']==F and meta['target_period_ms']==140 and meta['read_errors']==0 and meta['status']=='COMPLETE' and meta['pass']
assert receipt['state']=='FAIL' and receipt['workload_exit_code']==0 and receipt['sampler_exit_code'] is None and receipt['lease_released'] and not receipt['survivors']
assert work['status']=='COMPLETE_WITH_LIMITS' and work['completed_windows']==12 and len(windows)==12 and Counter(w['kind'] for w in windows)==dict.fromkeys(['idle','attention_repeat','mlp_repeat','full_kv128_step'],3)
assert all(w['status']=='COMPLETE' and w['qpc_frequency']==F and w['run_id']==meta['run_id'] for w in windows)
assert all(a['end_ticks']<b['start_ticks'] for a,b in zip(windows,windows[1:]))
series={r:[] for r in R};pointinfo={r:[] for r in R};pout={r:[] for r in HV};types=Counter();reads={};lastread=0;lastend=0;modes={};pc=0;sc=0;negative=Counter();badvi=0;sweepdur=[];sweept=[];late=0
cmds={'VOUT_MODE':(32,1),'IOUT_CAL_GAIN':(56,2),'IOUT_CAL_OFFSET':(57,2),'READ_VOUT':(139,2),'READ_IOUT':(140,2),'READ_POUT':(150,2)}
def near(a,b):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12),(a,b)
def lin(w):
 e=w>>11;m=w&2047;e=e-32 if e&16 else e;m=m-2048 if m&1024 else m;return m*2.0**e,e
for line in (M/'telemetry.jsonl').open(encoding='utf-8-sig'):
 x=json.loads(line);typ=x['record'];types[typ]+=1
 if typ=='bus_read':
  assert x['read_id']==lastread+1;lastread=x['read_id'];r=x['address'];assert r in R
  code,n=cmds[x['command']];assert x['command_code']==code and x['expected_bytes']==x['byte_count']==n
  b=bytes.fromhex(x['raw_hex']);assert len(b)==n and int.from_bytes(b,'little')==x['word_le']
  assert x['api_status']=='returned' and x['error'] is None and x['fresh_hardware_read'] and x['native_ack_status']=='NOT_EXPOSED_BY_OFFICIAL_API'
  assert x['qpc_frequency']==F and x['run_id']==meta['run_id'] and lastend<=x['before_ticks']<x['after_ticks'];lastend=x['after_ticks'];reads[lastread]=x
  if x['command']=='VOUT_MODE':modes[r]=x['word_le'];assert modes[r]==(32 if r in HV else 20)
 elif typ in ['configuration','calibration']:pass
 elif typ=='rail_point':
  r=x['address'];assert x['sweep']==pc//7 and x['position']==pc%7 and r==R[(x['sweep']+x['position'])%7];pc+=1
  assert x['mode_word']==modes[r] and x['run_id']==meta['run_id']
  for key in ['read_vout','read_iout','read_pout']:
   z=x[key]
   if z is None:assert key=='read_pout' and r not in HV;continue
   assert reads.pop(z['read_id'])==z and x[key+'_id']==z['read_id']
  vcode=x['read_vout']['word_le'];icode=x['read_iout']['word_le'];i,e=lin(icode)
  if r in HV:
   assert 1<=vcode<=255 and e==-1 and x['current_exponent']==-1;v=.25+(vcode-1)/200;p,pe=lin(x['read_pout']['word_le']);assert pe==1 and x['pout_exponent']==1;near(p,x['pout_w']);z=x['read_pout'];pout[r].append(((z['before_ticks']+z['after_ticks'])/2,p))
  else:
   v=vcode/4096;assert x['read_pout'] is None and x['pout_w'] is None and x['pout_status']=='NOT_SUPPORTED_BY_DOCUMENTED_COMMAND_SET'
  near(v,x['voltage_v']);near(i,x['current_a']);near(v*i,x['vi_w']);assert x['physical_aperture_contained_busy'] is None
  a=x['vi_before_ticks'];b=x['vi_after_ticks'];assert a==x['read_vout']['before_ticks'] and b==x['read_iout']['after_ticks'];assert x['read_vout']['after_ticks']<=x['read_iout']['before_ticks'];assert a<b
  val=v*i if b-a<=G else None;badvi+=val is None;series[r].append(((a+b)/2,val));pointinfo[r].append((a,b,v*i,x['name'],x['point_after_ticks']))
  if i<0:negative[r]+=1
 elif typ=='sweep':
  assert x['sweep']==sc and pc==7*(sc+1) and x['complete_rail_points']==7 and x['rail_order']==R[sc%7:]+R[:sc%7];sc+=1;sweepdur.append((x['end_ticks']-x['start_ticks'])/F);sweept.append(x['start_ticks']);late+=x['late_ticks']>20000
 else:raise AssertionError(typ)
assert pc==70812==meta['complete_rail_points'] and sc==10116==meta['complete_sweeps'] and lastread==171993 and late==meta['missed_deadlines']==5069
assert len(reads)==21
for r,points in series.items():assert all(a[0]<b[0] for a,b in zip(points,points[1:]))
for conf in meta['configuration']:
 for q in [conf['read'],*conf['calibration']]:assert reads.pop(q['read_id'])==q
assert not reads
traces=[]
for line in (M/'commands.jsonl').open():
 c=json.loads(line)
 if c['record']=='clock':assert c['qpc_frequency']==F and c['run_id']==meta['run_id'];continue
 traces.append(c)
summaries=[json.loads(x) for x in (M/'workload/commands_summary.jsonl').read_text().splitlines()];assert len(traces)==len(summaries)==9129
unseen=[];previousack=0;signature={};groups=[[] for _ in windows];outside=0
for j,(c,s) in enumerate(zip(traces,summaries)):
 d=c['descriptor'];w=c['descriptor_words'];cid=d['command_id'];assert cid==8286+j and s['command_id']==cid and w[2]==w[7]==cid
 assert w[3]==127 and w[4]==d['opcode'] and w[5]==d['layer'] and w[6]==65535 and w[32:]==[127,1]*16 and d['active_mask']==65535
 assert hashlib.sha256(struct.pack('<64I',*w)).hexdigest()==c['descriptor_sha256']==s['descriptor_sha256']
 assert c['trace_state']=='ACK_WRITTEN' and c['first_error_status'] is None and c['core_hz']==80000000
 cyc=c['done_cycles_read']['value'];assert 0<cyc<0xffffffff and cyc==s['cycles'];out=196608 if d['opcode']==1 else 917504
 cv={z['register']:z['value'] for z in c['completion_reads']};assert cv==dict(ADMISSION_ERROR=0,DONE_ERROR=0,DONE_INPUT_BYTES=196608,DONE_OUTPUT_BYTES=out)
 assert c['input_transfer']['bytes']==196608 and c['output_transfer']['bytes']==s['output_bytes']==out
 obs=c['status_observations'];busy=[z for z in obs if z['value']==1];done=[z for z in obs if z['value']==2];assert done and c['status_reads']==len(obs) and c['busy_reads']==len(busy)
 assert c['first_busy']==(busy[0] if busy else None) and c['last_busy']==(busy[-1] if busy else None) and c['first_done']==done[0]
 assert all(z['before_ticks']<z['after_ticks'] for z in obs) and all(a['after_ticks']<=b['before_ticks'] for a,b in zip(obs,obs[1:]))
 assert previousack<c['start_write']['before_ticks']<c['start_write']['after_ticks']<=obs[0]['before_ticks']<done[0]['after_ticks']<=c['ack_write']['before_ticks']<c['ack_write']['after_ticks'];previousack=c['ack_write']['after_ticks']
 if not busy:unseen.append(cid)
 key=(d['opcode'],d['layer']);sig=(s['input_sha256'],s['output_sha256']);assert key not in signature or signature[key]==sig;signature[key]=sig
 found=False
 for k,window in enumerate(windows):
  if window['start_ticks']<=c['start_write']['before_ticks'] and c['ack_write']['after_ticks']<=window['end_ticks']:groups[k].append(c);found=True;break
 if not found:outside+=1
assert unseen==[14365] and outside==74
assert [(c['descriptor']['layer'],c['descriptor']['opcode']) for c in traces[:64]]==[(l,o) for l in range(32) for o in [1,2]]
q=work['qualification'];assert q['completed_commands']==64 and q['all_32_layer_receipts'] and q['token_match'] and q['six_target_inputs_outputs_byteexact'] and q['kv_snapshot_restored_and_preserved']
T={r:[x[0] for x in series[r]] for r in R}
BT={r:[x[0] for x in pointinfo[r]] for r in R}
def integrate(a,b):
 cuts={a,b}
 for r in R:cuts.update(T[r][bisect_right(T[r],a):bisect_left(T[r],b)])
 cuts=sorted(cuts);cover=0;ener={r:0.0 for r in R};zoh={r:0.0 for r in R};missing=[]
 for left,right in zip(cuts,cuts[1:]):
  mid=(left+right)/2;segs={}
  for r in R:
   idx=bisect_right(T[r],mid)-1
   if not(0<=idx<len(series[r])-1):break
   x,y=series[r][idx:idx+2]
   if y[0]-x[0]>G or x[1] is None or y[1] is None:break
   segs[r]=(x,y)
  if len(segs)!=7:
   if missing and missing[-1][1]==left:missing[-1][1]=right
   else:missing.append([left,right])
   continue
  cover+=right-left;seconds=(right-left)/F
  for r,(x,y) in segs.items():
   slope=(y[1]-x[1])/(y[0]-x[0]);pl=x[1]+slope*(left-x[0]);pr=x[1]+slope*(right-x[0]);ener[r]+=(pl+pr)*.5*seconds;zoh[r]+=x[1]*seconds
 duration=cover/F
 return dict(coverage=cover/(b-a),covered_seconds=duration,missing_seconds=(b-a-cover)/F,missing_intervals=missing,rail_means={r:ener[r]/duration for r in R},total_mean=sum(ener.values())/duration,zoh_mean=sum(zoh.values())/duration,full_mean=sum(ener.values())/duration if b-a-cover<=2 else None)
results=[]
for window,cs in zip(windows,groups):
 a=window['start_ticks'];b=window['end_ticks'];kind=window['kind'];assert len(cs)==window['completed_commands'];shape=[(c['descriptor']['layer'],c['descriptor']['opcode']) for c in cs]
 if kind=='idle':assert not cs and (b-a)/F>=120
 elif kind=='attention_repeat':assert shape==[(l,1) for _ in range(len(cs)//5) for l in [0,8,16,24,31]] and len(cs)%5==0 and (b-a)/F>=120
 elif kind=='mlp_repeat':assert shape==[(0,2)]*len(cs) and (b-a)/F>=120
 else:
  assert shape==[(l,o) for l in range(32) for o in [1,2]] and window['emitted']==q['emitted'] and window['token_match'] and window['six_target_inputs_outputs_byteexact'] and window['kv_snapshot_restored_and_preserved']
 counts={r:sum(a<=x[0] and x[1]<=b for x in pointinfo[r]) for r in R}
 
 vipcounts={r:sum(a<=x[0] and x[4]<=b for x in pointinfo[r]) for r in R}
 assert all(vipcounts[r]==window['rail_vi_points'][pointinfo[r][0][3]] for r in R) and min(vipcounts.values())>=200
 result=dict(kind=kind,repeat=window['repeat_id'],duration=(b-a)/F,commands=len(cs),min_rail_points=min(counts.values()),cycles=sum(c['done_cycles_read']['value'] for c in cs),busy_unobserved=[c['descriptor']['command_id'] for c in cs if c['first_busy'] is None])
 result.update(integrate(a,b))
 busysec=0;ccount={r:0 for r in R};unavailable=[]
 for c in cs:
  busy=[o for o in c['status_observations'] if o['value']==1]
  if len(busy)<2:
   unavailable.append(c['descriptor']['command_id']);continue
  ba=busy[0]['after_ticks']+2;bb=busy[-1]['before_ticks']-2
  assert bb>ba;busysec+=(bb-ba)/F
  for r in R:
   idx=bisect_left(BT[r],ba)
   while idx<len(pointinfo[r]) and pointinfo[r][idx][0]<=bb:
    if pointinfo[r][idx][1]<=bb:ccount[r]+=1
    idx+=1
 result['busy_inner_seconds']=busysec;result['busy_inner_unavailable']=unavailable;result['conditional_vi_counts']=ccount;result['vi_envelope_counts']=counts;result['vip_envelope_counts']=vipcounts
 results.append(result)
summary={}
for kind in ['idle','attention_repeat','mlp_repeat','full_kv128_step']:
 vals=[r['total_mean'] for r in results if r['kind']==kind];summary[kind]=dict(n=3,mean=statistics.mean(vals),sd=statistics.stdev(vals),min=min(vals),max=max(vals))
out=dict(status='INDEPENDENT_RAW_AND_COMMON_COVERAGE_RECOMPUTE_COMPLETE',raw_types=dict(types),invalid_long_vi=badvi,negative_current_points=dict(negative),command_count=len(traces),outside_formal_commands=outside,busy_unobserved=unseen,raw_wrapper_state=receipt['state'],sampler_native_exit=receipt['sampler_exit_code'],windows=results,repeat_summary=summary,raw_sha256={str(p.relative_to(M)):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in [M/'telemetry.jsonl',M/'commands.jsonl',M/'workload/windows.jsonl',M/'workload/workload.json',M/'receipt.json']})
if args.output is not None:args.output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
