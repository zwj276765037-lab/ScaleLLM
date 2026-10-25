#!/usr/bin/env python3
"""M006 GU-only v7 root-bound source identity; leaves historical M003 locks intact."""
import argparse,ast,hashlib,json,re,sys
from pathlib import Path
HW=Path(__file__).resolve().parents[2]
ROOT=HW.parents[1]
MANIFEST=HW/'vivado/manifests/mlp_gu_only/board.list'
FREEZE=HW/'vivado/manifests/mlp_gu_only/input_manifest.json'
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
 for p in [HW/'source/mlp_gu_only/debug_endpoint_reference.json',HW/'source/mlp_linear/abi_gu_only.json',HW/'vivado/scripts/generate_mlp_gu_csr.py',HW/'rtl/integration/hap_mlp_axil_control.sv',HW/'host/scalellm_mlp_gu_only_abi.py',Path(__file__).resolve(),HW/'vivado/scripts/create_mlp_gu_board.tcl',HW/'vivado/scripts/build_mlp_gu_board.tcl',HW/'vivado/scripts/run_mlp_gu_board.py',HW/'vivado/scripts/run_mlp_gu_sim.py',HW/'vivado/scripts/run_mlp_gu_syntax.py',HW/'vivado/scripts/m006_system_python.tcl',HW/'vivado/constraints/mlp_linear_physical.xdc',HW/'vivado/constraints/attention_mlp_vcu118_board_v5.xdc',HW/'vivado/constraints/vcu118_ddr4_explicit_pins.xdc',HW/'vivado/constraints/board_clock_domains.xdc',HW/'vivado/constraints/ddr_timing_recovery.xdc']:visit(p)
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
 forbidden=['hap_mlp_full_command','hap_mlp_serial_ddr_command','hap_mlp_input_frontend','hap_mlp_hadamard','hap_mlp_swiglu','hap_mlp_silu_mul','hap_mlp_robust_a8_quantizer','hap_mlp_product_frontend','hap_mlp_linear_compute16_s54','hap_mlp_shared_dual_slice16x12_s44_s54','hap_a8w4_group32_lane2_s45','hap_a8w4_slice8x12_group_s45','hap_mlp_tile_accum_s45_s54','hap_mlp_linear_down_scheduler','hap_mlp_down_scheduler','hap_mlp_projection_repack12_to16_s32']
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
 """Static source binding; actual hierarchy and resources are checked natively."""
 expected=dict(INTERMEDIATE_COLUMNS=14336,HIDDEN_COLUMNS=4096,ENFORCE_PRODUCTION_SHAPE=1)
 files={"production":"rtl/integration/hap_attention_mlp_production_core_gu_only.sv", "resource":"rtl/integration/hap_attention_mlp_resource_top_gu_only.sv", "compute":"rtl/mlp/hap_mlp_gu_compute16_s44.sv"}
 texts={key:re.sub(r"//[^\n]*|/\*.*?\*/", "", (HW/rel).read_text(),flags=re.S) for key,rel in files.items()}
 defaults={}
 for key,text in texts.items():
  header=text.split(") (",1)[0] if ") (" in text else text.split("input",1)[0]
  defaults[key]={}
  for name,value in expected.items():
   found=re.search(r"\b"+name+r"\s*=\s*(\d+)\b",header)
   if not found or int(found[1])!=value:raise ValueError(f"production default mismatch {key}.{name}")
   defaults[key][name]=int(found[1])
 if not re.search(r"parameter\s+integer\s+HIDDEN_GROUPS\s*=\s*128\b",texts['compute']):raise ValueError('GU input K must be128groups')
 wrapper=(HW/'rtl/integration/hap_attention_mlp_board_core_gu_only.sv').read_text()
 bindings=instance_parameters(wrapper,'hap_attention_mlp_production_core_gu_only','u_core')
 if {k:constant_expression(bindings[k],{}) for k in expected}!=expected:raise ValueError('board production shape changed')
 for key,child,instance in [('production','hap_attention_mlp_resource_top_gu_only','u_compute'),('resource','hap_mlp_gu_compute16_s44','u_mlp')]:
  bindings=instance_parameters(texts[key],child,instance)
  if any(bindings.get(k)!=k for k in expected):raise ValueError('production shape not propagated: '+key)
 derived={'GATE_SOURCE_RECORDS':1792}
 match=re.search(r"parameter\s+integer\s+GATE_SOURCE_RECORDS\s*=\s*([^,]+)",texts['compute'].split(') (',1)[0])
 if not match or constant_expression(match[1].strip(),expected)!=1792:raise ValueError('GU source records mismatch')
 chain={}
 for module,instance in [('hap_mlp_gu_job_control','u_job'),('hap_mlp_gu_tensor_dma','u_tensor')]:
  binding=instance_parameters(texts['production'],module,instance)
  wanted={'GU_OUTPUT_RECORDS':1792,'ENFORCE_PRODUCTION_SHAPE':1}
  chain[instance]={k:constant_expression(binding[k],expected) for k in wanted}
  if chain[instance]!=wanted:raise ValueError('GU output count mismatch: '+instance)
 for module,instance in [('hap_mlp_gu_metadata_scheduler','u_meta_sched'),('hap_mlp_gu_weight_meta_resident_ab','u_meta_bank'),('hap_mlp_gu_meta_dma_loader','u_meta_dma')]:
  binding=instance_parameters(texts['production'],module,instance)
  wanted={'GATE_DEPTH' if instance=='u_meta_bank' else 'GATE_RECORDS':229376,'PRODUCTION_SHAPE':1}
  chain[instance]={k:constant_expression(binding[k],expected) for k in wanted}
  if chain[instance]!=wanted:raise ValueError('GU metadata count mismatch: '+instance)
 cache=(HW/'rtl/mlp/hap_mlp_gu_cache16.sv').read_text()
 if not re.search(r'reg\s*\[279:0\]\s*memory\[0:127\]',cache):raise ValueError('cache must declare128groups of280bits perrow')
 if 'wr_group<128' not in cache or 'rd_req_group<128' not in cache or 'write_count<128' not in cache:raise ValueError('cache must validate full9bit indices before truncation')
 lane=(HW/'rtl/mlp/hap_a8w4_gu_group32_lane2_s37.sv').read_text()
 for name in ['guard0_mem','guard1_mem']:
  if not re.search(r'reg signed \[36:0\] '+name+r' \[0:GUARD_DEPTH-1\]',lane):raise ValueError('native guard payload source must be37bits')
 return dict(scope='static bound source; native hierarchy/resources independently required',defaults=defaults,derived_compute=derived,production_child_parameters=chain,gu_output_records=1792,gu_metadata_records=229376,gu_input_bytes=73728,gu_output_bytes=1376256,cache_groups=128,cache_row_bits=280,guard_bits=37,expected_mlp_dsps=3072,expected_gu_metadata_uram=448,down_hardware='statically_removed',parameter_values_source='static_bound_source',actual_elaboration_parameters='unavailable')

def main():
 a=argparse.ArgumentParser();a.add_argument('action',choices=['freeze','check','list-sources','shape']);o=a.parse_args();paths=closure();check_graph(paths);shape=production_shape()
 if o.action=='shape':print(json.dumps(shape,indent=2));return
 payload=dict(selected_hdl=[str(p.relative_to(HW)) for p in selected_hdl()],production_shape=shape,mission='M006_GU_ONLY_V7',root=str(ROOT),hardware_root=str(HW),baseline_commit='0c0d2cdba00ef8e91cc96e678ca4e0b68c4cda60',source_manifest=str(MANIFEST.relative_to(HW)),attention_baseline_sha256=sha(ROOT/'mission/M006_mlp_linear_only_hardware/attention_baseline.json'),files={str(p.relative_to(HW)):sha(p) for p in paths})
 if o.action=='freeze':FREEZE.write_text(json.dumps(payload,indent=2)+'\n');print('M006_INPUT_FROZEN',len(paths));return
 old=json.loads(FREEZE.read_text())
 if old!=payload:raise ValueError('M006 current inputs differ from freeze; create a reviewed new freeze before running')
 if o.action=='list-sources':print('\n'.join(str(p) for p in paths))
 else:print('M006_INPUT_CHECK_PASS',len(paths))
if __name__=='__main__':main()
