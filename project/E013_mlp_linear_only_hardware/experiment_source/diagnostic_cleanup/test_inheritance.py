#!/usr/bin/env python3
"""Isolated provenance guard tests; no Vivado and no production-file edits."""
import argparse, copy, difflib, hashlib, json, re, tempfile
from pathlib import Path

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n' if not isinstance(value,str) else value)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('driver',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    import ast
    source=a.driver.read_text(); tree=ast.parse(source)
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_diagnostic_inheritance')
    namespace=dict(Path=Path,json=json,re=re,difflib=difflib,sha=sha)
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(a.driver),'exec'),namespace)
    results=[]
    cases=['valid','rtl_change','membership_change','shape_change','constraint_semantics','parent_snapshot','parent_manifest','parent_faulted_result','owned_survivor','foreign_dcp_identity','driver_patch_changed','record_identity','outside_scope']
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='m006-inheritance-') as d:
            root=Path(d);hw=root/'project/hardware';scope=root/'project/E013_mlp_linear_only_hardware/experiment_source/diagnostic_cleanup'
            parent=root/'project/E013_mlp_linear_only_hardware/experiment_results/runs/R003/attempts/AT004_fixture';scope.mkdir(parents=True)
            manifest=hw/'vivado/manifests/mlp_linear/input_manifest.json';constructor=hw/'vivado/project/example/m006_constructor_identity.json'
            xdc=['vivado/constraints/ddr_timing_recovery.xdc','vivado/constraints/mlp_linear_physical.xdc'];driver='vivado/scripts/run_mlp_linear_board.py';rtl='rtl/example.sv'
            old_files={xdc[0]:'# retained\nputs {INFO: literal diagnostic}\n',xdc[1]:'# retained other\nputs {INFO: other diagnostic}\n',driver:'# parent runner\n',rtl:'module example; endmodule\n'}
            new_files={**old_files,xdc[0]:'# retained\n',xdc[1]:'# retained other\n',driver:'# current runner with provenance gate\n'}
            for rel,text in old_files.items():put(parent/'source_snapshot'/rel,text)
            for rel,text in new_files.items():put(hw/rel,text)
            old=dict(files={r:sha(parent/'source_snapshot'/r) for r in old_files},selected_hdl=[rtl],production_shape={'N':14336},root=str(root))
            put(parent/'input_manifest.json',old);current=copy.deepcopy(old)
            current['files']={r:sha(hw/r) for r in new_files};put(manifest,current)
            put(constructor,'constructor fixture\n')
            dcp=hw/'vivado/reports/parent/synthesized.dcp';put(dcp,'DCP fixture; not native hardware evidence\n')
            receipt=dict(input_manifest_sha256=sha(parent/'input_manifest.json'),synth_evidence=str(parent),dcp=str(dcp),dcp_sha256=sha(dcp))
            put(dcp.parent/'m006_synth_identity.json',receipt)
            put(parent/'result.json',dict(verdict='NATIVE_STAGE_COMPLETED',native_returncode=0,stop_reason=None,changed_inputs=[]))
            put(parent/'owned_processes.json',dict(survivors=[]))
            patch=scope/'driver.patch';put(patch,''.join(difflib.unified_diff(old_files[driver].splitlines(True),new_files[driver].splitlines(True),fromfile='parent/run_mlp_linear_board.py',tofile='current/run_mlp_linear_board.py')))
            def record():
                put(manifest,current)
                return dict(schema=1,scope='impl_diagnostic_cleanup_only',parent_input_manifest_sha256=receipt['input_manifest_sha256'],current_input_manifest_sha256=sha(manifest),parent_synth_receipt_sha256=sha(dcp.parent/'m006_synth_identity.json'),constructor_sha256=sha(constructor),dcp_sha256=receipt['dcp_sha256'],changes={r:dict(parent_sha256=h,current_sha256=current['files'][r]) for r,h in old['files'].items() if h!=current['files'].get(r)},driver_patch='driver.patch',driver_patch_sha256=sha(patch))
            if case=='rtl_change':put(hw/rtl,'module changed; endmodule\n');current['files'][rtl]=sha(hw/rtl)
            if case=='membership_change':current['files']['rtl/new.sv']='f'*64
            if case=='shape_change':current['production_shape']['N']=128
            if case=='constraint_semantics':put(hw/xdc[0],'# retained\nset_false_path -from [all_registers]\n');current['files'][xdc[0]]=sha(hw/xdc[0])
            data=record();path=scope/'inheritance.json'
            if case=='parent_snapshot':put(parent/'source_snapshot'/xdc[0],'changed parent source\n')
            if case=='parent_manifest':put(parent/'input_manifest.json','{}\n')
            if case=='parent_faulted_result':put(parent/'result.json',dict(verdict='NATIVE_STAGE_COMPLETED',native_returncode=0,stop_reason='resource_protection',changed_inputs=[]))
            if case=='owned_survivor':put(parent/'owned_processes.json',dict(survivors=[123]))
            if case=='foreign_dcp_identity':data['dcp_sha256']='0'*64
            if case=='driver_patch_changed':put(patch,'unrecorded patch\n')
            if case=='record_identity':data['current_input_manifest_sha256']='0'*64
            if case=='outside_scope':path=root/'outside.json'
            put(path,data);namespace.update(ROOT=root,HW=hw,INPUTS=manifest)
            try:
                namespace['validate_diagnostic_inheritance'](path,receipt,constructor,sha(manifest));accepted=True;reason='accepted'
            except ValueError as e:accepted=False;reason=str(e)
            expected=(case=='valid');results.append(dict(case=case,accepted=accepted,expected_accepted=expected,pass_check=accepted==expected,reason=reason))
    outcome=dict(scope='isolated CPU provenance helper tests, synthetic fixtures only; no EDA',driver=str(a.driver.resolve()),driver_sha256=sha(a.driver),test_source_sha256=sha(Path(__file__)),checks=results,verdict='PASS' if all(r['pass_check'] for r in results) else 'FAIL')
    put(a.output,outcome);print(json.dumps(outcome));return 0 if outcome['verdict']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
