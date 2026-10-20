"""Freeze a simple random sample before any candidate token decoding."""
from pathlib import Path
import csv, hashlib, json, math, os, random, sys, time

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
SEED = 20261020

def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(8 << 20), b''):
            h.update(data)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}

def save(name, obj):
    with (HERE / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def main():
    started = time.time()
    source = RUN / 'analysis/top1_margin_stratification/top1_flips.csv'
    official = RUN / 'session_S001/analysis_manifest.json'
    protocol = {
        'schema': 'r006_qualitative_sample_protocol_v1',
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'scope': 'CPU-only preparation and local-tokenizer decoding; no semantic annotation, model inference or GPU',
        'population': 'Original formal R006 Top1 flips with finite reference raw-logit margin >=0 and <0.05',
        'expected_eligible_positions': 876,
        'stable_sort': ['doc_id ascending Unicode string', 'position ascending integer'],
        'sampling': 'random.Random(20261020).sample(sorted_eligible_rows, 100)',
        'seed': SEED, 'sample_size': 100,
        'replacement': False, 'equal_probability_per_eligible_position': True,
        'sample_order': 'Unmodified order returned by random.Random.sample; S001 through S100',
        'position_semantics': 'Logits at zero-based position t predict the next token; prefix includes input_ids[:t+1]',
        'prefix_sources': 'Use frozen token_artifact, cross-checked against R006 input_identity and source metadata',
        'tokenizer': 'Original local Llama-3.1-8B-Instruct tokenizer, local_files_only, original file SHA checks',
        'decode': {'skip_special_tokens': False, 'clean_up_tokenization_spaces': False,
                   'full_prefix_maximum_tokens': 128, 'tail_tokens': 64,
                   'joint_context': 'Decode prefix plus exactly one candidate; do not append original suffix or generate more tokens'},
        'actual_source_next_token': 'Auxiliary only, not a gold label. Use frozen next input ID when present; for t=127, locally tokenize source text up to129 tokens and require entire frozen prefix identity. Null when no source next token exists.',
        'review_packet': 'Main view omits actual source next token; no subjective data-stage labels',
        'shared_directory_boundaries': {'engineering': 'Files directly in this directory',
                                        'independent_reviewer': 'independent_annotation/',
                                        'controller': ['root_annotation/', 'reconciled/']},
        'source_csv': identity(source), 'official_manifest': identity(official),
        'frozen_before_candidate_text_decoding': True,
    }
    save('protocol.json', protocol)
    rows = list(csv.DictReader(source.open(newline='')))
    assert len(rows) == 1053
    eligible = [r for r in rows if int(r['top1_flip']) == 1 and
                math.isfinite(float(r['reference_top1_margin'])) and
                0 <= float(r['reference_top1_margin']) < .05]
    eligible.sort(key=lambda r: (r['doc_id'], int(r['position'])))
    assert len(eligible) == 876
    assert len({(r['doc_id'], int(r['position'])) for r in eligible}) == 876
    selected = random.Random(SEED).sample(eligible, 100)
    manifest = json.loads(official.read_text())
    groups = {g['group_id']: g for g in manifest['ordered_groups']}
    assert len(groups) == 64
    sources = {x['path']: x for x in [identity(source), identity(official), identity(__file__), identity(HERE / 'protocol.json')]}
    samples = []
    cache = {}
    for n, row in enumerate(selected, 1):
        g = groups[row['group_id']]
        attempt = Path(g['attempt_path'])
        if row['group_id'] not in cache:
            worker_path = attempt / 'paired_worker_manifest.json'
            logit_path = attempt / 'logit_metrics.jsonl'
            worker = json.loads(worker_path.read_text())
            metrics = [json.loads(s) for s in logit_path.read_text().splitlines()]
            assert [d['doc_id'] for d in worker['selected_documents']] == [d['doc_id'] for d in metrics]
            cache[row['group_id']] = worker, metrics
            for p in [worker_path, logit_path, attempt / 'tokenizer_identity.json']:
                sources[str(p)] = identity(p)
        worker, metrics = cache[row['group_id']]
        index = next(i for i, d in enumerate(worker['selected_documents']) if d['doc_id'] == row['doc_id'])
        doc = worker['selected_documents'][index]
        metric = metrics[index]
        t = int(row['position'])
        pt = metric['per_token']
        assert not pt['top1_matches'][t]
        assert pt['current_top1_ids'][t] == int(row['current_top1_id'])
        assert pt['reference_top1_ids'][t] == int(row['reference_top1_id'])
        assert pt['reference_top1_margin'][t] == float(row['reference_top1_margin'])
        input_path = attempt / f'documents/doc{index:04d}/input_identity.json'
        inp = json.loads(input_path.read_text())
        assert inp['doc_id'] == doc['doc_id'] == metric['doc_id']
        assert inp['text_sha256'] == doc['text_sha256']
        assert inp['tokens'] == metric['tokens'] and 0 <= t < inp['tokens'] <= 128
        token_path = Path(inp['token_artifact']['path'])
        token_ident = identity(token_path)
        assert token_ident == inp['token_artifact']
        for p in [input_path, token_path]:
            sources[str(p)] = identity(p)
        samples.append({
            'sample_id': f'S{n:03d}', 'sampling_order': n,
            'group_id': row['group_id'], 'doc_id': row['doc_id'], 'domain': row['domain'],
            'position': t, 'document_tokens': inp['tokens'],
            'reference_top1_margin': float(row['reference_top1_margin']),
            'current_top1_id': int(row['current_top1_id']),
            'reference_top1_id': int(row['reference_top1_id']),
            'softmax_tv': float(row['softmax_tv']),
            'source_logit_metrics': identity(attempt / 'logit_metrics.jsonl'),
            'input_identity': identity(input_path), 'token_artifact': token_ident,
            'text_sha256': inp['text_sha256'],
            'tokenizer_identity': identity(attempt / 'tokenizer_identity.json'),
        })
    save('eligible_pool_keys.json', {'sorted_eligible_keys': [
        {'doc_id': r['doc_id'], 'position': int(r['position'])} for r in eligible]})
    save('sample_manifest.json', {
        'schema': 'r006_qualitative_frozen_sample_v1',
        'frozen_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'seed': SEED, 'eligible_count': len(eligible), 'sample_count': len(samples),
        'protocol': identity(HERE / 'protocol.json'),
        'pool_keys': identity(HERE / 'eligible_pool_keys.json'),
        'source_csv': identity(source), 'official_manifest': identity(official),
        'samples': samples, 'sources': list(sources.values()),
        'no_candidate_token_text_decoded': True,
    })
    save('freeze_execution.json', {
        'pid': os.getpid(), 'argv': sys.argv, 'wall_seconds': time.time() - started,
        'execution_state': 'completed', 'sample_manifest': identity(HERE / 'sample_manifest.json'),
        'candidate_decoding_performed': False, 'GPU_or_model_used': False,
    })
    print(json.dumps({'sample_count': len(samples), 'eligible': len(eligible),
                      'unique_documents': len({s['doc_id'] for s in samples}),
                      'manifest': identity(HERE / 'sample_manifest.json')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
