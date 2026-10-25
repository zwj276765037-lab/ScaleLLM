#!/usr/bin/env python3
"""M006-only root-bound source identity; leaves historical M003 locks intact."""
import argparse,ast,hashlib,json,re,sys
from pathlib import Path
HW=Path(__file__).resolve().parents[2]
ROOT=HW.parents[1]
MANIFEST=HW/'vivado/manifests/mlp_linear/board.list'
FREEZE=HW/'vivado/manifests/mlp_linear/input_manifest.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def closure():
 out=set()
 def visit(p):
  p=p.resolve()
  if not p.is_relative_to(HW) or not p.is_file():raise ValueError(f'input outside new root or missing: {p}')
  if p in out:return
  out.add(p)
  if p.suffix=='.list':
   for l in p.read_text().splitlines():
    l=l.split('#',1)[0].strip()
    if l:visit(HW/l)
 visit(MANIFEST)
 for p in [HW/'source/mlp_linear/abi.json',HW/'vivado/scripts/generate_mlp_linear_csr.py',HW/'rtl/integration/hap_mlp_axil_control.sv',HW/'rtl/integration/hap_mlp_linear_abi.svh',HW/'host/scalellm_mlp_linear_abi.py',Path(__file__).resolve(),HW/'vivado/scripts/create_mlp_linear_board.tcl',HW/'vivado/scripts/build_mlp_linear_board.tcl',HW/'vivado/scripts/run_mlp_linear_board.py',HW/'vivado/scripts/run_mlp_linear_sim.py',HW/'vivado/scripts/m006_system_python.tcl',HW/'vivado/constraints/mlp_linear_physical.xdc',HW/'vivado/constraints/attention_mlp_vcu118_board_v5.xdc',HW/'vivado/constraints/vcu118_ddr4_explicit_pins.xdc',HW/'vivado/constraints/board_clock_domains.xdc',HW/'vivado/constraints/ddr_timing_recovery.xdc']:visit(p)
 return sorted(out)
def selected_hdl():
 selected=set();visited=set()
 def visit(path):
  path=path.resolve()
  if path in visited:return
  if not path.is_relative_to(HW) or not path.is_file():raise ValueError('selected input missing/outside new root: '+str(path))
  visited.add(path)
  if path.suffix=='.list':
   for raw in path.read_text().splitlines():
    line=raw.split('#',1)[0].strip()
    if line:visit(HW/line)
  elif path.suffix in {'.v','.sv'}:selected.add(path)
 visit(MANIFEST)
 return sorted(selected)

def check_graph(paths):
 forbidden=['hap_mlp_full_command','hap_mlp_serial_ddr_command','hap_mlp_input_frontend','hap_mlp_hadamard','hap_mlp_swiglu','hap_mlp_silu_mul','hap_mlp_robust_a8_quantizer','hap_mlp_product_frontend']
 for p in paths:
  if p.parent==HW/'rtl/mlp' and any(p.name.startswith(n) for n in forbidden):raise ValueError('nonlinear/full MLP in production graph: '+str(p))
 att=json.loads((ROOT/'mission/M006_mlp_linear_only_hardware/attention_baseline.json').read_text())
 for rel,h in att["files_sha256"].items():
  q=HW/rel
  if not q.is_file() or sha(q)!=h:raise ValueError("Attention baseline mismatch: "+rel)
 return att

def constant_expression(text,values):
 node=ast.parse(text.replace('/','//'),mode='eval').body
 def value(n):
  if isinstance(n,ast.Constant) and type(n.value) is int:return n.value
  if isinstance(n,ast.Name) and n.id in values:return values[n.id]
  if isinstance(n,ast.BinOp):
   left,right=value(n.left),value(n.right)
   if isinstance(n.op,ast.Add):return left+right
   if isinstance(n.op,ast.Sub):return left-right
   if isinstance(n.op,ast.Mult):return left*right
   if isinstance(n.op,ast.FloorDiv):return left//right
  raise ValueError('unsupported shape expression: '+text)
 return value(node)

def instance_parameters(text,module,instance):
 match=re.search(r"\b"+module+r"\s*#\s*\((.*?)\)\s*"+instance+r"\s*\(",text,re.S)
 if not match:raise ValueError('missing parameterized instance: '+instance)
 body=match[1];result={};offset=0
 while offset<len(body):
  name=re.search(r"\.(\w+)\s*\(",body[offset:])
  if not name:break
  start=offset+name.end();end=start;depth=1
  while depth and end<len(body):
   depth+=(body[end]=='(')-(body[end]==')');end+=1
  if depth:raise ValueError('unbalanced shape parameter '+instance)
  result[name[1]]=re.sub(r"\s+","",body[start:end-1]);offset=end
 return result

def production_shape():
 """Fail closed on the three production defaults and the board propagation chain."""
 expected=dict(INTERMEDIATE_COLUMNS=14336,HIDDEN_COLUMNS=4096,ENFORCE_PRODUCTION_SHAPE=1)
 files={"production":"rtl/integration/hap_attention_mlp_production_core_linear.sv",
        "resource":"rtl/integration/hap_attention_mlp_resource_top_linear.sv",
        "compute":"rtl/mlp/hap_mlp_linear_compute16_s54.sv"}
 texts={key:re.sub(r"//[^\n]*|/\*.*?\*/", "", (HW/rel).read_text(),flags=re.S) for key,rel in files.items()}
 defaults={}
 for key,text in texts.items():
  header=text.split(") (",1)[0] if ") (" in text else text.split("input",1)[0]
  defaults[key]={}
  for name,value in expected.items():
   found=re.search(r"\b"+name+r"\s*=\s*(\d+)\b",header)
   if not found or int(found[1])!=value:raise ValueError(f"production default mismatch {key}.{name}")
   defaults[key][name]=int(found[1])
 for name,value in {"HIDDEN_GROUPS":128,"DOWN_GROUPS":448}.items():
  found=re.search(r"parameter\s+integer\s+"+name+r"\s*=\s*(\d+)",texts["compute"])
  if not found or int(found[1])!=value:raise ValueError("production input K mismatch: "+name)
  defaults["compute"][name]=value
 wrapper=re.sub(r"//[^\n]*|/\*.*?\*/", "", (HW/'rtl/integration/hap_attention_mlp_board_core_linear.sv').read_text(),flags=re.S)
 bound=re.search(r"\bhap_attention_mlp_production_core\s*#\s*\((.*?)\)\s*u_core\s*\(",wrapper,re.S)
 if not bound:raise ValueError("board must instantiate explicit production shape")
 for name,value in expected.items():
  if not re.search(r"\."+name+r"\s*\(\s*"+str(value)+r"\s*\)",bound[1]):raise ValueError("board production shape mismatch: "+name)
 for key,child,instance in [("production","hap_attention_mlp_resource_top","u_compute"),("resource","hap_mlp_linear_compute16_s54","u_mlp")]:
  match=re.search(r"\b"+child+r"\s*#\s*\((.*?)\)\s*"+instance+r"\s*\(",texts[key],re.S)
  if not match:raise ValueError("missing shape propagation: "+key)
  for name in expected:
   if not re.search(r"\."+name+r"\s*\(\s*"+name+r"\s*\)",match[1]):raise ValueError("shape propagation mismatch: "+key+"."+name)
  if key=="resource" and not re.search(r"\.DOWN_GROUPS\s*\(448\)",match[1]):raise ValueError("Down input K must remain448")
 derived={"GATE_SOURCE_RECORDS":1792,"DOWN_SOURCE_RECORDS":256,"DOWN_OUTPUT_RECORDS":256,"DOWN_COMPUTE_TILES":342}
 compute_header=texts['compute'].split(') (',1)[0]
 for name,wanted in derived.items():
  match=re.search(r"parameter\s+integer\s+"+name+r"\s*=\s*([^,]+)",compute_header)
  if not match or constant_expression(match[1].strip(),{**expected,**derived})!=wanted:raise ValueError('compute derived shape mismatch: '+name)
 chain={}
 for module,instance in [('hap_mlp_linear_job_control','u_job'),('hap_mlp_linear_tensor_dma','u_tensor')]:
  bindings=instance_parameters(texts['production'],module,instance)
  wanted={'GU_OUTPUT_RECORDS':1792,'DOWN_OUTPUT_RECORDS':256,'ENFORCE_PRODUCTION_SHAPE':1}
  chain[instance]={name:constant_expression(bindings[name],expected) for name in wanted}
  if chain[instance]!=wanted:raise ValueError('output count propagation mismatch: '+instance)
 for module,instance in [('hap_mlp_linear_metadata_scheduler','u_meta_sched'),('hap_mlp_weight_meta_resident_ab','u_meta_bank'),('hap_mlp_meta_dma_loader','u_meta_dma')]:
  bindings=instance_parameters(texts['production'],module,instance)
  wanted={'GATE_RECORDS' if instance!='u_meta_bank' else 'GATE_DEPTH':229376,'DOWN_RECORDS' if instance!='u_meta_bank' else 'DOWN_DEPTH':114688,'PRODUCTION_SHAPE':1}
  chain[instance]={name:constant_expression(bindings[name],expected) for name in wanted}
  if chain[instance]!=wanted:raise ValueError('metadata count propagation mismatch: '+instance)
 return dict(scope="static production defaults and explicit propagation; not dynamic elaboration",defaults=defaults,derived_compute=derived,production_child_parameters=chain,gu_output_records=1792,down_output_records=256,gu_metadata_records=229376,down_metadata_records=114688,gu_input_bytes=73728,down_input_bytes=258048,gu_output_bytes=1376256,down_output_bytes=262144)

def main():
 a=argparse.ArgumentParser();a.add_argument('action',choices=['freeze','check','list-sources','shape']);o=a.parse_args();paths=closure();check_graph(paths);shape=production_shape()
 if o.action=='shape':print(json.dumps(shape,indent=2));return
 payload=dict(selected_hdl=[str(p.relative_to(HW)) for p in selected_hdl()],production_shape=shape,mission='M006',root=str(ROOT),hardware_root=str(HW),baseline_commit='0c0d2cdba00ef8e91cc96e678ca4e0b68c4cda60',source_manifest=str(MANIFEST.relative_to(HW)),attention_baseline_sha256=sha(ROOT/'mission/M006_mlp_linear_only_hardware/attention_baseline.json'),files={str(p.relative_to(HW)):sha(p) for p in paths})
 if o.action=='freeze':FREEZE.write_text(json.dumps(payload,indent=2)+'\n');print('M006_INPUT_FROZEN',len(paths));return
 old=json.loads(FREEZE.read_text())
 if old!=payload:raise ValueError('M006 current inputs differ from freeze; create a reviewed new freeze before running')
 if o.action=='list-sources':print('\n'.join(str(p) for p in paths))
 else:print('M006_INPUT_CHECK_PASS',len(paths))
if __name__=='__main__':main()
