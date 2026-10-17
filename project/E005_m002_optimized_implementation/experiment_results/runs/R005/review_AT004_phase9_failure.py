"""Bounded independent native-log parsing; no EDA, process or production writes."""
from pathlib import Path
import hashlib
import json
import re
from datetime import datetime, timezone

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).parent

def identity(path):
    data = path.read_bytes()
    return {'path': str(path.relative_to(ROOT)), 'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()}

def parse(path):
    lines = path.read_text().splitlines()
    phase8_start = lines.index('Phase 8 Route finalize')
    def record(i):
        return {'native_line': i + 1, 'raw': lines[i]}
    def one(pattern):
        found = [(i, re.search(pattern, line)) for i, line in enumerate(lines) if i >= phase8_start]
        found = [(i, m) for i, m in found if m]
        assert len(found) == 1, (pattern, len(found))
        i, match = found[0]
        return {**record(i), 'value': float(match[1]) if '.' in match[1] else int(match[1])}
    result = {'source': identity(path), 'native_lines': len(lines)}
    result['metrics'] = {name: one(pattern) for name, pattern in {
        'overlap_nodes_phase8': r'Number of Node Overlaps\s*=\s*(\d+)',
        'overlap_nodes_phase9': r'Design is not legally routed. There are (\d+) node overlaps',
        'congestion_failed_signals': r'\[Route 35-162\] (\d+) signals failed',
        'failed_nets_phase8': r'Number of Failed Nets\s*=\s*(\d+)',
        'unrouted_nets_phase8': r'Number of Unrouted Nets\s*=\s*(\d+)',
        'partial_nets_phase8': r'Number of Partially Routed Nets\s*=\s*(\d+)',
        'vertical_utilization_percent': r'Global Vertical Routing Utilization\s*=\s*([\d.]+)',
        'horizontal_utilization_percent': r'Global Horizontal Routing Utilization\s*=\s*([\d.]+)',
        'route_native_total_elapsed_seconds': r'Total Elapsed time in route_design: ([\d.]+) secs',
    }.items()}
    result['final_global_congestion'] = []
    for i, line in enumerate(lines):
        m = re.fullmatch(r'(North|South|East|West) Dir (\d+x\d+) Area, Max Cong = ([\d.]+)%, Congestion bounded by tiles \(Lower Left Tile -> Upper Right Tile\):', line)
        if not m:
            continue
        windows = []
        j = i + 1
        while j < len(lines):
            w = re.fullmatch(r'\s+(INT_X\d+Y\d+) -> (INT_X\d+Y\d+)', lines[j])
            if not w:
                break
            windows.append({**record(j), 'lower_left': w[1], 'upper_right': w[2]})
            j += 1
        assert len(windows) == 5
        result['final_global_congestion'].append({**record(i), 'direction': m[1],
            'area_label': m[2], 'max_congestion_percent': float(m[3]), 'windows': windows})
    assert len(result['final_global_congestion']) == 4
    result['hotspot_levels'] = []
    for i, line in enumerate(lines):
        d = re.fullmatch(r'Direction: (North|South|East|West)', line)
        if d:
            cluster = re.fullmatch(r'Congested clusters found at Level (\d+)', lines[i+2])
            effective = re.fullmatch(r'Effective congestion level: (\d+) Aspect Ratio: ([\d.]+) Sparse Ratio: ([\d.]+)', lines[i+3])
            assert cluster and effective
            result['hotspot_levels'].append({'direction':d[1], 'cluster_level':int(cluster[1]),
                'effective_level':int(effective[1]), 'aspect_ratio':float(effective[2]),
                'sparse_ratio':float(effective[3]), 'records':[record(j) for j in (i,i+2,i+3)]})
    assert len(result['hotspot_levels']) == 4
    starts=[]
    pattern = r'(\d+)\. \((\d+,\d+,\d+)\) (NODE_\w+) Hist: (\d+) Tile Name: (INT_X\d+Y\d+) Node: (\S+) Overlapping Nets: (\d+)'
    for i,line in enumerate(lines):
        m=re.fullmatch(pattern,line)
        if m: starts.append((i,m))
    assert len(starts)==10
    result['top10_overlap_node_samples']=[]
    for index,(i,m) in enumerate(starts):
        end=starts[index+1][0] if index+1<len(starts) else next(j for j in range(i+1,len(lines)) if lines[j].strip()=='Verification failed')
        net_start=next(j for j in range(i+1,end) if lines[j]=='Nets:')
        nets=[{**record(j),'name':lines[j]} for j in range(net_start+1,end) if lines[j].startswith('scalellm_')]
        assert len(nets)<=5
        result['top10_overlap_node_samples'].append({**record(i), 'rank':int(m[1]),
            'native_tuple':m[2],'node_type':m[3],'hist':int(m[4]),'tile':m[5],
            'node':m[6],'overlapping_nets':int(m[7]),'listed_nets':nets,
            'full_native_block':[record(j) for j in range(i,end)]})
    result['phase_completions']=[]
    for i,line in enumerate(lines):
        if (' | Checksum:' in line and (line.startswith('Phase ') or line.startswith('Ending Routing Task'))):
            for j in range(i+1,min(i+4,len(lines))):
                t=re.match(r'Time \(s\): cpu = ([\d:]+) ; elapsed = ([\d:]+)', lines[j])
                if t:
                    seconds=lambda text:sum(int(v)*60**power for power,v in enumerate(reversed(text.split(':'))))
                    result['phase_completions'].append({'phase':line.split(' | Checksum:')[0],
                        'completion_record':record(i),'time_record':record(j),'elapsed':t[2],
                        'elapsed_seconds':seconds(t[2]),'cpu':t[1]})
                    break
    result['setup_and_hold_critical_warning']=[record(i) for i,line in enumerate(lines) if '[Route 35-468]' in line]
    result['errors_and_postroute_status']=[record(i) for i,line in enumerate(lines)
        if any(s in line for s in ('[Route 35-2]', '[Route 35-17]', 'Verification failed',
            'Running DRC after route_design', '[Vivado_Tcl 4-198]', "'route_design' failed", 'Exiting Vivado'))]
    return result

new_path=OUT/'AT004_phase9_failure_native_log_observed_prefix.txt'
old_path=ROOT/'project/hardware/vivado/reports/m002_E003_R003_AT001_full_route/vivado.log'
old_snapshot=OUT/'E003_closed_route_native_log_final_comparison.txt'
if old_snapshot.exists():
    assert old_snapshot.read_bytes() == old_path.read_bytes()
else:
    with old_snapshot.open('xb') as handle: handle.write(old_path.read_bytes())
new=parse(new_path)
old=parse(old_snapshot)
old['original_source']=identity(old_path)
compare={'metrics':{key:{'old':old['metrics'][key]['value'],'new':value['value'],
    'new_minus_old':value['value']-old['metrics'][key]['value']} for key,value in new['metrics'].items()}}
compare['final_global_congestion']=[]
for a,b in zip(old['final_global_congestion'],new['final_global_congestion']):
    assert a['direction']==b['direction']
    wa={(x['lower_left'],x['upper_right']) for x in a['windows']}
    wb={(x['lower_left'],x['upper_right']) for x in b['windows']}
    compare['final_global_congestion'].append({'direction':b['direction'],'area_label':b['area_label'],
        'old_max_percent':a['max_congestion_percent'],'new_max_percent':b['max_congestion_percent'],
        'delta_percentage_points':round(b['max_congestion_percent']-a['max_congestion_percent'],7),
        'common_windows':sorted(wa&wb)})
compare['same_named_phase_cumulative_elapsed']=[]
old_times={x['phase']:x for x in old['phase_completions']}
for item in new['phase_completions']:
    if item['phase'] in old_times:
        compare['same_named_phase_cumulative_elapsed'].append({'phase':item['phase'],
            'old':old_times[item['phase']]['elapsed'],'new':item['elapsed'],
            'new_minus_old_seconds':item['elapsed_seconds']-old_times[item['phase']]['elapsed_seconds']})
for record in (old,new):
    phases={x['phase']:x['elapsed_seconds'] for x in record['phase_completions']}
    record['derived_iteration2_elapsed_seconds']=phases['Phase 5.3 Global Iteration 2']-phases['Phase 5.2 Global Iteration 1']
evidence={'reviewed_at':datetime.now(timezone.utc).isoformat(), 'old':old,'new':new,'comparison':compare,
    'execution':'phase9_failure_and_late_native_diagnostics_review_completed; capture_and_process_terminal_pending',
    'verdict':'current candidate native legal routing failed; whole method general feasibility remains inconclusive',
    'applicability':'same tool/device and named router phases; changed RTL and SSI placement confounded',
    'review':'independent A007 bounded review; actual parent and A006 notification required',
    'limits':['Immutable current prefix ends at line 658; it is not a native-process or supervisor terminal receipt.',
        'Overlap nodes, congestion-failed signals, and Phase8 unrouted/partial counters are different metrics.',
        'Final Max Cong percent, Initial Estimated %Tiles, and placed Placer Final Level are different measurements.',
        'Native cluster level and effective congestion level are distinct fields.',
        'The 20 final windows overlap; missing old windows in the new top list are not measured as zero.',
        'Top10 node/net examples are selected samples, not a global root-cause attribution or distribution.',
        'Lower elapsed time to a failed route is not successful throughput or equal-work acceleration.',
        'Failed DCP, capture report closure, original error rethrow, success POST rejection, process/lock/freeze remain to be reviewed.']}
target=OUT/'AT004_phase9_failure_same_stage_review_evidence.json'
with target.open('x') as handle: json.dump(evidence,handle,ensure_ascii=False,indent=2); handle.write('\n')
print(json.dumps({'evidence':str(target.relative_to(ROOT)), 'comparison':compare,
    'old_iteration2_seconds':old['derived_iteration2_elapsed_seconds'],
    'new_iteration2_seconds':new['derived_iteration2_elapsed_seconds'],
    'top10_new':[{k:v for k,v in node.items() if k in ('rank','node_type','tile','node','overlapping_nets')} for node in new['top10_overlap_node_samples']]},indent=2))
