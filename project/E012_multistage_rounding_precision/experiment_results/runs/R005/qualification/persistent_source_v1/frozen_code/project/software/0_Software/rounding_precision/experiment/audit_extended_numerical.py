"""Independent CPU audit of R005 extensions; no production numerical imports.

Raw logit rows validate complete-vocabulary statistics at predeclared positions.
Selected complete head dot products diagnose FP32 GEMM roundoff separately from
measured current/reference propagation. No fidelity pass threshold is inferred.
"""
from __future__ import annotations
import os
for _key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import struct
import time
import subprocess
import sys
import tempfile
import numpy as np


def require(condition,message):
    if not condition:raise AssertionError(message)


def read_json(path):return json.loads(Path(path).read_text())
def read_rows(path):
    with Path(path).open() as stream:return [json.loads(line) for line in stream if line.strip()]


def sha_file(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(8<<20):result.update(block)
    return result.hexdigest()


def array_identity(value):
    value=np.ascontiguousarray(value)
    return {'shape':list(value.shape),'dtype':str(value.dtype),'sha256':hashlib.sha256(value.tobytes()).hexdigest()}


def verify_file(record):
    require(sha_file(record['path'])==record['sha256'],'file identity '+record['path'])


def close(actual,expected,label):
    require(math.isfinite(float(actual)) and math.isfinite(float(expected)),label+' finite')
    require(math.isclose(float(actual),float(expected),rel_tol=2e-11,abs_tol=2e-12),label+' numerical formula')


def exact_dyadic_dot(a,b):
    """Integer summation of exact represented binary inputs, not a float reduction."""
    terms=[];bits=0
    for x,y in zip(a,b):
        xn,xd=float(x).as_integer_ratio();yn,yd=float(y).as_integer_ratio()
        exponent=(xd.bit_length()-1)+(yd.bit_length()-1)
        terms.append((xn*yn,exponent));bits=max(bits,exponent)
    return Fraction(sum(n<<(bits-k) for n,k in terms),1<<bits)


def head_source_rows(source,indices,cache):
    """Read just the real BF16 tensor region/rows from safetensors, without torch."""
    require(source['checkpoint_key']=='lm_head.weight' and source['source_dtype']=='torch.bfloat16','head key/dtype')
    require(source['bias'] is False and source['tied'] is False,'head bias/tied contract')
    verify_file(source['checkpoint_index']);verify_file(source['config'])
    path=Path(source['checkpoint_shard']);key=source['checkpoint_key'];index=read_json(source['checkpoint_index']['path'])
    require((Path(source['checkpoint_index']['path']).parent/index['weight_map'][key]).resolve()==path.resolve(),'head index maps shard')
    config=read_json(source['config']['path'])
    require(not config.get('tie_word_embeddings') and 'lm_head.bias' not in index['weight_map'],'source actual untied/bias-free')
    with path.open('rb') as stream:
        length=struct.unpack('<Q',stream.read(8))[0];require(length<=64<<20,'safetensors bounded header')
        header=json.loads(stream.read(length));tensor=header[key]
        require(tensor['dtype']=='BF16' and tensor['shape']==source['shape']==[config['vocab_size'],config['hidden_size']],'head tensor source geometry')
        low,high=tensor['data_offsets'];V,D=tensor['shape'];require(high-low==V*D*2,'BF16 tensor byte span')
        start=8+length+low;cache_key=(str(path.resolve()),start,high-low,source['consumed_tensor_sha256'])
        if cache_key not in cache:
            stream.seek(start);digest=hashlib.sha256();left=high-low
            while left:
                block=stream.read(min(left,8<<20));require(bool(block),'head body not truncated');digest.update(block);left-=len(block)
            require(digest.hexdigest()==source['consumed_tensor_sha256'],'all consumed BF16 head body hash')
            cache.add(cache_key)
        rows=[]
        for index in indices:
            require(0<=int(index)<V,'head row index');stream.seek(start+int(index)*D*2)
            raw=stream.read(D*2);require(len(raw)==D*2,'head selected row complete')
            rows.append((np.frombuffer(raw,dtype='<u2').astype(np.uint32)<<16).view(np.float32))
    return np.stack(rows)


def independent_logit_row(current,reference):
    current=np.asarray(current,dtype=np.float64);reference=np.asarray(reference,dtype=np.float64)
    require(current.ndim==1 and current.shape==reference.shape and current.size>=2,'logit row geometry')
    require(np.isfinite(current).all() and np.isfinite(reference).all(),'finite complete raw logits')
    delta=current-reference;absolute=np.abs(delta)
    top=[];ties=[];lse=[]
    for value in (current,reference):
        best=float(np.max(value));top.append(int(np.flatnonzero(value==best)[0]));ties.append(int(np.count_nonzero(value==best)))
        lse.append(best+math.log(math.fsum(np.exp(value-best).tolist())))
    reference_order=np.partition(reference,-2);margin=float(reference_order[-1]-reference_order[-2]);maxabs=float(np.max(absolute));logprob_delta=delta-(lse[0]-lse[1])
    return dict(max_abs_logit_delta=maxabs,max_abs_vocab_ids=int(np.flatnonzero(absolute==maxabs)[0]),
                delta_min=float(np.min(delta)),delta_max=float(np.max(delta)),mean_signed_delta=math.fsum(delta.tolist())/len(delta),
                logit_rmse=math.sqrt(math.fsum((delta*delta).tolist())/len(delta)),
                max_abs_logprob_delta=float(np.max(np.abs(logprob_delta))),logsumexp_current=lse[0],logsumexp_reference=lse[1],logsumexp_delta=lse[0]-lse[1],
                current_top1_ids=top[0],reference_top1_ids=top[1],current_top1_tie_counts=ties[0],reference_top1_tie_counts=ties[1],
                reference_top1_margin=margin,top1_matches=top[0]==top[1],margin_certified=margin>2*maxabs)


def audit_logit_record(record,doc_directory,head_cache):
    T,V,D=(record[k] for k in ('tokens','vocab_size','hidden_size'))
    require(1<=T<=128 and V>=2 and D>0,'R005 logit geometry')
    require(record['score_pairs']==T*V and record['nonfinite']==0 and record['missing_positions']==0,'all scores covered')
    require(record['tie_break']=='smallest vocabulary ID','tie contract')
    step=record['chunk_size'];require(step==4096,'primary head chunk frozen4096')
    require(record['vocab_chunks']==[[start,min(start+step,V)] for start in range(0,V,step)],'full contiguous vocabulary once')
    p=record['per_token'];require(all(len(values)==T for values in p.values()),'all token metric arrays length T')
    numerical=[key for key in p if key not in ('top1_matches','margin_certified')]
    require(all(math.isfinite(float(x)) for key in numerical for x in p[key]),'finite per-token metrics')
    match=[];cert=[]
    for t in range(T):
        require(all(0<=int(p[key][t])<V for key in ('max_abs_vocab_ids','current_top1_ids','reference_top1_ids')),'token vocab ID range')
        require(all(1<=int(p[key][t])<=V for key in ('current_top1_tie_counts','reference_top1_tie_counts')),'ties1..V')
        require(p['reference_top1_margin'][t]>=0 and p['max_abs_logit_delta'][t]>=0,'nonnegative margin/error')
        ld=p['logsumexp_current'][t]-p['logsumexp_reference'][t]
        close(p['logsumexp_delta'][t],ld,'LSE difference')
        close(p['max_abs_logprob_delta'][t],max(abs(p['delta_min'][t]-ld),abs(p['delta_max'][t]-ld)),'log-prob extrema')
        close(p['max_abs_logit_delta'][t],max(abs(p['delta_min'][t]),abs(p['delta_max'][t])),'logit extrema')
        match.append(p['current_top1_ids'][t]==p['reference_top1_ids'][t]);cert.append(p['reference_top1_margin'][t]>2*p['max_abs_logit_delta'][t])
        require(bool(p['top1_matches'][t])==match[-1] and bool(p['margin_certified'][t])==cert[-1],'match/certificate definition')
        require(not cert[-1] or match[-1],'strict margin certificate implies measured Top1 match')
    require(record['top1_match_count']==sum(match) and record['top1_total_count']==T and record['all_positions_top1_match']==all(match),'document Top1 integer counts')
    close(record['top1_agreement'],sum(match)/T,'document Top1 fraction')
    require(record['margin_certified_count']==sum(cert),'document margin count')
    require(record['current_tied_positions']==sum(x>1 for x in p['current_top1_tie_counts']) and record['reference_tied_positions']==sum(x>1 for x in p['reference_top1_tie_counts']),'document tie counts')
    maxpos=int(np.argmax(p['max_abs_logit_delta']));require(record['max_abs_token_position']==maxpos and record['max_abs_vocab_id']==p['max_abs_vocab_ids'][maxpos],'document maximum coordinate')
    close(record['max_abs_logit_delta'],p['max_abs_logit_delta'][maxpos],'document maximum')
    close(record['max_abs_logprob_delta'],max(p['max_abs_logprob_delta']),'document max log-prob')
    close(record['logit_rmse'],math.sqrt(math.fsum(x*x for x in p['logit_rmse'])/T),'document RMSE')
    E,S=record['error_energy'],record['reference_signal_energy']
    require(all(math.isfinite(x) and x>=0 for x in (E,S)),'logit document energies')
    close(record['logit_rmse'],math.sqrt(E/(T*V)),'logit energy/RMSE')
    if S:
        close(record['relative_l2_percent'],100*math.sqrt(E/S),'logit relative L2')
        require(record['relative_l2_state']=='defined','logit ratio defined state')
    else:require(record['relative_l2_percent'] is None and record['relative_l2_state']==('exact_zero_match' if E==0 else 'zero_signal_nonzero_error'),'zero logit signal explicit')
    counts=record['score_within_threshold_counts'];thresholds=record['score_thresholds']
    require(len(counts)==len(thresholds) and counts==sorted(counts) and all(type(n) is int and 0<=n<=T*V for n in counts),'threshold coverage integer counts')
    for epsilon,count in zip(thresholds,counts):require((record['max_abs_logit_delta']<=epsilon)==(count==T*V),'max/complete threshold coverage equivalence')
    report={'doc_id':record['doc_id'],'tokens':T,'score_pairs':T*V,'aggregate_formula_verified':True,'raw_positions':[],
            'top1_match_count':sum(match),'top1_total_count':T,'max_abs_logit_delta':record['max_abs_logit_delta'],'head_roundoff':None}
    if record['raw_audit'] is None:return report
    verify_file(record['raw_audit']);manifest=read_json(record['raw_audit']['path']);verify_file(manifest['raw'])
    require(manifest['doc_id']==record['doc_id'] and all(manifest[k]==record[k] for k in ('tokens','vocab_size','hidden_size')),'raw logit manifest scope')
    require(manifest['head']['consumed_tensor_sha256']==record['head_sha256'],'consumed head identity agreement')
    with np.load(manifest['raw']['path'],allow_pickle=False) as archive:arrays={key:archive[key].copy() for key in archive.files}
    require(set(arrays)==set(manifest['arrays']),'all raw arrays declared')
    for key,value in arrays.items():require(array_identity(value)==manifest['arrays'][key],'raw array identity '+key)
    positions=arrays['token_positions'];expected=sorted(set([0,T//2,T-1]));require(positions.tolist()==expected,'predeclared token positions')
    require(arrays['logits_current'].shape==arrays['logits_reference'].shape==(len(positions),V),'full raw vocabulary rows')
    require(arrays['hidden_current'].shape==arrays['hidden_reference'].shape==(len(positions),D),'complete hidden vectors')
    vocab=arrays['vocab_ids'];required=set([0,min(2048,V-1),min(4096,V-1),min(65536,V-1),V-1])
    for t in positions:
        for key in ('current_top1_ids','reference_top1_ids','max_abs_vocab_ids'):required.add(p[key][t])
    require(vocab.tolist()==sorted(required),'predeclared fixed and explicitly diagnostic vocab selection')
    actual_head=head_source_rows(manifest['head'],vocab,head_cache)
    require(np.array_equal(actual_head,arrays['head_rows']),'raw head rows equal original checkpoint BF16 exact FP32 conversion')
    for arm in ('current','reference'):
        path=Path(doc_directory)/f'final_hidden_{arm}.npz'
        with np.load(path,allow_pickle=False) as payload:full=payload['hidden']
        if full.ndim==3:full=full[0]
        require(np.array_equal(full[positions],arrays['hidden_'+arm]),'raw selected hidden equals saved decoder final '+arm)
        require(array_identity(full)==record['final_hidden_identity'][arm],'whole final hidden hash '+arm)
    per_raw=[];spots=[];exact_spots=[]
    for i,t in enumerate(positions):
        derived=independent_logit_row(arrays['logits_current'][i],arrays['logits_reference'][i])
        for key,value in derived.items():
            if isinstance(value,(bool,int)):require(p[key][t]==value,'raw exact metric '+key)
            else:close(p[key][t],value,'raw metric '+key)
        per_raw.append({'position':int(t),**derived})
        for j,v in enumerate(vocab):
            high=[];observed=[]
            for arm in ('current','reference'):
                h=arrays['hidden_'+arm][i].astype(np.float64);w=actual_head[j].astype(np.float64)
                value=math.fsum((h*w).tolist());high.append(value);observed.append(float(arrays['logits_'+arm][i,v]))
                if (i,j) in {(0,0),(len(positions)-1,len(vocab)-1)}:
                    exact=exact_dyadic_dot(h,w);exact_spots.append({'position':int(t),'vocab_id':int(v),'arm':arm,'exact_numerator':str(exact.numerator),'exact_denominator':str(exact.denominator),'fsum_minus_exact':float(Fraction.from_float(value)-exact),'fp32_head_minus_exact':float(Fraction.from_float(observed[-1])-exact)})
            spots.append({'position':int(t),'vocab_id':int(v),'current_fp32_head_error':observed[0]-high[0],'reference_fp32_head_error':observed[1]-high[1],
                          'measured_pair_delta':observed[0]-observed[1],'high_precision_pair_delta':high[0]-high[1],
                          'pair_delta_head_roundoff':(observed[0]-observed[1])-(high[0]-high[1])})
    report.update(raw_positions=expected,independent_full_vocabulary_rows=per_raw,
                  head_roundoff={'selection':'fixed IDs plus result-dependent diagnostic extrema/Top1; not IID','dots_checked':2*len(spots),'spots':spots,'exact_dyadic_spots':exact_spots,
                    'max_abs_current':max(abs(x['current_fp32_head_error']) for x in spots),'max_abs_reference':max(abs(x['reference_fp32_head_error']) for x in spots),
                    'max_abs_pair_delta_head_roundoff':max(abs(x['pair_delta_head_roundoff']) for x in spots),
                    'limitation':'selected dot products only; not a global FP32 head error bound'})
    return report

_PER_ARM=('silu_lookup','gating_multiply_total','gating_multiply_extra','down_host_total')
_CURRENT=('whole_mlp_local','mlp_fixed_residual_local')
_PAIRED=('mlp_branch_propagation','mlp_residual_input_propagation','mlp_residual_sum_propagation')


def metric_formulas(metric,label):
    N=metric['total_elements'];valid=metric['valid_elements']
    require(type(N) is int and N>0 and valid==N and metric['nonfinite_elements']==0 and metric['excluded_elements']==0,label+' full finite domain')
    E,S,Z=(metric[k] for k in ('error_energy','signal_energy','signed_error_sum'))
    require(all(math.isfinite(x) for x in (E,S,Z)) and E>=0 and S>=0,label+' legal energies')
    close(metric['absolute_rmse'],math.sqrt(E/N),label+' RMSE');close(metric['signal_rms'],math.sqrt(S/N),label+' signal RMS')
    require(metric['absolute_max']>=0 and metric['zero_signal']==(S==0) and not metric['empty_valid_domain'],label+' domain flags')
    if S:
        close(metric['relative_l2_percent'],100*math.sqrt(E/S),label+' relative L2')
        close(metric['normalized_signed_bias_percent'],100*Z/math.sqrt(N*S),label+' normalized bias')
    else:require(metric['relative_l2_percent'] is None and metric['normalized_signed_bias_percent'] is None,label+' zero signal not hidden')


def sampled_flat_indices(size,count,seed):
    chosen={0,size-1} if count>1 else {0};counter=0
    while len(chosen)<min(size,count):
        value=int.from_bytes(hashlib.sha256((seed+':'+str(counter)).encode()).digest()[:8],'big')%size
        chosen.add(value);counter+=1
    return sorted(chosen)


def signed24(x):return x-(1<<24) if (1<<23)<=x<1<<24 else x


def round_away_ratio(numerator,denominator):
    q=(2*abs(numerator)+denominator)//(2*denominator)
    return -q if numerator<0 else q


def audit_mlp_records(rows,doc_id,audited):
    expected={(layer,op,arm) for layer in range(32) for arm,ops in [('current',_PER_ARM),('reference',_PER_ARM),('current',_CURRENT),('paired',_PAIRED)] for op in ops}
    coordinates=[(r['layer'],r['op'],r['arm']) for r in rows]
    require(len(rows)==416 and len(set(coordinates))==416 and set(coordinates)==expected,'416 complete unique extended MLP sites')
    sampled=0;host_sampled=0;pair_sampled=0;product_max=Fraction(0);lut_identities=set();semantics=Counter()
    row_map={(r['layer'],r['op'],r['arm']):r for r in rows}
    for row in rows:
        require(row['doc_id']==doc_id and row['node']=='mlp_extension','MLP document/node identity')
        op,arm,layer=row['op'],row['arm'],row['layer'];metric=row['metrics'];meta=row['metadata'];q=row['qualifiers']
        metric_formulas(metric,'MLP '+op)
        require(q['shared_rule_zero_is_not_total_loss_zero'] is True and q['strict_per_output_domain'] is False,'MLP metric qualification')
        if op=='gating_multiply_extra':require(metric['error_energy']==0 and metric['absolute_max']==0,'independent common product exit equals actual')
        if op=='gating_multiply_total':require(metric['absolute_max']<=2**-17,'same-LUT product output rounding bound')
        if op!='silu_lookup':
            points=meta.get('raw_samples',[])
            if op in ('down_host_total',*_CURRENT,*_PAIRED):
                require(bool(points)==audited,'paired MLP sample scope')
                if points:require([x['flat_index'] for x in points]==sampled_flat_indices(metric['total_elements'],16,f'{doc_id}:{layer}:{op}:{arm}'),'paired MLP sample indices')
                for point in points:
                    a,b=point['current'],point['reference'];require(math.isfinite(a) and math.isfinite(b),'finite raw MLP pair')
                    require(abs(a-b)<=metric['absolute_max']+1e-12,'sample within full-tensor maximum')
                    pair_sampled+=1
                    if op=='down_host_total':
                        code=point['down_raw_int32'];require(type(code) is int and -(1<<31)<=code<(1<<31),'S32 raw Host input')
                        require(a==float(np.float32(code)/np.float32(65536)) and b==code/65536,'independent S32 to FP32 Host conversion')
                        host_sampled+=1
                    if op=='mlp_fixed_residual_local':
                        require(a==float(np.float32(point['residual_base'])+np.float32(point['current_branch'])) and b==float(np.float32(point['residual_base'])+np.float32(point['reference_branch'])),'same fixed residual base FP32 sum')
            continue
        require(q['silu_analytic_approximation_not_evaluated'] and q['semantics_only_not_total_function_approximation'],'SiLU shared semantics qualification')
        require(metric['error_energy']==0 and metric['absolute_max']==0,'SiLU semantic identity not analytic approximation')
        counts=meta['counts'];require(counts['product_s32_overflow']==0 and counts['product_common_exit_mismatch']==0,'actual complete product semantic/overflow check')
        require(sum(counts[k] for k in ('negative_outer_branch','positive_outer_branch','interior_lookup'))==metric['total_elements'],'SiLU all branch counts')
        require(meta['max_interior_address_displacement_q16_code']<=128,'rounded lookup grid displacement')
        for k,v in counts.items():semantics[k]+=v
        points=meta['raw_samples'];require(bool(points)==audited,'MLP sample scope follows frozen audit set')
        if not audited:continue
        values=meta.get('lut_values_s24')
        if values is None:
            require(meta['lut_values_record']==dict(doc_id=doc_id,layer=layer,arm='current',op='silu_lookup'),'SiLU same-layer current table link')
            original=row_map[layer,'silu_lookup','current']['metadata']
            require(original['lut_identity']==meta['lut_identity'],'two arms same LUT identity')
            values=original['lut_values_s24']
        lut=np.asarray(values,dtype=np.dtype(meta['lut_identity']['dtype'].replace('torch.','')))
        require(list(lut.shape)==meta['lut_identity']['shape'] and lut.shape==(8193,),'SiLU full quantized LUT geometry')
        require(hashlib.sha256(lut.tobytes()).hexdigest()==meta['lut_identity']['sha256'],'SiLU original table identity')
        lut_identities.add(meta['lut_identity']['sha256'])
        require([x['flat_index'] for x in points]==sampled_flat_indices(metric['total_elements'],16,f'{doc_id}:{layer}:{arm}'),'MLP predeclared output sample coordinates')
        for point in points:
            g=signed24(point['gate_input_raw']);u=signed24(point['up_input_raw']);require(-(1<<23)<=g<(1<<23) and -(1<<23)<=u<(1<<23),'sample legal normalized S24')
            address=min(max((g+(16<<16)+128)>>8,0),8192)
            silu=0 if g<=-(16<<16) else g if g>=16<<16 else int(lut[address])
            numerator=silu*u;code=round_away_ratio(numerator,1<<16)
            require(-(1<<31)<=code<(1<<31),'sample legal S32 product')
            require((point['gate_s24'],point['up_s24'],point['lut_address'],point['silu_s24'],point['product_s32_actual'])==(g,u,address,silu,code),'independent SiLU lookup/product integer reconstruction')
            require(int(point['exact_product_numerator'])==numerator and point['exact_product_denominator_bits']==32,'sample exact same-LUT product')
            error=abs(Fraction(code,1<<16)-Fraction(numerator,1<<32));require(error<=Fraction(1,1<<17),'sample exact product output bound')
            sampled+=1;product_max=max(product_max,error)
    return {'doc_id':doc_id,'mlp_rows':len(rows),'aggregate_formula_verified':True,'independent_product_samples':sampled,'independent_host_conversion_samples':host_sampled,'paired_output_spots_checked':pair_sampled,
            'product_bound_violations':0 if sampled else None,'max_sample_product_absolute_error':float(product_max) if sampled else None,
            'lut_identities':sorted(lut_identities),'actual_full_array_semantic_counts':dict(semantics),
            'limitation':'SiLU intermediate reconstructed from real inputs/LUT; full-branch numeric statistics are not a full independent branch recomputation'}


def runtime_bindings(base,session=None):
    base=Path(base).resolve()
    if session is None:return base/'gpu_receipt.json',base/'gpu_launch_manifest.json',None
    session=Path(session).resolve();group_path=base/'execution_receipt.json';group=read_json(group_path)
    require(group['schema']=='m005_r005_persistent_group_receipt_v1' and group['execution_state']=='completed','complete canonical persistent group')
    require(group['runtime_kind']=='segment_of_shared_gpu_worker','group is explicitly shared-process segment')
    require(group['source_unchanged'] is True and group['coverage_complete'] is True and group['exit_code']==0,'group consumed sources and complete coverage')
    require(Path(group['canonical_group_path']).resolve()==base and Path(group['session_path']).resolve()==session,'canonical group and session paths')
    verify_file(group['session_launch_identity'])
    require(Path(group['session_launch_identity']['path']).resolve()==session/'session_launch_manifest.json','canonical global launch reference')
    paired=read_json(base/'paired_result.json');manifest=read_json(base/'paired_worker_manifest.json')
    require(group['logical_batch_ids']==paired['formal_batch_ids'] and group['doc_ids']==[d['doc_id'] for d in paired['documents']],'group scope equals measured scope')
    require(group['completed_doc_ids']==group['doc_ids'] and group['actual_token_lengths']==[d['tokens'] for d in paired['documents']],'complete group tokens and identities')
    receipt=session/'session_gpu_receipt.json';launch=session/'session_launch_manifest.json'
    require(Path(group['global_receipt_path']).resolve()==receipt,'canonical global receipt reference')
    complete=read_json(receipt);launched=read_json(launch)
    require(complete.get('execution_state')=='completed' and complete.get('exit_code')==complete.get('native_exit_code')==0 and complete.get('worker_reaped') is True and complete.get('source_unchanged') is True and complete.get('stop_reason') is None,'shared GPU session must finish successfully before final audit')
    shared=group['shared_worker_identity']
    require(all(key in shared for key in ('pid','pgid','starttime','argv')) and shared['pid']==shared['pgid'] and bool(shared['argv']),'complete shared process identity')
    require(shared==complete['shared_worker_identity']==launched['shared_worker_identity'] and complete['worker_pid']==shared['pid'],'one actual shared launch and worker identity')
    for value in (paired,manifest):
        require(value['runtime_kind']=='segment_of_shared_gpu_worker' and value['shared_worker_identity']==shared and Path(value['shared_session']).resolve()==session,'measured artifacts explicitly bind the shared process')
    for item in group['code']+group['input_identities']+group['output_identities']:verify_file(item)
    require({r['path']:r['sha256'] for r in group['code']}=={r['path']:r['sha256'] for r in manifest['code']},'group and consumed manifest source identities')
    analysis_path=session/'analysis_manifest.json';analysis=read_json(analysis_path)
    require(analysis['schema']=='m005_r005_analysis_manifest_v1' and analysis['model_execution_complete'] is True and analysis['completed_documents']==analysis['expected_documents']==1024 and analysis['missing_doc_ids']==[],'completed global target before final group audit')
    require(analysis['actual_doc_ids']==analysis['expected_doc_ids'] and len(set(analysis['actual_doc_ids']))==1024,'unique ordered global target')
    require(analysis['shared_worker_identity']==shared,'analysis shared worker identity')
    for key,expected in (('session_gpu_receipt',receipt),('session_launch_manifest',launch)):
        verify_file(analysis[key]);require(Path(analysis[key]['path']).resolve()==expected,'analysis canonical '+key)
    matches=[g for g in analysis['ordered_groups'] if Path(g['attempt_path']).resolve()==base]
    require(len(matches)==1 and matches[0]['group_id']==group['group_id'],'one canonical group in global analysis roster')
    verify_file(matches[0]['receipt']);require(Path(matches[0]['receipt']['path']).resolve()==group_path,'global roster authentic group receipt')
    loader=read_json(base/'shared_loader_reference.json')['global_loader'];verify_file(loader)
    require(Path(loader['path']).resolve()==session/'stream_loader_validation.json','shared actual model loader source')
    head=read_json(base/'output_head/shared_head_reference.json')['global_head'];verify_file(head)
    require(Path(head['path']).resolve()==session/'output_head/output_head_identity.json','shared actual output-head source')
    require(read_json(head['path'])==read_json(base/'output_head/output_head_identity.json'),'group head identity equals consumed global head')
    runtime={'canonical_group':str(base),'session':str(session),'shared_process':True,'shared_worker_identity':shared,
             'group_receipt':{'path':str(group_path),'sha256':sha_file(group_path)},
             'global_receipt':{'path':str(receipt),'sha256':sha_file(receipt)},'global_launch':{'path':str(launch),'sha256':sha_file(launch)},
             'analysis_manifest':{'path':str(analysis_path),'sha256':sha_file(analysis_path)},'shared_loader_reference':loader,'shared_head_reference':head}
    return receipt,launch,runtime


def audit_core_via_view(base,session,output):
    """Only /tmp aliases; never fabricate per-group launch/receipt or edit old code."""
    base=Path(base).resolve();receipt,launch,runtime=runtime_bindings(base,session)
    require(runtime is not None,'core compatibility view only for a shared session')
    old=Path(__file__).with_name('audit_formal_numerical.py')
    require(sha_file(old)=='1b0eae5f16b2b6b7957d319b570c95c5ab918a2bec94b288a3a240ca8773e421','immutable previously qualified core auditor')
    output=Path(output);require(not output.exists(),'never overwrite core audit')
    with tempfile.TemporaryDirectory(prefix='A014_shared_gpu_readonly_view_') as directory:
        view=Path(directory)/'group';view.mkdir()
        for path in base.iterdir():
            if path.name not in ('gpu_receipt.json','gpu_launch_manifest.json'):(view/path.name).symlink_to(path,target_is_directory=path.is_dir())
        (view/'gpu_receipt.json').symlink_to(receipt)
        (view/'gpu_launch_manifest.json').symlink_to(launch)
        raw_output=Path(directory)/'raw_core_report.json'
        environment=dict(os.environ,CUDA_VISIBLE_DEVICES='')
        run=subprocess.run([sys.executable,'-B',str(old),'--attempt',str(view),'--output',str(raw_output)],capture_output=True,text=True,env=environment,timeout=45)
        require(run.returncode==0,'frozen core auditor failed: '+run.stderr[-4000:])
        raw=read_json(raw_output)
        report={**raw,'attempt':str(base),'ephemeral_evidence_view':raw['attempt'],'evidence_view_deleted_after_audit':True,
                'runtime_binding':runtime,'compatibility_note':'receipt/launch symlinks referred to one real completed global session; this group was not independently GPU-launched',
                'adapter_source_identity':{'path':str(Path(__file__).resolve()),'sha256':sha_file(__file__)}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    return {'path':str(output.resolve()),'sha256':sha_file(output)}


def audit_attempt(attempt,session=None):
    base=Path(attempt).resolve();start=time.monotonic();receipt_path,launch_path,runtime=runtime_bindings(base,session);receipt=read_json(receipt_path)
    require(receipt.get('execution_state')=='completed' and receipt.get('exit_code')==receipt.get('native_exit_code')==0 and receipt.get('worker_reaped') is True and receipt.get('source_unchanged') is True and receipt.get('stop_reason') is None,'complete unchanged reaped GPU receipt')
    manifest=read_json(base/'paired_worker_manifest.json');result=read_json(base/'paired_result.json')
    require(manifest['schema']=='m005_r005_extended_document_stream_v1' and result['schema']=='m005_r005_extended_result_v1','R005 explicit schemas')
    require(result['execution_state']=='completed' and result['required_extension_complete'] and result['source_unchanged'] and result['shared_weight_buffers_unchanged'],'completed extension and immutable decoder')
    require(result['batch_bootstrap_replicates']==0 and result['batch_confidence_intervals_computed'] is False,'no per-batch bootstrap claim')
    for record in manifest['code']:verify_file(record)
    launched={r['path']:r['sha256'] for r in read_json(launch_path)['source_identity']}
    require(all(launched.get(r['path'])==r['sha256'] for r in manifest['code']),'all worker sources included in launch freeze')
    verify_file(manifest['document_source']);verify_file(result['output_head_source'])
    head=read_json(result['output_head_source']['path'])
    selected=manifest['selected_documents'];ids=[row['doc_id'] for row in selected]
    require(len(ids)==len(set(ids))==result['measured_documents'] and [d['doc_id'] for d in result['documents']]==ids,'complete selected document order')
    require(len({d['duplicate_cluster'] for d in selected})==len(ids),'unique clusters within attempt')
    source={row['doc_id']:row for row in selected};audit_ids=manifest['audit_document_ids']
    require(audit_ids==result['audit_document_ids'] and set(audit_ids)<=set(ids),'frozen audit IDs')
    formal=manifest['planned_formal_documents']>0
    require(result['formal_eval_documents']==(len(ids) if formal else 0),'development/formal count separated')
    if formal:
        plan=read_json(manifest['document_source']['path']);by_batch={b['batch_id']:b for b in plan['batches']};batches=result['formal_batch_ids']
        require(batches==manifest['formal_batch_ids'],'formal batch IDs')
        require([d for b in batches for d in by_batch[b]['doc_ids']]==ids,'same frozen formal document order')
        verify_file(plan['input_stream_manifest']);stream=read_json(plan['input_stream_manifest']['path'])
        original={d['doc_id']:d for d in stream['documents']}
    else:original={d['doc_id']:d for d in read_rows(manifest['document_source']['path'])}
    for d in selected:require(all(d.get(k)==original[d['doc_id']].get(k) for k in ('domain','split','evidence_role','text_sha256','duplicate_cluster')),'document source identity')
    logit_rows=read_rows(base/'logit_metrics.jsonl');mlp_rows=read_rows(base/'mlp_metrics.jsonl')
    require([r['doc_id'] for r in logit_rows]==ids and len(mlp_rows)==416*len(ids),'extended document/row coverage')
    hidden=read_rows(base/'tensor_metrics.jsonl');local=read_rows(base/'local_tensor_metrics.jsonl');dynamic=read_rows(base/'dynamic_metadata.jsonl')
    core_sites={('linear',op) for op in ('q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj')}|{('rope','query_rope'),('rope','key_rope'),('qk','qk'),('softmax','softmax'),('pv','pv')}
    expected_core={(layer,node,op) for layer in range(32) for node,op in core_sites}
    expected_dynamic={(arm,layer,fn,i) for arm in ('current','reference') for layer in range(32) for fn,n in [('prepare_fixed_activation',4),('_kv12_quantize',2)] for i in range(n)}
    reports=[];head_cache=set();raw_hidden=0
    head_source_rows(head,[0],head_cache)  # full consumed source-body hash, including no-audit groups
    for i,doc in enumerate(ids):
        directory=base/'documents'/f'doc{i:04d}';input_identity=read_json(directory/'input_identity.json');row=logit_rows[i]
        require(input_identity['doc_id']==doc and input_identity['tokens']==row['tokens']==result['documents'][i]['tokens'],'tokens/document identity')
        require(row['head_sha256']==head['consumed_tensor_sha256'] and row['vocab_size']==128256 and row['hidden_size']==4096,'same actual output head')
        require(all(row.get(k)==source[doc].get(k) for k in ('domain','split','evidence_role','text_sha256','duplicate_cluster')),'logit source fields')
        require(read_json(directory/'logit_metrics.json')==row,'logit per-doc and stream equality')
        if formal:
            verify_file(original[doc]['token_artifact'])
            with np.load(original[doc]['token_artifact']['path'],allow_pickle=False) as tokens:
                require(tokens['input_ids'].tolist()==input_identity['input_ids'][0] and tokens['attention_mask'].tolist()==input_identity['attention_mask'][0],'original frozen formal tokens/mask')
                require(np.array_equal(tokens['position_ids'],np.arange(row['tokens'])) and bool(np.all(tokens['attention_mask']==1)),'real unpadded formal positions')
            require(input_identity['retokenized'] is False,'formal inputs not retokenized')
        core=[r for r in local if r['doc_id']==doc];hs=[r for r in hidden if r['doc_id']==doc];ds=[r for r in dynamic if r['doc_id']==doc]
        require(len(core)==384 and {(r['layer'],r['node'],r['op']) for r in core}==expected_core,'unchanged384 old local coordinates')
        require(len(hs)==32 and {r['layer'] for r in hs}==set(range(32)),'unchanged32 hidden coordinates')
        require(len(ds)==384 and {(r['arm'],r['layer'],r['function'],r['ordinal']) for r in ds}==expected_dynamic,'unchanged dynamic192 events per arm')
        for h in hs:
            metric_formulas(h['metrics']['current_vs_reference'],'decoder hidden')
            if h['output_artifact']:
                require(doc in audit_ids,'raw hidden only declared audit doc');verify_file(h['output_artifact'])
                with np.load(h['output_artifact']['path'],allow_pickle=False) as arrays:
                    a,b=arrays['current'].astype(np.float64),arrays['reference'].astype(np.float64);delta=a-b
                    m=h['metrics']['current_vs_reference']
                    close(m['error_energy'],math.fsum((delta*delta).ravel().tolist()),'raw hidden error energy')
                    close(m['signal_energy'],math.fsum((b*b).ravel().tolist()),'raw hidden signal energy')
                    close(m['signed_error_sum'],math.fsum(delta.ravel().tolist()),'raw hidden signed sum')
                    require(m['absolute_max']==float(np.max(np.abs(delta))),'raw hidden max')
                raw_hidden+=1
        final=read_json(directory/'final_norm_comparison.json');metric_formulas(final['metrics']['current_vs_reference'],'final norm')
        require((row['raw_audit'] is not None)==(doc in audit_ids),'logit raw scope matches audit selection')
        mlp=audit_mlp_records([r for r in mlp_rows if r['doc_id']==doc],doc,doc in audit_ids)
        logits=audit_logit_record(row,directory,head_cache);reports.append({'doc_id':doc,'mlp':mlp,'logits':logits})
    baseline=None
    if (base/'readonly_baseline_qualification.json').exists():
        baseline=read_json(base/'readonly_baseline_qualification.json');require(baseline['passed'] is True,'read-only baseline qualification passed')
        for file in baseline['source']:verify_file(file)
        previous=Path(baseline['baseline']);old=read_json(previous/'node_witnesses/manifest.json');new=read_json(base/'node_witnesses/manifest.json')
        def coordinates(manifest):return {(r['doc_id'],r['layer'],r['node'],r['op_name']):r for r in manifest['records']}
        left,right=coordinates(old),coordinates(new);require(set(left)==set(right),'pilot baseline witness selection unchanged')
        for key in left:
            require(left[key]['status']==right[key]['status'],'pilot witness status unchanged')
            if left[key]['status']=='saved':
                require(left[key]['arrays']==right[key]['arrays'],'pilot witness all raw arrays unchanged')
                for parent,rec in ((previous,left[key]),(base,right[key])):require(sha_file(parent/'node_witnesses'/rec['path'])==rec['sha256'],'baseline witness original file identity')
        baseline={'path':str(previous),'all_old_witness_arrays_unchanged':True,'witness_records_compared':len(left),'scope':'same four development docs and shapes only; not formal1024 execution'}
    return {'schema':'m005_r005_independent_extended_audit_v1','execution_state':'completed','review':'limited_evidence_verified','overall_precision_verdict':'inconclusive',
            'attempt':str(base),'runtime_binding':runtime,'source_identity':{'path':str(Path(__file__).resolve()),'sha256':sha_file(__file__)},
            'documents':reports,'measured_documents':len(ids),'formal_eval_documents':len(ids) if formal else 0,'audit_doc_ids':audit_ids,
            'raw_hidden_tensors_recomputed':raw_hidden,'full_consumed_head_source_verified':True,'readonly_baseline':baseline,'seconds':time.monotonic()-start,
            'limitations':['at most128 real tokens,32-layer prefill; no long context/decode or labeled accuracy claim',
              'full-tensor statistics and source/formula checks distinguished from preselected raw witnesses',
              'selected FP32 head roundoff spots do not prove a whole-vocabulary head rounding bound',
              'SiLU same quantized lookup semantics, not analytic approximation error; whole-MLP spots are not full independent branch reruns']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--attempt',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--session',type=Path,help='real completed persistent GPU session; no per-group fake receipt')
    parser.add_argument('--core-output',type=Path,help='optional frozen core-audit output via a temporary read-only shared-session view')
    args=parser.parse_args(argv)
    require(not args.output.exists(),'never overwrite previous independent audit')
    if args.core_output:require(args.session is not None,'core-output requires shared session binding')
    report=audit_attempt(args.attempt,args.session)
    if args.core_output:report['core_audit']=audit_core_via_view(args.attempt,args.session,args.core_output)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({k:report[k] for k in ('execution_state','review','measured_documents','formal_eval_documents','audit_doc_ids','seconds')}))
    return 0

if __name__=='__main__':raise SystemExit(main())
