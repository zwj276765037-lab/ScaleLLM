#!/usr/bin/env python3
"""Mechanical M001 copy and static verification; never launches EDA or tests."""

import argparse
import ast
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess


SOURCE = Path('/home/user/EDA-202/zhuowenjun/ScaleLLM/1_Hardware')
DEST = Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware')
ENTRY_MANIFESTS = (
    'vivado/manifests/attention_mlp_board_core_v5_sources.list',
    'vivado/manifests/attention_mlp_production_v5_cohort16_sources.list',
)
MODEL_FILES = (
    '__init__.py', 'fixbit_v2.py', 'mlp_fixed.py',
    'attention_cohort16_integration_contract.py',
    'attention_two_wave_reuse_contract.py', 'v5_schedule_contract.py',
    'v5_gate_up_gather_contract.py', 'export_scalellm_llama31_artifacts.py',
    'verify_scalellm_real_mlp_artifacts.py', 'freeze_scalellm_workload.py',
    'generate_scalellm_workload_reference.py',
)
TEST_FILES = (
    '__init__.py', 'test_mlp_fixed.py', 'test_rebuild_contract.py',
    'test_attention_cohort16_integration_contract.py',
    'test_attention_two_wave_reuse_contract.py',
    'test_v5_gate_up_gather_contract.py', 'test_v5_schedule_contract.py',
    'test_vcu118_builder_sources.py', 'test_vcu118_builder_rom_staging.py',
)
SCRIPTS = (
    'create_vcu118_board.tcl', 'build_vcu118_board.tcl',
    'run_vcu118_board.sh', 'emit_current_board_evidence.py',
    'audit_attention_mlp_vcu118_v5_post_route.tcl', 'check_rebuild_static.py',
    'run_xsim_tb.sh', 'mission0004_metadata_physical.tcl',
    'mission0005_coordinated_physical.tcl', 'check_mission0005_partition.tcl',
)
CONSTRAINTS = (
    'attention_mlp_vcu118_board_v5.xdc', 'vcu118_ddr4_explicit_pins.xdc',
    'board_clock_domains.xdc', 'mission0004_metadata_width_local.xdc',
    'mission0005_coordinated_partition.xdc',
    'attention_mlp_production_v5_ooc_clocks_100mhz.xdc',
)
TB_STEMS = (
    'hap_attention_mlp_production_v5_joint',
    'hap_attention_mlp_production_v5_cdc',
    'hap_attention_compute_cohort16_top',
    'hap_attention_cohort16_local_stores', 'hap_attention_cohort16_axil_control',
    'hap_tensor24_cohort16_buffers', 'hap_tensor24_output_buffer',
    'hap_mlp_shared_dual_s44_s54_dispatch',
    'hap_mlp_down_group_major_accum_s54_rebuild',
    'hap_mlp_rebuild_recovery', 'hap_mlp_rebuild_minmax_s35',
    'hap_mlp_rebuild_hadamard_s35', 'hap_mlp_rebuild_repack_s32',
    'hap_mlp_rebuild_silu_s32', 'hap_mlp_v5_shift20_recovery',
    'hap_mlp_swiglu_product_frontend16_q4_rebuild_v5',
    'hap_mlp_product_frontend16_q4_rebuild_v5',
    'hap_mlp_tensor_dma_bridge', 'hap_mlp_tensor_dma_bridge_banked_stall',
    'hap_mlp_axil_control', 'hap_mlp_meta_dma_loader',
    'hap_mlp_metadata_scheduler', 'hap_mlp_weight_meta_resident_ab',
    'hap_mlp_launch_readiness_local', 'hap_mlp_metadata_width_local',
    'hap_mlp_metadata_bank_local_capture',
    'hap_mlp_gate_up_gather_pingpong12', 'hap_mlp_w4_repack48_to12',
    'hap_mlp_w4_repack48_to12_throughput',
    'hap_mlp_input_frontend16_compact_cache',
    'hap_a8w4_group32_lane2_s37', 'hap_a8w4_scalecode_recover2_lut',
    'hap_a8w4_pack2_dsp', 'hap_a8w4_pack2_dsp_exhaustive',
    'hap_a8w4_group32_pack2_s17', 'hap_a8w4_group32_pack2_s17_queue',
    'hap_softmax_row_128', 'hap_projection_core16x16_w8_reuse',
    'hap_axi512_paired_2client_read_wrr',
    'hap_axi512_paired_2client_read_wrr_modes',
    'hap_axi512_paired_2client_read_wrr_resets',
    'hap_axi512_paired_2client_read_wrr_enable_cdc',
    'hap_axi512_paired_2client_read_wrr_rebuild_cdc',
    'hap_axi512_paired_2client_read_wrr_rebuild_cdc_fault',
    'hap_axi512_ordered_local_issue_protocol',
    'hap_v4_ddr_mode_controller', 'hap_attention_mlp_axil_router',
)
EVIDENCE_FILES = (
    'worker_final_receipt.txt', 'diagnostic_timing_deltas.tsv',
    'candidate_placed_state.txt',
)


def digest(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_json(name, value):
    path = DEST / 'migration' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def manifest_closure(root):
    manifests, leaves, active = set(), set(), set()

    def visit(name):
        assert name not in active, f'manifest cycle: {name}'
        if name in manifests:
            return
        active.add(name)
        manifests.add(name)
        for line in (root / name).read_text().splitlines():
            fields = shlex.split(line, comments=True)
            if not fields:
                continue
            assert len(fields) == 1, (name, line)
            relative = Path(fields[0])
            assert not relative.is_absolute() and '..' not in relative.parts
            assert (root / relative).is_file() and not (root / relative).is_symlink()
            if relative.suffix == '.list':
                visit(str(relative))
            else:
                leaves.add(str(relative))
        active.remove(name)

    for entry in ENTRY_MANIFESTS:
        visit(entry)
    return manifests, leaves


def source_text(path):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(), flags=re.S)


def selection():
    manifests, leaves = manifest_closure(SOURCE)
    files = manifests | leaves
    files.update(str(p.relative_to(SOURCE)) for p in (SOURCE / 'host').glob('*.py'))
    files.update('model/' + name for name in MODEL_FILES)
    files.update('tests/' + name for name in TEST_FILES)
    files.update(str(p.relative_to(SOURCE)) for p in (SOURCE / 'tests').glob('test_scalellm_*.py'))
    files.update('vivado/scripts/' + name for name in SCRIPTS)
    files.update('vivado/constraints/' + name for name in CONSTRAINTS)
    files.update('tb/' + name + '_tb.sv' for name in TB_STEMS)
    files.add('tb/rebuild_v5_joint_axi_bfm.svh')
    files.add('data/attention_mlp_architecture.json')

    # Add only referenced RTL support and literal include/vector dependencies.
    owners = {}
    for path in (SOURCE / 'rtl').rglob('*'):
        if path.suffix in {'.v', '.sv'}:
            for module in re.findall(r'\bmodule\s+(hap_\w+)\b', source_text(path)):
                owners[module] = str(path.relative_to(SOURCE))
    pending = [name for name in files if Path(name).suffix in {'.v', '.sv', '.svh'}]
    examined = set()
    while pending:
        name = pending.pop()
        if name in examined:
            continue
        examined.add(name)
        content = source_text(SOURCE / name)
        dependencies = {owners[t] for t in re.findall(r'\bhap_\w+\b', content) if t in owners}
        dependencies.update(re.findall(r'`include\s+"([^"]+)"', content))
        for dependency in dependencies - files:
            files.add(dependency)
            pending.append(dependency)
        for literal in re.findall(r'"(data/[^"\n]+)"', content):
            path = SOURCE / literal
            assert 'rebuild_v5_realmodel' not in path.parts
            assert path.exists(), f'missing literal input: {name}: {literal}'
            inputs = [path] if path.is_file() else list(path.rglob('*'))
            files.update(str(p.relative_to(SOURCE)) for p in inputs if p.is_file())
    for name in tuple(files):
        if name.startswith('data/'):
            manifest = SOURCE / Path(name).parent / 'manifest.json'
            if manifest.is_file():
                files.add(str(manifest.relative_to(SOURCE)))
    mapping = {name: name for name in files}
    for name in EVIDENCE_FILES:
        mapping['vivado/reports/mission0008_e2_diagnostic_native_025/' + name] = 'evidence/native025/' + name
    return mapping


def copy():
    assert Path(__file__).resolve().is_relative_to(DEST)
    rows = []
    for source_name, dest_name in sorted(selection().items()):
        source, dest = SOURCE / source_name, DEST / dest_name
        assert source.is_file() and not source.is_symlink(), source
        assert not dest.exists(), f'refusing overwrite: {dest}'
        before = digest(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        assert before == digest(source) == digest(dest), source
        rows.append({'source_relative': source_name, 'destination_relative': dest_name,
                     'source': str(source), 'destination': str(dest),
                     'source_sha256': before, 'source_bytes': source.stat().st_size})
    write_json('source_snapshot.json', {'schema': 1, 'source_root': str(SOURCE),
                                      'destination_root': str(DEST), 'files': rows})
    print(json.dumps({'copied_files': len(rows), 'copied_bytes': sum(r['source_bytes'] for r in rows)}))


def verify():
    snapshot = json.loads((DEST / 'migration/source_snapshot.json').read_text())
    adaptations = json.loads((DEST / 'migration/adaptations.json').read_text())
    allowed = {r['path'] for r in adaptations['files']}
    for adaptation in adaptations['files']:
        old = (SOURCE / adaptation['path']).read_text()
        assert old.count(adaptation['source_text']) == 1
        assert old.replace(adaptation['source_text'], adaptation['destination_text'], 1) == (
            DEST / adaptation['path']).read_text(), 'non-path changes detected'
    old_golden = SOURCE.parent / '0_Software/FPtoQ/experiment/v5_fullchain.py'
    new_golden = DEST.parent / 'software/0_Software/FPtoQ/experiment/v5_fullchain.py'
    assert old_golden.read_bytes() == new_golden.read_bytes()
    assert digest(new_golden) == adaptations['approved_golden_sha256']
    rows = []
    for item in snapshot['files']:
        source, dest = Path(item['source']), Path(item['destination'])
        assert digest(source) == item['source_sha256'], f'source drift: {source}'
        destination_sha = digest(dest)
        changed = destination_sha != item['source_sha256']
        assert changed == (item['destination_relative'] in allowed), dest
        rows.append(dict(item, destination_sha256=destination_sha,
                         destination_bytes=dest.stat().st_size, adapted=changed))
    manifests, leaves = manifest_closure(DEST)
    fresh_inputs = manifests | leaves | {
        'vivado/scripts/' + name for name in (
            'create_vcu118_board.tcl', 'build_vcu118_board.tcl',
            'run_vcu118_board.sh', 'emit_current_board_evidence.py',
            'mission0004_metadata_physical.tcl', 'mission0005_coordinated_physical.tcl')
    } | {'vivado/constraints/' + name for name in CONSTRAINTS}
    for name in fresh_inputs:
        assert (DEST / name).is_file() and digest(DEST / name) == digest(SOURCE / name)
    python_files = sorted(DEST.rglob('*.py'))
    local_imports = 0
    for path in python_files:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                parts = node.module.split('.')
                if parts[0] in {'host', 'model', 'tests', 'vivado'}:
                    member = DEST.joinpath(*parts)
                    assert member.is_dir() or member.with_suffix('.py').is_file(), (
                        path, node.module)
                    local_imports += 1
    shell_files = sorted(DEST.rglob('*.sh'))
    for path in shell_files:
        subprocess.run(['bash', '-n', str(path)], check=True)
    # Tcl only receives strings and uses info complete; no source/eval of inputs.
    tcl_files = sorted(DEST.rglob('*.tcl')) + sorted(DEST.rglob('*.xdc'))
    for path in tcl_files:
        encoded = path.read_bytes().hex()
        program = f'set s [encoding convertfrom utf-8 [binary decode hex {encoded}]]\nif {{![info complete $s]}} {{exit 1}}\n'
        subprocess.run(['tclsh'], input=program, text=True, check=True)
    forbidden = {'__pycache__', '.Xil', 'rebuild_v5_realmodel'}
    assert not any(forbidden.intersection(p.parts) for p in DEST.rglob('*'))
    assert not (DEST / 'vivado/project').exists() and not (DEST / 'vivado/reports').exists()
    spec = importlib.util.spec_from_file_location(
        'migration_static_contract', DEST / 'vivado/scripts/check_rebuild_static.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    contract = checker.audit(
        DEST, checker.DEFAULT_MANIFEST,
        Path('vivado/constraints/attention_mlp_production_v5_ooc_clocks_100mhz.xdc'),
        checker.REQUIRED_DEFINES)
    write_json('contract_check.json', contract)
    external_files = [
        (SOURCE / 'source/design.md', 'full specification authority'),
        (SOURCE / 'source/results.md', 'historical results authority; no qualification transfer'),
        (SOURCE / 'vivado/scripts/run_mission0005_bitgen.sh',
         'NOT MIGRATED: launcher requires same-root routed/audit reports and joint/norm/full32 evidence; frozen inputs not migrated; must not execute against the read-only source tree'),
        (SOURCE / 'vivado/scripts/mission0005_bitgen.tcl',
         'NOT MIGRATED: bitgen requires exact routed DCP/preflight hashes and unchanged signoff gates; not part of fresh create/synth/place/route source closure'),
        (SOURCE / 'vivado/scripts/mission0005_post_route_gate.py',
         'NOT MIGRATED: acceptance binds historical golden-source identities and real joint/norm/full32 evidence; M001 does not rewrite or requalify that flow'),
    ]
    board = Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/data/xhub/boards/XilinxBoardStore/boards/Xilinx/vcu118/2.0')
    external_files.extend((board / name, 'build-required Vivado board metadata')
                          for name in ('board.xml', 'part0_pins.xml', 'preset.xml'))
    indexed = []
    for path, purpose in external_files:
        record = {'path': str(path), 'purpose': purpose, 'exists': path.is_file()}
        if path.is_file():
            record.update(bytes=path.stat().st_size, sha256=digest(path))
        if 'NOT MIGRATED:' in purpose:
            record['copied'] = False
        indexed.append(record)
    assert all(r['exists'] for r in indexed if r['purpose'] == 'build-required Vivado board metadata')
    native = SOURCE / 'vivado/reports/mission0008_e2_diagnostic_native_025'
    directories = [
        {'path': str(SOURCE / 'data/rebuild_v5_realmodel'),
         'purpose': 'large capture/vector/weight inputs; not copied or fully rehashed'},
        {'path': str(SOURCE / 'vivado/project'),
         'purpose': 'old Vivado projects/IP; not a destination build input'},
        {'path': str(SOURCE / 'vivado/reports'),
         'purpose': 'old raw evidence and frozen source identities; not copied'},
        {'path': str(native), 'purpose': 'original native025 report/fixture directory'},
        {'path': '/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct',
         'purpose': 'read-only checkpoint; explicit --model-dir and identity validation still required'},
    ]
    for item in directories:
        item['exists'] = Path(item['path']).is_dir()
    write_json('external_dependencies.json', {
        'schema': 1, 'files': indexed, 'directories': directories,
        'native025_checkpoint': {
            'path': str(native / 'candidate_placed.dcp'), 'recorded_bytes': 581848433,
            'recorded_sha256': '51e5c5208e2923bc29a053360af6da7ec4364ba3c66725b347b6ec880c19de02',
            'identity_source': 'evidence/native025/candidate_placed_state.txt',
            'verification_this_migration': 'receipt/state copy hashes only; DCP not rehashed or reopened',
            'status': 'failed_unrouted_diagnostic_not_deployable',
        },
        'current_software_reference': {'path': str(new_golden),
            'sha256': digest(new_golden), 'bytes_identical_to_original': True,
            'historical_original': str(old_golden),
            'frozen_evidence': 'original paths retained; no rewriting or new PASS'},
        'toolchain': {'expected_version': 'Vivado 2025.2; not executed',
            'default_executable': '/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/bin/vivado',
            'unprovided': ['Vivado generated IP/project', 'XDMA devices/driver',
                           'board programming scripts and qualified bitstream',
                           'legacy FXP16 reference script closure'],
            'python_runtime_dependencies': ['numpy', 'torch', 'triton', 'safetensors', 'transformers']},
        'read_only_policy': 'old inputs/evidence remain external; never generate into the source tree',
    })
    write_json('source_dest_sha256.json', dict(schema=1, source_root=str(SOURCE),
               destination_root=str(DEST), files=rows))
    result = {'execution_state': 'completed', 'verdict': 'static_checks_pass',
              'applicability': 'migration_only_no_functional_timing_or_board_validation',
              'copied_files': len(rows), 'source_bytes': sum(r['source_bytes'] for r in rows),
              'destination_copied_bytes': sum(r['destination_bytes'] for r in rows),
              'unchanged_files': sum(not r['adapted'] for r in rows),
              'adapted_files': sum(r['adapted'] for r in rows),
              'source_rehash_matches': len(rows), 'manifest_count': len(manifests),
              'manifest_leaf_count': len(leaves), 'python_ast_files': len(python_files),
              'fresh_build_sources_complete': True,
              'fresh_build_inputs_checked': len(fresh_inputs),
              'fresh_build_scope': 'create/synth/place/route source closure only; stages and runtime admission gates not executed',
              'local_python_imports_resolved': local_imports,
              'bash_syntax_files': len(shell_files), 'tcl_complete_files': len(tcl_files),
              'format05_static_contract': contract['status'],
              'path_only_adaptations_verified': len(allowed),
              'new_software_golden': str(new_golden),
              'old_software_golden': str(old_golden),
              'software_golden_bytes_identical': True,
              'software_golden_sha256': digest(new_golden),
              'categories': dict(Counter(r['destination_relative'].split('/')[0] for r in rows)),
              'not_run': ['Vivado', 'XSim', 'GPU', 'board', 'functional_tests', 'real_experiments']}
    write_json('static_checks.json', result)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('copy', 'verify'))
    args = parser.parse_args()
    (copy if args.action == 'copy' else verify)()
