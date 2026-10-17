"""CPU-only exact extraction of native selected overlap samples; no DCP access."""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import hashlib
import json
import re

ROOT = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
OUT = Path(__file__).parent
SOURCE = ROOT / 'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route/vivado.log'
AUDITED = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R005/AT004_natural_terminal_native_log.txt'
data = SOURCE.read_bytes()
assert data == AUDITED.read_bytes()
lines = data.decode().splitlines()
scope_line = next(i for i,line in enumerate(lines,1) if line.startswith('Below is a list of the top 10 physical nodes'))
end_line = next(i for i,line in enumerate(lines,1) if i > scope_line and line.strip() == 'Verification failed')
pattern = re.compile(r'^(\d+)\. \((\d+),(\d+),(\d+)\) (\S+) Hist: (\d+) Tile Name: (\S+) Node: (\S+) Overlapping Nets: (\d+)$')
nodes = []; node = None; mode = None; current_tile = None
for line_number in range(scope_line+1,end_line):
    raw = lines[line_number-1]; text = raw.strip()
    match = pattern.fullmatch(raw)
    if match:
        rank,x,y,z,kind,hist,tile,name,count = match.groups()
        node = dict(sample_id=f'NODE{int(rank):02}',native_rank=int(rank),native_line=line_number,raw_header=raw,
            native_coordinate_tuple=[int(x),int(y),int(z)],node_type=kind,native_hist=int(hist),tile_name=tile,
            node_name=name,device_node_candidate=tile+'/'+name,reported_overlapping_nets=int(count),
            listed_contender_nets=[],nearby_CLB_tiles=[],listed_InstTerms=[])
        nodes.append(node); mode=None;current_tile=None
    elif text == 'Nets:': mode='nets'
    elif text == 'CLB Tiles:': mode='tiles'
    elif text == 'InstTerms:': mode='instterms'
    elif node and text:
        if mode == 'nets': node['listed_contender_nets'].append(dict(native_line=line_number,net_name=text,raw_line=raw))
        elif text.startswith(('CLEM_','CLEL_')):
            current_tile=text;node['nearby_CLB_tiles'].append(dict(native_line=line_number,tile_name=text));mode='tiles'
        elif mode == 'instterms': node['listed_InstTerms'].append(dict(native_line=line_number,InstTerm=text,nearby_CLB_tile=current_tile,raw_line=raw))
assert len(nodes)==10 and [n['native_rank'] for n in nodes]==list(range(1,11))
assert all(n['reported_overlapping_nets']==4 and len(n['listed_contender_nets'])==4 for n in nodes)
unique = {}; occurrences=defaultdict(list)
for node in nodes:
    for item in node['listed_contender_nets']:
        name=item['net_name'];unique.setdefault(name,f'NET{len(unique)+1:03}')
        item['target_id']=unique[name]
        occurrences[name].append(dict(sample_id=node['sample_id'],node_native_line=node['native_line'],net_native_line=item['native_line']))
targets=[dict(target_id=key,net_name=name,exact_name_required=True,occurrences=occurrences[name]) for name,key in unique.items()]
assert len(targets)==40 and sum(len(n['listed_InstTerms']) for n in nodes)==12
source_identity=dict(path=str(SOURCE),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
record=dict(schema='E006_A007_exact_route_failure_sample_targets_v1',recorded_utc=datetime.now(timezone.utc).isoformat(),
    source=source_identity,audited_copy=dict(path=str(AUDITED),bytes=len(data),sha256=source_identity['sha256']),
    source_scope=dict(native_line=scope_line,raw=lines[scope_line-1],slice_end_exclusive_native_line=end_line,
        native_description='tool-selected top10 overlapping physical nodes, up to5 contenders per node; this source lists4 each'),
    counts=dict(nodes=10,net_occurrences=40,unique_exact_net_names=40,duplicate_net_occurrences=0,nearby_InstTerms=12),
    nodes=nodes,unique_contender_nets=targets,
    intended_query_scope='exact40 net names plus10 native device tiles/node identifiers in authorized own physopt DCP session; no full failed-route graph scan',
    query_phase=dict(name='original E005 closed physopt',checkpoint=str(ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/physopt.dcp'),
        expected_bytes=579969232,expected_sha256='766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d'),
    limits=['Samples originate from failed route; physopt is earlier. Unresolved route-generated net names must remain NOT_FOUND, never silently renamed.',
        'Preserve literal brackets and slashes; native Nets entries such as /DOA0 and /P[22] remain exact net-name candidates, not automatically recast as pins.',
        'InstTerms are nearby primitive-pin context, not additional contender nets and not proven associated one-to-one with listed nets.',
        'Raw header coordinate tuple is not interpreted as GRID_POINT or SLICE coordinates. Map tile/SLR using actual device API.',
        'Top10 selection and max5 list are bounded tool samples, not full overlap distribution or globally representative nets.',
        '40 unique names are exact string deduplication, not yet native canonical logical-net deduplication.',
        'Physopt endpoint relations cannot establish that a net occupies a failed-route node in the earlier graph; failed-log membership is the original evidence.',
        'Density/window co-location and sampled contention support association, not sole cause or per-RTL/SSI causal separation.'])
path=OUT/'route_failure_sample_targets.json'
with path.open('x') as stream:json.dump(record,stream,ensure_ascii=False,indent=2);stream.write('\n')
print(json.dumps(dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),counts=record['counts'],source=source_identity),ensure_ascii=False,indent=2))
