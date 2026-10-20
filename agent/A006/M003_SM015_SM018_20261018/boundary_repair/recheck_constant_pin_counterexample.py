from pathlib import Path
import copy,datetime,hashlib,importlib.machinery,importlib.util,json,sys,tkinter
ROOT=Path.cwd();OWN=ROOT/'agent/A006/M003_SM015_SM018_20261018/boundary_repair/reset_semantics_application_evidence';P=ROOT/'agent/A006/M003_SM015_SM018_20261018/boundary_repair/m003_joint_evidence.reset_semantics.py.proposed';sys.path.insert(0,str(ROOT/'project/hardware/vivado/scripts'));before=P.read_bytes()
loader=importlib.machinery.SourceFileLoader('a007_constant_check',str(P));sp=importlib.util.spec_from_loader(loader.name,loader);E=importlib.util.module_from_spec(sp);loader.exec_module(E)
raw=[json.loads(x) for x in (ROOT/'project/hardware/vivado/reports/m003_E011_R002_AT026_fresh_core_reset_provenance/reset_provenance.jsonl').read_text().splitlines()];tcl=tkinter.Tcl();groups={x['id']:x for x in raw if x['kind']=='group'};originals=[dict(NAME=e['cell'],REF_NAME=e['REF_NAME'],bit=e['bit'],CLR_nets=groups[e['group']]['nets']) for e in raw if e['kind']=='endpoint' and e['family']=='core'];helpers=[dict(NAME=e['cell'],REF_NAME=e['REF_NAME'],bit=e['bit'],slice=e['slice'],CLR_nets=groups[e['group']]['nets']) for e in raw if e['kind']=='endpoint' and e['family']=='helper'];sources={'reset':set(tcl.splitlist(groups['R1']['nets']))}
def errors(rows):
 out=[];E.validate_native_reset({'reset_provenance':rows},originals,helpers,sources,lambda ok,msg:out.append(msg) if not ok else None);return out
cases=[];samples=[]
for ref,pin,truth in [('GND','G',"4'h1"),('VCC','P',"4'h4")]:
 rows=copy.deepcopy(raw);node=next(x for x in rows if x['kind']=='node' and x['output_group']=='R2');node.update(REF_NAME='LUT2',INIT=truth);rows.extend([dict(kind='group',id='CONST',actual_segment_count='1',nets='const_net',direct_net='const_net',leaf_drivers='const_cell/'+pin,primary_ports='',source_directions='OUT'),dict(kind='node',cell='const_cell',REF_NAME=ref,INIT='NOT_SUPPORTED',output_pin='const_cell/'+pin,output_direction='OUT',output_group='CONST'),dict(kind='input',cell=node['cell'],pin='I1',actual_pin=node['cell']+'/I1',direction='IN',group='CONST')]);next(x for x in rows if x['kind']=='complete').update(nodes='4',input_pins='4',groups='5');cases.append(dict(constant=ref,native_output=pin,expected='NOT(root) for both values, with native GND/G or VCC/P constant as I1',errors=errors(rows)));samples.append(copy.deepcopy(rows))
assert all(not c['errors'] for c in cases), cases
negatives=[]
for sample in samples:
 bad=copy.deepcopy(sample)
 node=next(n for n in bad if n['kind']=='node' and n['cell']=='const_cell');node['output_pin']='const_cell/O'
 next(g for g in bad if g['kind']=='group' and g['id']=='CONST')['leaf_drivers']='const_cell/O'
 result=errors(bad);assert result;negatives.append(dict(case='fake_O_for_'+node['REF_NAME'],errors=result))
bad=copy.deepcopy(raw);node=next(n for n in bad if n['kind']=='node' and n['output_group']=='R2');node.update(REF_NAME='GND',INIT='NOT_SUPPORTED',output_pin=node['cell']+'/G');next(g for g in bad if g['kind']=='group' and g['id']=='R2')['leaf_drivers']=node['output_pin'];bad=[z for z in bad if not(z['kind']=='input' and z['cell']==node['cell'])];next(z for z in bad if z['kind']=='complete')['input_pins']='2';result=errors(bad);assert result;negatives.append(dict(case='direct_GND_CLR',errors=result))
assert P.read_bytes()==before
out=dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=dict(path=str(P.relative_to(ROOT)),bytes=len(before),sha256=hashlib.sha256(before).hexdigest()),cases=cases,verdict='Current all-nodes cell/O owner check rejects native GND/G and VCC/P before constant evaluation. Conservative false rejection, not unsafe acceptance; current measured3LUT1 has no constants.',suggestion='Either explicitly narrow documented supported cones to3direct INV, or validate primitive-specific native output REF_PIN_NAME (LUT/O,GND/G,VCC/P) and permit constants only when full effective truth still matches NOT(root).')
out['fixed']=True;out['negative_cases']=negatives;out['verdict']='Native GND/G and VCC/P accepted only through proven NOT(root) cones; fake pin and constant CLR rejected.'
p=OWN/'constant_pin_counterexample_recheck.json';p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False));print(json.dumps(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())))
