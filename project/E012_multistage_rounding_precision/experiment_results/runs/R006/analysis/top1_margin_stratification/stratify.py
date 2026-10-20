"""CPU-only census of frozen R006 reference-logit margins and top1 flips."""
from pathlib import Path
import bisect,csv,hashlib,json,math,os,time
import numpy as np
HERE=Path(__file__).resolve().parent;RUN=HERE.parents[1]
EDGES=[0,.01,.05,.1,.2,.5,1,2,float('inf')]
LABELS=['[0,0.01)','[0.01,0.05)','[0.05,0.1)','[0.1,0.2)','[0.2,0.5)','[0.5,1)','[1,2)','[2,∞)']
def identity(p):
 p=Path(p).resolve();h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(8<<20),b''):h.update(x)
 return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def savecsv(name,rows,fields=None):
 with (HERE/name).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 started=time.monotonic();manifest_path=RUN/'session_S001/analysis_manifest.json';manifest=json.loads(manifest_path.read_text());protocol=json.loads((HERE/'protocol.json').read_text())
 assert protocol['boundaries']==[0,.01,.05,.1,.2,.5,1,2,'infinity']
 groups=manifest['ordered_groups'];assert len(groups)==64 and len({g['group_id'] for g in groups})==64 and len({g['attempt_path'] for g in groups})==64
 assert manifest['expected_documents']==manifest['completed_documents']==1024 and not manifest['missing_doc_ids'] and manifest['expected_doc_ids']==manifest['actual_doc_ids']
 sources=[identity(manifest_path),identity(HERE/'protocol.json')];positions=[];docchecks=[];docids=[];negative=[];nonfinite=[];ties=[];seen=set();alltv=True
 for g in groups:
  at=Path(g['attempt_path']);at.relative_to(RUN/'attempts');assert 'formal_tv_resident' in at.name
  receipt=identity(g['receipt']['path']);assert receipt['sha256']==g['receipt']['sha256'];sources.append(receipt)
  inputpath=at/'logit_metrics.jsonl';sources.append(identity(inputpath));workerpath=at/'paired_worker_manifest.json';sources.append(identity(workerpath));w=json.loads(workerpath.read_text());selected=w['selected_documents'];resultpath=at/'paired_result.json';sources.append(identity(resultpath));original=json.loads(resultpath.read_text());resultdocs={d['doc_id']:d for d in original['documents']}
  rows=[json.loads(s) for s in inputpath.read_text().splitlines()];assert [r['doc_id'] for r in rows]==[d['doc_id'] for d in selected] and len(rows)==16
  for row in rows:
   docid=row['doc_id'];assert docid not in seen;seen.add(docid);docids.append(docid);n=row['tokens'];pt=row['per_token'];fields=['reference_top1_margin','top1_matches','current_top1_ids','reference_top1_ids','current_top1_tie_counts','reference_top1_tie_counts','max_abs_logit_delta','margin_certified']
   assert all(len(pt[f])==n for f in fields) and row['top1_total_count']==n and row['nonfinite']==row['missing_positions']==0 and row['split']=='eval' and row['evidence_role']=='formal_eval'
   matches=[a==b for a,b in zip(pt['current_top1_ids'],pt['reference_top1_ids'])];assert matches==pt['top1_matches'];mcount=sum(matches);assert mcount==row['top1_match_count']==resultdocs[docid]['top1_match_count'] and n==resultdocs[docid]['tokens']==resultdocs[docid]['top1_total_count']
   assert sum(t>1 for t in pt['reference_top1_tie_counts'])==row['reference_tied_positions'] and sum(t>1 for t in pt['current_top1_tie_counts'])==row['current_tied_positions']
   tv=row.get('softmax_tv');tv_values=tv.get('tv') if isinstance(tv,dict) else None
   if tv_values is not None:assert len(tv_values)==n and tv['tokens']==n and tv['temperature']==1.0 and tv['complete'] and tv['nonfinite']==tv['missing_positions']==0
   else:alltv=False
   certified=0
   for j in range(n):
    margin=pt['reference_top1_margin'][j];assert type(margin) in [float,int];valid=math.isfinite(margin) and margin>=0;idx=bisect.bisect_right(EDGES,margin)-1 if valid else None
    flip=not matches[j];current_id=pt['current_top1_ids'][j];reference_id=pt['reference_top1_ids'][j];assert 0<=current_id<row['vocab_size'] and 0<=reference_id<row['vocab_size'];assert pt['current_top1_tie_counts'][j]>=1 and pt['reference_top1_tie_counts'][j]>=1
    record=dict(group_id=g['group_id'],document_order=len(docids)-1,doc_id=docid,domain=row['domain'],position=j,reference_top1_margin=margin,margin_bucket=LABELS[idx] if idx is not None else 'invalid',top1_flip=int(flip),current_top1_id=current_id,reference_top1_id=reference_id,current_top1_tie_count=pt['current_top1_tie_counts'][j],reference_top1_tie_count=pt['reference_top1_tie_counts'][j],max_abs_logit_delta=pt['max_abs_logit_delta'][j],margin_certified=int(pt['margin_certified'][j]),softmax_tv=tv_values[j] if tv_values is not None else None,source_logit_metrics=str(inputpath))
    if tv_values is not None:assert math.isfinite(tv_values[j]) and 0<=tv_values[j]<=1
    if not math.isfinite(margin):nonfinite.append(record)
    elif margin<0:negative.append(record)
    elif margin==0:ties.append(record)
    if valid:
     assert (margin==0)==(pt['reference_top1_tie_counts'][j]>1),(docid,j,margin,pt['reference_top1_tie_counts'][j])
     cert=margin>2*pt['max_abs_logit_delta'][j];assert cert==pt['margin_certified'][j];assert not (cert and flip);certified+=cert
    positions.append(record)
   assert certified==row['margin_certified_count']
   docchecks.append(dict(group_id=g['group_id'],doc_id=docid,positions=n,top1_match_count=mcount,flip_count=n-mcount,original_document_counts_equal=True,top1_ids_and_matches_equal=True,margin_certificate_consistent=True,tv_key_alignment_valid=tv_values is not None))
 assert docids==manifest['expected_doc_ids'] and len(docids)==1024 and len(positions)==103700
 flips=[p for p in positions if p['top1_flip']];assert len(flips)==1053
 validation=dict(passed=not negative and not nonfinite,formal_groups=len(groups),documents=len(docids),positions=len(positions),flips=len(flips),original_document_top1_counts_checked=len(docchecks),negative_margin_count=len(negative),nonfinite_margin_count=len(nonfinite),zero_margin_ties_count=len(ties),zero_margin_flip_count=sum(p['top1_flip'] for p in ties),zero_margin_equals_reference_top1_ties=True,all_positions_TV_key_aligned=alltv,all_top1_ids_and_match_flags_agree=True,qualified_groups_only=True)
 write(HERE/'validation.json',validation)
 assert not negative and not nonfinite,validation
 bins=[];cumulative=0
 for label in LABELS:
  subset=[p for p in positions if p['margin_bucket']==label];n=len(subset);f=sum(p['top1_flip'] for p in subset);cumulative+=f
  bins.append(dict(margin_bucket=label,positions=n,flips=f,within_bucket_flip_rate_percent=100*f/n if n else None,share_of_all_flips_percent=100*f/1053,cumulative_flips=cumulative,cumulative_share_of_all_flips_percent=100*cumulative/1053))
 assert sum(b['positions'] for b in bins)==103700 and sum(b['flips'] for b in bins)==1053 and bins[-1]['cumulative_flips']==1053
 margins=np.asarray([p['reference_top1_margin'] for p in flips],dtype=np.float64);quantiles={str(q):float(np.quantile(margins,q)) for q in protocol['quantiles']};ranked=sorted(flips,key=lambda x:(-x['reference_top1_margin'],x['document_order'],x['position']));high=[x for x in ranked if x['reference_top1_margin']>=1]
 tied=dict(subset_of='[0,0.01), do not add again to grand total',margin=0,positions=len(ties),flips=sum(x['top1_flip'] for x in ties),within_subset_flip_rate_percent=100*sum(x['top1_flip'] for x in ties)/len(ties) if ties else None,share_of_all_flips_percent=100*sum(x['top1_flip'] for x in ties)/1053)
 summary=dict(schema='r006_reference_margin_stratification_v1',definition=protocol['margin'],scope=protocol['scope'],totals=dict(documents=1024,positions=103700,flips=1053,overall_flip_rate_percent=100*1053/103700),buckets=bins,zero_margin_tie_subset=tied,flip_margin_quantiles=quantiles,flip_margin_mean=float(margins.mean()),flip_margin_max=float(margins.max()),high_margin_rule=protocol['high_margin_flip_rule'],high_margin_flip_count=len(high),top20_highest_margin_flips=ranked[:20],validation=validation,no_model_or_GPU=True)
 savecsv('positions.csv',positions);savecsv('top1_flips.csv',flips);savecsv('high_margin_flips_ge1.csv',high,list(positions[0]));savecsv('highest_margin_flips_top20.csv',ranked[:20]);savecsv('buckets.csv',bins);savecsv('document_checks.csv',docchecks)
 write(HERE/'summary.json',summary);write(HERE/'source_manifest.json',dict(analysis_manifest=identity(manifest_path),script=identity(Path(__file__)),protocol=identity(HERE/'protocol.json'),sources=sources,input_consumption_rule='Only64 ordered_groups from official session manifest, each exact roster; no filesystem attempt discovery',position_alignment='Unique doc_id and0-based real prediction position within original per_token lists; TV joined on same row/position after length and temperature checks'))
 print(json.dumps(dict(validation=validation,buckets=bins,flip_margin_quantiles=quantiles,high_margin_count=len(high)),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
