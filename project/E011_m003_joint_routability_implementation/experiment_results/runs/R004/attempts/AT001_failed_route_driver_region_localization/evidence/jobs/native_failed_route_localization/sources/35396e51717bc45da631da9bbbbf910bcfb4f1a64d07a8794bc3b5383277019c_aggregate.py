#!/usr/bin/env python3
"""Recompute unique-net attribution; native facts only, no EDA commands."""
import argparse, collections, csv, hashlib, json
from pathlib import Path

def rows(p):
    with p.open() as f:
        yield from csv.DictReader(f, delimiter='\t')

def write(p, names, records):
    with p.open('w', newline='') as f:
        w=csv.writer(f, delimiter='\t'); w.writerow(names); w.writerows(records)

def norm(owner, plan):
    if owner=='TOP_PORT': return 'TOP_PORT'
    base=plan['normalization_base']
    parts=owner.split('/')
    # The primitive's containing RTL instance, capped at four levels below
    # u_compute. No removal of generate indices, semantic/name guesses or refs.
    module='/'.join(parts[:-1])
    if module.startswith(base+'/'):
        return base+'/'+ '/'.join(module[len(base)+1:].split('/')[:4])
    return '/'.join(module.split('/')[:4]) or 'ROOT'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--final',action='store_true')
    a=ap.parse_args();out=a.out;plan=json.loads(a.plan.read_text())
    cells={r['name']:r for r in rows(out/'cells.tsv')}
    sites={r['site']:r for r in rows(out/'sites.tsv')}
    def physical(owner):
        if owner=='TOP_PORT': return ('TOP_PORT','TOP_PORT','TOP_PORT','TOP_PORT')
        r=cells.get(owner);p=owner
        if r is None: return ('UNKNOWN','UNKNOWN','UNKNOWN','UNKNOWN')
        while not r['LOC'] and r['REF_NAME'].startswith('DSP') and '/' in p:
            p=p.rsplit('/',1)[0];r=cells.get(p, {})
            if not r: return ('UNKNOWN','UNKNOWN','UNKNOWN','UNKNOWN')
        loc=r['LOC'];s=sites.get(loc,{})
        return (p,loc or 'UNPLACED',s.get('SLR','UNKNOWN'),s.get('clock_region','UNKNOWN'))
    nets={r['canonical']:dict(r,drivers=[],loads=[],inouts=[],unknown=[]) for r in rows(out/'net_inventory.tsv')}
    consumer=collections.defaultdict(set);regions=collections.defaultdict(set)
    for r in rows(out/'endpoints.tsv'):
        n=nets[r['canonical']];r.update(zip(('physical_owner','LOC','SLR','clock_region'),physical(r['owner'])))
        r['module']=norm(r['owner'],plan)
        role={'OUT':'drivers','IN':'loads'}.get(r['DIRECTION'],'inouts' if r['DIRECTION']=='INOUT' else 'unknown')
        if r['kind']=='TOP_PORT': role={'IN':'drivers','OUT':'loads'}.get(r['DIRECTION'],'inouts')
        n[role].append(r)
        if role=='loads': consumer[r['module']].add(r['canonical'])
        regions[(r['module'],r['SLR'],r['clock_region'],role)].add(r['canonical'])
    groups=collections.defaultdict(set);classes=collections.Counter();failed=[]
    for key,n in sorted(nets.items()):
        drivers=n['drivers'];loads=n['loads'];inouts=n['inouts']
        if inouts: owner,source,bucket='INOUT_OR_AMBIGUOUS','AMBIGUOUS','INOUT_OR_AMBIGUOUS'
        elif len(drivers)>1: owner,source,bucket='MULTIDRIVER','MULTIPLE','MULTIDRIVER'
        elif len(drivers)==0: owner,source,bucket='UNKNOWN_DRIVER','UNKNOWN','UNKNOWN_DRIVER'
        else: owner,source,bucket=drivers[0]['module'],drivers[0]['SLR'],'SINGLE_DRIVER'
        loadslr=sorted({r['SLR'] for r in loads})
        types=set()
        if any(cells.get(r['owner'],{}).get('REF_NAME') in ('GND','VCC') for r in drivers): types.add('CONSTANT')
        if any(r['IS_CLOCK'] in ('1','TRUE','true') for r in loads): types.add('CLOCK_SINK_NATIVE')
        if any(r['REF_PIN_NAME'] in ('CE','R','S','CLR','PRE','RST','EN','ENA','ENB','WE','WEA','WEB') for r in loads):types.add('CONTROL_SINK_NATIVE')
        if not types: types.add('DATA_OR_UNCLASSIFIED')
        n.update(driver_module=owner,source_SLR=source,load_SLRs=loadslr,bucket=bucket,types=sorted(types))
        n['group']=(owner,source,','.join(loadslr) or 'NO_LOADS')
        if int(n['conflict']):
            groups[n['group']].add(key);failed.append(n)
            for t in types: classes[t]+=1
    order=sorted(groups,key=lambda k:(-len(groups[k]),k));top=order[:20]
    write(out/'failed_nets.tsv',['canonical','aliases','driver_module','source_SLR','load_SLRs','driver_count','load_pin_count','INOUT_count','unknown_endpoint_count','bucket','native_sink_types','consumer_modules','clock_regions'],
        ([n['canonical'],n['aliases'],n['driver_module'],n['source_SLR'],','.join(n['load_SLRs']),len(n['drivers']),len(n['loads']),len(n['inouts']),len(n['unknown']),n['bucket'],','.join(n['types']),json.dumps(sorted({r['module'] for r in n['loads']})),json.dumps(sorted({r['clock_region'] for r in n['drivers']+n['loads']}))] for n in failed))
    write(out/'module_region_summary.tsv',['rank','driver_module','source_SLR','load_SLR_set','unique_conflict_nets'],([i+1,*k,len(groups[k])] for i,k in enumerate(order)))
    failed_ids={n['canonical'] for n in failed}
    write(out/'consumer_incidence.tsv',['consumer_module','unique_conflict_nets'],([k,len(v&failed_ids)] for k,v in sorted(consumer.items())))
    write(out/'clock_region_incidence.tsv',['module','SLR','clock_region','role','unique_conflict_nets'],([*k,len(v&failed_ids)] for k,v in sorted(regions.items())))
    from extend_aggregation import add_classification
    extra=add_classification(out, plan, nets, failed, cells, sites, groups)
    selected={};union=set()
    for i,k in enumerate(top):
        ids=sorted(groups[k]);union.update(ids)
        for net in ids[:plan['representative_nets_per_group']]:selected.setdefault(net,set()).add(f'TOP{i+1:02}')
    for net in extra:
        selected.setdefault(net,set()).add('ENDPOINT_CLASS_REPRESENTATIVE')
    supplemental={k for k,n in nets.items() if n['seed_tags']}
    for net in supplemental:
        selected.setdefault(net,set()).update(nets[net]['seed_tags'].split(','))
    selected={k:v for k,v in selected.items() if len(nets[k]['loads'])<=plan['deep_max_load_pins']}
    write(out/'deep_selected.tsv',['canonical','tags'],([k,','.join(sorted(v))] for k,v in sorted(selected.items())))
    # Tcl list items are braced and validated by prepare.py; names from native
    # NAME may contain brackets but cannot be re-evaluated as code.
    def tq(s):
        if any(c in s for c in '{}\n\r'):raise ValueError('unsupported NAME syntax')
        return '{'+s+'}'
    bytag=collections.defaultdict(list)
    for key,tags in sorted(selected.items()):
        for tag in tags:bytag[tag].append(key)
    with (out/'deep_targets.tcl').open('w') as f:
        f.write('set deep_nets [list '+ ' '.join(tq(k) for k in sorted(selected)) +']\n')
        f.write('set timing_groups [dict create]\n')
        for tag,keys in sorted(bytag.items()):
            f.write('dict set timing_groups '+tq(tag)+' [list '+' '.join(tq(k) for k in keys[:plan['representative_nets_per_group']])+']\n')
    write(out/'candidate_endpoints.tsv',['canonical','tags','kind','name','DIRECTION','REF_PIN_NAME','IS_CLOCK','owner','physical_owner','LOC','SLR','clock_region'],
        ([k,','.join(sorted(selected[k])),r['kind'],r['name'],r['DIRECTION'],r['REF_PIN_NAME'],r['IS_CLOCK'],r['owner'],r['physical_owner'],r['LOC'],r['SLR'],r['clock_region']] for k in sorted(selected) for r in nets[k]['drivers']+nets[k]['loads']+nets[k]['inouts']+nets[k]['unknown']))
    raw=sum(1 for _ in rows(out/'raw_conflicts.tsv'))
    coverage=union|(supplemental&failed_ids)
    result=dict(native_raw_conflict_objects=raw,canonical_conflict_nets=len(failed),native_report_conflict_nets=plan['native_report_conflict_nets'],
        raw_minus_canonical=raw-len(failed),canonical_minus_native_report=len(failed)-plan['native_report_conflict_nets'],
        primary_group_sum=sum(map(len,groups.values())),primary_group_disjoint=True,primary_groups=len(groups),
        top20_unique_conflict_nets=len(union),supplemental_unique_conflict_nets=len(supplemental&failed_ids),
        top20_plus_supplemental_union=len(coverage),coverage_denominator=len(failed),coverage_fraction=len(coverage)/len(failed) if failed else None,
        unknown_driver_nets=sum(n['bucket']=='UNKNOWN_DRIVER' for n in failed),multidriver_nets=sum(n['bucket']=='MULTIDRIVER' for n in failed),
        inout_ambiguous_nets=sum(n['bucket']=='INOUT_OR_AMBIGUOUS' for n in failed),
        unknown_source_SLR_nets=sum(n['source_SLR']=='UNKNOWN' for n in failed),unknown_load_SLR_nets=sum('UNKNOWN' in n['load_SLRs'] for n in failed),
        no_load_nets=sum(not n['loads'] for n in failed),unknown_endpoint_rows=sum(len(n['unknown']) for n in failed),
        native_type_incidence=dict(classes),overlap_nodes_native_report=plan['native_report_overlap_nodes'],overlap_node_identity_export='NOT_MEASURED',
        unmeasured_fields=['full_cut_TNS','SLL_usage_per_net','physical_overlap_node_to_net_complete_mapping'],
        consumer_incidence_additive=False,region_incidence_additive=False,source_load_cartesian_pairs_exported=False,
        top20_deep_representatives_per_group=plan['representative_nets_per_group'],final_native_deep_capture=a.final,
        reconciliation='EXACT' if len(failed)==plan['native_report_conflict_nets'] else 'DIFFERENT_COUNTS_RETAINED_REQUIRES_REVIEW')
    (out/'unknowns_and_coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    manifest=dict(schema=1,scope='SM013 bounded readonly attribution',normalization=plan['driver_normalization'],
        files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in out.glob('*.tsv')},coverage=result)
    (out/'attribution_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('canonical_conflict_nets','primary_groups','top20_unique_conflict_nets','reconciliation')}))

if __name__=='__main__':main()
