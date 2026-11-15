import hashlib
import json
from pathlib import Path

stage = Path('0_Source/operator_timing_kv32/kv128_compare')
board = stage / 'board/native/run_002'
output = Path('0_Hardware_supplementation_experiment/experiment/mlp_scalecode_dsp_board/board_test/reference')
output.mkdir(exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


inventory = json.loads((board / 'remote_inventory.json').read_text())
by_path = {entry['path']: entry for entry in inventory['files']}
publication = json.loads((stage / 'results/publication_final_001/summary.json').read_text())
commands = []
for analysis_entry in publication['analyses']:
    analysis_path = Path(analysis_entry['path'])
    assert sha(analysis_path) == analysis_entry['sha256']
    analysis = json.loads(analysis_path.read_text())
    cid = analysis['command_id']
    validation_path = Path(analysis['source_manifest']['path'])
    assert sha(validation_path) == analysis['source_manifest']['sha256']
    validation = json.loads(validation_path.read_text())
    assert analysis['status'] == validation['validation']['status'] == 'PASS'
    assert validation['validation_scope']['command_ids'] == [cid]
    original = validation['input_manifest'][str(cid)]
    files = {}
    for name, expected_sha in original['captured_payloads'].items():
        file_name = f'cmd_{cid:04d}_{name}.bin'
        source = board / 'payloads' / file_name
        record = by_path['payloads/' + file_name]
        assert source.stat().st_size == record['bytes']
        assert sha(source) == record['sha256'] == expected_sha
        files[name] = dict(file=file_name, bytes=record['bytes'], sha256=expected_sha)
    sim_record = validation['command_evidence']['raw_sources']['sim_output']
    sim_path = Path(sim_record['snapshot_path'])
    replay = validation['numerical_replay'][str(cid)]
    assert replay['byte_exact'] is True
    assert sha(sim_path) == sim_record['sha256'] == files['output']['sha256']
    assert sim_path.stat().st_size == files['output']['bytes']
    assert replay['actual_sha256'] == replay['captured_sha256'] == files['output']['sha256']
    commands.append(dict(command_id=cid, layer=analysis['layer'], opcode=analysis['opcode'],
                         kv_length=analysis['workload']['kv_length'], files=files,
                         scale_assets=original['scale_assets'], sealed_analysis=analysis_entry,
                         sealed_validation=dict(path=str(validation_path), sha256=sha(validation_path)),
                         sealed_sim_output=sim_record))
order = [1986, 8130, 1985, 8129, 2001, 8145, 2017, 8161, 2033, 8177, 2047, 8191]
assert sorted(order) == sorted(item['command_id'] for item in commands)
commands.sort(key=lambda item: order.index(item['command_id']))
manifest = dict(schema='scalellm_dsp_operator_reference_v1', status='PASS',
                reference='sealed version operator reference',
                publication_sha256=sha(stage / 'results/publication_final_001/summary.json'),
                original_remote_inventory_sha256=sha(board / 'remote_inventory.json'),
                original_remote_payload_root='D:/ScaleLLM_final_model/operator_kv128_20261101_001/run_002/payloads',
                commands=commands)
(output / 'reference_manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps(dict(status='PASS', commands=len(commands), payloads=sum(len(c['files']) for c in commands),
                      manifest_sha256=sha(output / 'reference_manifest.json'))))
