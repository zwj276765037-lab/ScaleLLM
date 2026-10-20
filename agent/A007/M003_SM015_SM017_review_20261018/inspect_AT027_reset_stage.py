"""Read only bounded actual AT027 reset table; never infer buffered rows or G4."""
from pathlib import Path
import hashlib,json,tkinter
ROOT=Path.cwd();RP=ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT027_reset_semantics_postreport_recovery';OWN=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
trace=RP/'m003_connection_synth_trace.jsonl'
if not trace.exists():print(json.dumps(dict(ready=False,reason='native trace not created')));raise SystemExit(0)
assert trace.stat().st_size<262144
tr=[]
for line in trace.read_text().splitlines():
 try:tr.append(json.loads(line))
 except ValueError:pass
markers=[x for x in tr if x.get('event')=='reset_provenance_complete']
if not markers:print(json.dumps(dict(ready=False,reason='actual native reset completion marker pending')));raise SystemExit(0)
paths=[RP/'m003_stream_synth_reset_provenance.jsonl',RP/'m003_stream_synth_reset_provenance.jsonl.partial'];p=next((x for x in paths if x.exists()),None)
if not p:print(json.dumps(dict(ready=False,reason='native reset table not on disk',markers=markers)));raise SystemExit(0)
assert p.stat().st_size<2**20;raw=p.read_bytes();rows=[];partial=False
for line in raw.splitlines():
 try:rows.append(json.loads(line))
 except ValueError:partial=True
if not rows or rows[-1].get('kind')!='complete':print(json.dumps(dict(ready=False,reason='actual table remains buffered/incomplete',bytes=len(raw),complete_rows=len(rows),partial_line=partial,markers=markers)));raise SystemExit(0)
assert not partial
T=tkinter.Tcl();words=lambda x:list(T.splitlist(x));groups={r['id']:r for r in rows if r['kind']=='group'};eps=[r for r in rows if r['kind']=='endpoint'];nodes=[r for r in rows if r['kind']=='node'];inputs=[r for r in rows if r['kind']=='input'];roots=[r for r in rows if r['kind']=='root'];done=rows[-1]
assert len(rows)==63 and len(roots)==1 and len(groups)==4 and len(eps)==51 and len(nodes)==3 and len(inputs)==3
assert done==dict(kind='complete',endpoints='51',nodes='3',input_pins='3',groups='4')
expected={(f,str(s),str(b)) for f,s in [('core',-1),('helper',0),('helper',1)] for b in range(17)};assert {(x['family'],x['slice'],x['bit']) for x in eps}==expected
projection=ROOT/'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT025_boundary_sources_postreport_recovery/evidence/AT025_actual_reset_comparison_projection.json';prior=json.loads(projection.read_text());old_eps={x['NAME']:x for x in prior['core_address_FF']+prior['helper_address_FF']};seen=set()
for gid,g in groups.items():
 ns=words(g['nets']);assert len(ns)==int(g['actual_segment_count'])==len(set(ns)) and all(ns) and not(set(ns)&seen);seen.update(ns);assert g['direct_net'] in ns
 assert len(words(g['leaf_drivers']))==1 and not words(g['primary_ports']) and words(g['source_directions'])==['OUT']
root=roots[0];rg=root['group'];root_names=set(words(groups[rg]['nets']));assert root_names==set(prior['unique_native_NAME_groups']['RESET_NET_3']['names'])
assert root['direction']=='OUT' and root['anchor'] in root_names and words(groups[rg]['leaf_drivers'])==[root['actual_source']]
for ep in eps:
 old=old_eps[ep['cell']];assert ep['REF_NAME']==old['REF_NAME']=='FDCE' and ep['INIT']=="1'b0" and ep['IS_CLR_INVERTED']=='' and ep['pin_IS_INVERTED']=='0';assert ep['CLR_pin']==ep['cell']+'/CLR';assert set(words(groups[ep['group']]['nets']))==set(prior['unique_native_NAME_groups'][old['CLR_group']]['names'])
for n in nodes:
 assert n['REF_NAME']=='LUT1' and n['INIT']=="2'h1" and n['output_pin']==n['cell']+'/O' and n['output_direction']=='OUT';assert words(groups[n['output_group']]['leaf_drivers'])==[n['output_pin']]
 ins=[x for x in inputs if x['cell']==n['cell']];assert len(ins)==1 and ins[0]['pin']=='I0' and ins[0]['actual_pin']==n['cell']+'/I0' and ins[0]['direction']=='IN' and ins[0]['group']==rg
print(json.dumps(dict(ready=True,path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),rows=len(rows),endpoints=len(eps),nodes=nodes,root=root,groups=[dict(id=k,count=v['actual_segment_count']) for k,v in groups.items()],scope='Actual fulltop51 raw reset table and source mapping only; complete structure/budget/G4 not implied',G4=False),ensure_ascii=False))
