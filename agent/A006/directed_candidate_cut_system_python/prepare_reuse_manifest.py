#!/usr/bin/env python3
"""Freeze narrow already-closed inputs only; never scan the full primitive export."""
from pathlib import Path
import json
from directed_evidence import identity, save
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REPORT=ROOT/'project/hardware/vivado/reports/m002_E006_R004_AT001_exact_candidate_comparison'
ATTEMPT=ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/attempts/AT001_exact_candidate_comparison'
R003=ROOT/'project/hardware/vivado/reports/m002_E006_R003_AT001_lean_physopt_attribution'
OLD=json.loads((ROOT/'agent/A006/E006_exact_candidates/reuse_manifest.json').read_text())

def main():
    out=HERE/'reuse_manifest.json'
    assert not out.exists(), 'Never overwrite frozen reuse manifest'
    artifacts={}; candidates={}
    for point in ['C01','C02']:
        keys=[]
        def add(key,path):
            key=point+'_'+key;artifacts[key]=identity(path);keys.append(key);return key
        item={}
        facts=ATTEMPT/f'candidate_{point}_membership_resources_closed_facts.json'
        facts_data=json.loads(facts.read_text())
        item['root']=facts_data['target']['root']
        item['facts_key']=add('closed_facts',facts)
        add('closed_summary',ATTEMPT/f'candidate_{point}_membership_resources_closed_summary.json')
        for tag in ['RAW','S','P','membership','physical_members','site_members']:
            item[tag+'_key']=add(tag,REPORT/f'candidate_{tag}_{point}.tsv')
        add('native_resources',REPORT/f'utilization_candidate_{point}_SLR.rpt')
        add('native_membership_marker',REPORT/f'candidate_membership_{point}_closed.txt')
        item['artifact_keys']=keys;candidates[point]=item
    for key in ['R004_authority_hotspot_ownership_closed_stage_facts.json',
                'R004_authority_failure_samples_closed_stage_facts.json','utilization_global_SLR.rpt',
                'R003_AT001_hotspot_UNION_cells.tsv','R003_AT001_failure_exact_net_resolution.tsv']:
        row=OLD['artifacts'][key];assert identity(row['path'])==row;artifacts[key]=row
    for key,path in {
        'R004_started':ATTEMPT/'started.json','R004_input_bindings':ATTEMPT/'input_bindings.json',
        'R004_target_authority':ROOT/'project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json',
        'R004_independent_membership_review':ATTEMPT.parents[1]/'independent_membership_resources_and_probe_review.json',
        'R004_actual_probe_facts':ATTEMPT/'actual_failed_batch_property_probe_closed_facts.json'
    }.items():artifacts[key]=identity(path)
    save(out,dict(coverage_version='candidate_directed_cut_v1',same_DCP_required=True,
        checkpoint=json.loads((ATTEMPT/'input_bindings.json').read_text())['checkpoint'],
        candidates=candidates,artifacts=artifacts,failure_resolution_key='R003_AT001_failure_exact_net_resolution.tsv',
        semantics='R004 closed members/resources, R003 closed hotspot/failure samples, R001 same-DCP SLR capacity reused by actual identity. Fresh directed cut and timing required.',
        excluded='No entire-design all_primitive_locations.tsv scan or binding; old unfinished hotspot UNION full-endpoint recovery is not new R005 scope.'))
    print(json.dumps(identity(out)))

if __name__=='__main__':main()
