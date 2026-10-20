import os
for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
import json,hashlib,math,sys,time
from pathlib import Path
from fractions import Fraction as F
from collections import Counter,defaultdict
import numpy as np
BASE=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical')
checks=Counter();details={};begin=time.monotonic()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]
def require(ok,msg):
 if not ok:raise AssertionError(msg)
 checks['assertions']+=1
def sat(x,w):return min(max(x,-(1<<(w-1))),(1<<(w-1))-1)
def away(x):
 x=F(x);m=abs(x);v=(2*m.numerator+m.denominator)//(2*m.denominator)
 return -v if x<0 else v
def powfrac(n,k):return F(int(n),1<<k) if k>=0 else F(int(n)*(1<<(-k)))
def metrics(c,r):
 c=c.astype(np.float64).ravel();r=r.astype(np.float64).ravel();d=c-r
 e=math.fsum((d*d).tolist());s=math.fsum((r*r).tolist());z=math.fsum(d.tolist());n=len(d)
 return dict(error_energy=e,signal_energy=s,signed_error_sum=z,relative_l2_percent=100*math.sqrt(e/s) if s else None,normalized_signed_bias_percent=100*z/math.sqrt(n*s) if n and s else None,absolute_rmse=math.sqrt(e/n) if n else None,absolute_max=float(np.max(abs(d))) if n else None,signal_rms=math.sqrt(s/n) if n else None)
def compare_metrics(a,b,label):
 for k,v in a.items():
  require((v is None and b.get(k) is None) or (v is not None and math.isclose(v,b[k],rel_tol=2e-11,abs_tol=1e-13)),label+' '+k)
def verify_identity(record):
 require(sha(record['path'])==record['sha256'],'file sha '+record['path']);checks['file_hashes']+=1
ready=load(BASE/'source_ready.json')
for rec in ready['code_identities']+ready['input_identities']:verify_identity(rec)
plan=load(ready['input_identities'][0]['path']);batch=next(b for b in plan['batches'] if b['batch_id']=='B001');stream=load(plan['input_stream_manifest']['path']);source_docs=[stream['documents'][i] for i in batch['source_indices']]
audit_id=batch['audit_doc_ids'][0];audit_index=batch['doc_ids'].index(audit_id)
result=load(BASE/'paired_result.json');require(result['execution_state']=='completed' and result['measured_documents']==16 and result['formal_eval_documents']==16,'scope')
hidden=rows(BASE/'tensor_metrics.jsonl');local=rows(BASE/'local_tensor_metrics.jsonl');dynamic=rows(BASE/'dynamic_metadata.jsonl')
docs=[r['doc_id'] for r in result['documents']];require(docs==batch['doc_ids'] and len(set(docs))==16,'distinct frozen docs')
for row in hidden+local:require(row['split']=='eval' and row['evidence_role']=='formal_eval','formal source role')
for doc in docs:
 h=[r for r in hidden if r['doc_id']==doc];l=[r for r in local if r['doc_id']==doc];d=[r for r in dynamic if r['doc_id']==doc]
 require(len(h)==32 and {r['layer'] for r in h}==set(range(32)),'32 hidden '+doc)
 require(len(l)==384 and all(sum(r['layer']==i for r in l)==12 for i in range(32)),'384 local '+doc)
 require(len({(r['layer'],r['node'],r['op']) for r in l})==384,'local unique '+doc)
 require(len(d)==384,'dynamic384 '+doc)
 for arm in ['current','reference']:
  armr=[r for r in d if r['arm']==arm]
  require(len(armr)==192 and len({(r['layer'],r['function'],r['ordinal']) for r in armr})==192,'dynamic unique '+doc+arm)
  require(all(sum(r['layer']==i and r['function']=='prepare_fixed_activation' for r in armr)==4 for i in range(32)),'four act perlayer')
  require(all(sum(r['layer']==i and r['function']=='_kv12_quantize' for r in armr)==2 for i in range(32)),'two KV perlayer')
 for r in l:
  m=r['metrics']['current_vs_reference'];e=m['error_energy'];s=m['signal_energy'];n=m['valid_elements'];z=m['signed_error_sum']
  require(math.isclose(m['relative_l2_percent'],100*math.sqrt(e/s),rel_tol=1e-12,abs_tol=1e-14) if s else m['relative_l2_percent'] is None,'local formula')
  require(not r['strict_valid_available'] and not r['exact_pre_output_comparison'],'local qualification')
summary=[]
for r in hidden:
 if r['output_artifact']:
  verify_identity(r['output_artifact'])
  with np.load(r['output_artifact']['path'],allow_pickle=False) as a:
   got=metrics(a['current'],a['reference']);compare_metrics(got,r['metrics']['current_vs_reference'],'hidden')
  summary.append(dict(layer=r['layer'],**got));checks['independent_hidden_tensors']+=1
require(len(summary)==32,'raw hidden32')
for i,doc in enumerate(docs):
 p=BASE/'documents'/f'doc{i:04d}';inp=load(p/'input_identity.json')
 require(inp['tokens']==batch['actual_token_lengths'][i] and len(inp['input_ids'][0])==inp['tokens'] and all(inp['attention_mask'][0]),'tokens')
 original=source_docs[i]
 require(inp['retokenized'] is False and inp['token_artifact']==original['token_artifact'],'direct frozen token provenance')
 verify_identity(original['token_artifact'])
 with np.load(original['token_artifact']['path'],allow_pickle=False) as raw:
  require(np.array_equal(np.asarray(inp['input_ids'][0]),raw['input_ids']),'token identity')
  require(np.array_equal(np.asarray(inp['attention_mask'][0]),raw['attention_mask']),'token mask identity')
  require(np.array_equal(raw['position_ids'],np.arange(inp['tokens'])),'frozen positions identity')
 final=load(p/'final_norm_comparison.json')
 require(final['doc_id']==doc,'final doc')
 if i==audit_index:
  with np.load(p/'final_hidden_current.npz') as a,np.load(p/'final_hidden_reference.npz') as b:
   got=metrics(a['hidden'],b['hidden']);compare_metrics(got,final['metrics']['current_vs_reference'],'final');details['auditdoc_final']=got
 changes=Counter();totals=Counter();pair={}
 for r in dynamic:
  if r['doc_id']!=doc:continue
  key=(r['layer'],r['function'],r['ordinal']);pair.setdefault(key,{})[r['arm']]=r
 for key,ab in pair.items():
  require(set(ab)=={'current','reference'},'dynamic pair')
  if i==audit_index:
   loaded={}
   for arm,r in ab.items():
    require(r['artifact'] is not None,'audit dynamic artifact');verify_identity(r['artifact'])
    with np.load(r['artifact']['path'],allow_pickle=False) as payload:loaded[arm]={f:payload[f].copy() for f in payload.files}
    expected={f for f in r['identity'] if key[0] in {0,15,31} or not f.startswith('values_')}
    require(set(loaded[arm])==expected,'dynamic saved fields')
    for f,a in loaded[arm].items():require(hashlib.sha256(a.tobytes()).hexdigest()==r['identity'][f]['sha256'],'dynamic array sha')
   for f,a in loaded['current'].items():
    b=loaded['reference'][f];num=int(np.count_nonzero(a!=b));require(num==ab['reference']['changed_elements_vs_current'][f],'dynamic change count');changes[f]+=num;totals[f]+=a.size
  else:require(all(r['artifact'] is None for r in ab.values()),'unaudited no raw')
 if i==audit_index:details['independent_dynamic_saved_scope']=dict(changed=dict(changes),total=dict(totals))
 details.setdefault('final_norm_by_doc',[]).append(dict(doc_id=doc,tokens=inp['tokens'],**final['metrics']['current_vs_reference']))
 for arm in ['current','reference']:
  audit=load(p/f'audit_{arm}.json')
  if arm=='reference':require(audit['finite_guard_accumulator_audit']=='not_applicable_wider_arithmetic','reference guard NA')
 details.setdefault('audits',{})[doc]={arm:load(p/f'audit_{arm}.json')['counters'] for arm in ['current','reference']}
wm=load(BASE/'node_witnesses/manifest.json');require(wm['audit_doc_ids']==[audit_id] and not wm['selection_is_iid'] and not wm['error_based_selection'],'witness scope')
require(wm['max_doc_bytes']==64<<20 and wm['max_at_bytes']==96<<20,'witness budgets')
wc=Counter();bounds=Counter();max_pair=defaultdict(int)
dynamic_sources={(r['layer'],r['function'],r['ordinal']):r['artifact']['path'] for r in dynamic if r['doc_id']==audit_id and r['arm']=='current'}
for rec in wm['records']:
 node=rec['node'];wc[node+'_'+rec['status']]+=1
 require(rec['doc_id']==audit_id and rec['call_ordinal']==0,'witness coordinate')
 size=math.prod(rec['original_output_shape']);wanted=min(16,size);selected={0}
 if wanted>1:selected.add(size-1)
 prefix=json.dumps([0,[rec['doc_id'],rec['layer'],node,rec['op_name']],size],sort_keys=True,separators=(',',':'),allow_nan=False).encode();limit=(1<<256)-((1<<256)%size);j=0
 while len(selected)<wanted:
  v=int.from_bytes(hashlib.sha256(prefix+j.to_bytes(8,'big')).digest(),'big');j+=1
  if v<limit:selected.add(v%size)
 require(sorted(selected)==rec['planned_output_flat_indices'],'independent preselection')
 if rec['status']!='saved':require(rec['status']=='skipped' and rec['skip_reason']=='byte_budget','explicit skip');continue
 path=BASE/'node_witnesses'/rec['path'];require(sha(path)==rec['sha256'],'witness file hash')
 with np.load(path,allow_pickle=False) as p:a={k:p[k].copy() for k in p.files}
 for k,v in a.items():require(hashlib.sha256(v.tobytes()).hexdigest()==rec['arrays'][k]['sha256'],'witness array hash')
 if node=='linear':
  ordinal={'q_proj':0,'k_proj':0,'v_proj':0,'o_proj':1,'gate_proj':2,'up_proj':2,'down_proj':3}[rec['op_name']]
  with np.load(dynamic_sources[(rec['layer'],'prepare_fixed_activation',ordinal)],allow_pickle=False) as raw:
   select=np.asarray(rec['activation_rows'])
   for target,source in [('act_code','codes_u8'),('act_shift','shifts_u8'),('zero_point','zero_points_u8')]:require(np.array_equal(a[target],raw[source][select]),'witness dynamic source '+target)
   if 'values_u8' in raw.files:require(np.array_equal(a['q_a'],raw['values_u8'][select]),'witness actual activation values')
 elif node in ('qk','pv'):
  coords=np.unravel_index(a['_witness_unit_flat_indices'],rec['original_output_shape']);b,h,q,last=coords;ratio=rec['num_key_value_groups']
  with np.load(dynamic_sources[(rec['layer'],'_kv12_quantize',0 if node=='qk' else 1)],allow_pickle=False) as raw:
   if node=='qk':
    for target,source in [('kv_code','codes_u8'),('kv_shift','shifts_u8')]:require(np.array_equal(a[target],raw[source][b,last,h//ratio]),'QK KV source')
    if 'values_s12' in raw.files:require(np.array_equal(a['key_s12'],raw['values_s12'][b,last,h//ratio]),'QK key lanes source')
   else:
    k=np.arange(a['kv_code'].shape[1])[None,:];g=last//32;lane=last%32
    for target,source in [('kv_code','codes_u8'),('kv_shift','shifts_u8')]:require(np.array_equal(a[target],raw[source][b[:,None],k,(h//ratio)[:,None],g[:,None]]),'PV KV source')
    if 'values_s12' in raw.files:require(np.array_equal(a['value_s12'],raw['values_s12'][b[:,None],k,(h//ratio)[:,None],g[:,None],lane[:,None]]),'PV value lanes source')
 cc=[];rr=[];ex=[];valid=[];bs=[];bps=[]
 if node=='linear':
  spec={'attention':(42,42,24,26,47),'mlp_gate_up':(37,44,24,20,44),'mlp_down':(45,54,32,12,44)}[rec['config']['profile']];gw,aw,ow,lo,hi=spec
  dot=np.sum((a['q_a'].astype(np.int64)-a['zero_point'][...,None])*a['q_w'].astype(np.int64),axis=-1)
  require(np.array_equal(dot,a['dot']),'independent Linear lane dot');checks['linear_groups']+=dot.size
  for row in range(len(dot)):
   acc=0;exact=F(0);ok=True;g=0
   for v,ca,cw,sa,sw in zip(dot[row],a['act_code'][row],a['weight_code'][row],a['act_shift'][row],a['weight_shift'][row]):
    n=int(v)*int(ca)*int(cw);t=int(sa)+int(sw);active=ca!=0 and cw!=0
    exact+=powfrac(n,t-16);shift=t-24;aligned=(n>>max(shift,0))<<max(-shift,0)
    ok &= (not active or lo<=t<=hi) and -(1<<(gw-1))<=aligned<(1<<(gw-1));g+=int(active and shift>0)
    if active and not lo<=t<=hi:aligned=0
    nxt=acc+aligned;ok &= -(1<<(aw-1))<=nxt<(1<<(aw-1));acc=(nxt+(1<<(aw-1)))%(1<<aw)-(1<<(aw-1))
   c=away(F(acc,256));r=away(exact);valid.append(ok and c==sat(c,ow) and r==sat(r,ow));cc.append(sat(c,ow));rr.append(sat(r,ow));ex.append(exact);bs.append(F(g,256)+F(1,2));bps.append(F(g,256)+1)
 elif node=='rope':
  for (x,y),c,s in zip(a['raw_pair'],a['cos_q16'],a['sin_q16']):
   x,y,c,s=map(int,(x,y,c,s))
   for cur,exact in [(away(F(x*c,65536))-away(F(y*s,65536)),F(x*c-y*s,65536)),(away(F(x*s,65536))+away(F(y*c,65536)),F(x*s+y*c,65536))]:
    r=away(exact);cc.append(sat(cur,24));rr.append(sat(r,24));ex.append(exact);valid.append(cur==sat(cur,24) and r==sat(r,24));bs.append(F(1));bps.append(F(3,2))
 elif node=='qk':
  dot=np.sum(a['query_s24'].astype(np.int64)*a['key_s12'].astype(np.int64),axis=-1);require(np.array_equal(dot,a['dot']),'QK lanes')
  for ds,cs,ss in zip(dot,a['kv_code'],a['kv_shift']):
   terms=[powfrac(int(d)*int(c)*5793,int(s)+18) for d,c,s in zip(ds,cs,ss)];exact=sum(terms,F(0));limit=16<<14;exact=min(max(exact,-limit),limit);cur=min(max(sum(x.numerator//x.denominator for x in terms),-limit),limit)
   cc.append(cur);rr.append(exact.numerator//exact.denominator);ex.append(exact);valid.append(True);bs.append(F(4));bps.append(F(3))
 elif node=='pv':
  for ps,vs,cs,ss in zip(a['probability_u16'],a['value_s12'],a['kv_code'],a['kv_shift']):
   terms=[powfrac(int(p)*int(v)*int(c),int(s)) for p,v,c,s in zip(ps,vs,cs,ss)];exact=sum(terms,F(0));acc=sum((t*256).numerator//(t*256).denominator for t in terms);cur=away(F(acc,256));ref=away(exact);g=sum(int(c!=0 and s>8) for c,s in zip(cs,ss))
   cc.append(sat(cur,24));rr.append(sat(ref,24));ex.append(exact);valid.append(cur==sat(cur,24) and ref==sat(ref,24));bs.append(F(g,256)+F(1,2));bps.append(F(g,256)+1)
 elif node=='softmax':
  lut=list(map(int,a['lut_u17']))
  for score,mask in zip(a['score_q14'],a['valid_mask']):
   score=list(map(int,score));mask=list(map(bool,mask));K=len(score);mx=max((s for s,v in zip(score,mask) if v),default=-(1<<19));E=[];Ec=[]
   for s,v in zip(score,mask):
    mag=min(max(mx-s,0),16<<14);idx,fr=divmod(mag,1024);hi,lo=lut[idx],lut[min(idx+1,256)];E.append(F(hi*1024-(hi-lo)*fr,1024) if v else F(0));Ec.append(hi-((hi-lo)*fr+512)//1024 if v else 0)
   S=sum(E,F(0));Sc=sum(Ec);inv=((1<<32)+Sc//2)//Sc if Sc else 0
   for e,c,v in zip(E,Ec,mask):
    exact=65536*e/S if S else F(0);cur=min((c*inv+32768)//65536,65535);ref=min(away(exact),65535);cc.append(cur);rr.append(ref);ex.append(exact);valid.append(v);bs.append(F(K+5,2));bps.append(F(K+4,2))
 else:raise ValueError(node)
 require(np.array_equal(np.asarray(cc),a['_witness_current_code'].ravel()),node+' current independent integer mismatch')
 require(np.array_equal(np.asarray(rr),a['_witness_reference_code'].ravel()),node+' reference independent Fraction mismatch')
 for c,r,e,v,b,bp in zip(cc,rr,ex,valid,bs,bps):
  wc[node+'_scalars']+=1;max_pair[node]=max(max_pair[node],abs(c-r))
  if v:require(abs(F(c)-e)<=b and abs(c-r)<=bp,node+' proven bound');bounds[node+'_applicable']+=1
  else:bounds[node+'_excluded']+=1
require(len(wm['records'])==384 and len({(r['layer'],r['node'],r['op_name']) for r in wm['records']})==384,'witness coverage384')
checks['witness_files']=sum(r['status']=='saved' for r in wm['records'])
details.update(hidden_by_layer=summary,witness_counts=dict(wc),bound_counts=dict(bounds),witness_max_pair_code=dict(max_pair),checks=dict(checks),seconds=time.monotonic()-begin,independent_reference='Python integer/Fraction; no production, evaluated policy or metric functions imported',formal_eval_documents=16,full_target_documents=1024)
print(json.dumps(details,indent=2,allow_nan=False))
