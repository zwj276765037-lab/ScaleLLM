"""Decode only the already-frozen R006 simple-random sample; CPU tokenizer only."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, os, random, resource, sys, time
import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
MODEL = Path('/home/user/EDA-202/zhuowenjun/fpga_llm_project/configs/models/Llama-3.1-8B-Instruct')

def identity(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(8 << 20), b''):
            h.update(data)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': h.hexdigest()}

def save(name, obj):
    if name == 'scope_clarification.json' and (HERE / name).exists():
        return
    with (HERE / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def check(record):
    assert identity(record['path']) == record, record['path']

def jsonl(name, records):
    with (HERE / name).open('x') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')

def csvfile(name, records):
    fields = list(records[0])
    with (HERE / name).open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: json.dumps(v, ensure_ascii=False, allow_nan=False)
                    if isinstance(v, (dict, list)) else v for k, v in r.items()} for r in records)

def fence(text):
    # Frozen source text may itself contain Markdown fences.
    n = max([len(x) for x in __import__('re').findall(r'`+', text)] + [2]) + 1
    delimiter = '`' * max(3, n)
    return delimiter + 'text\n' + text + '\n' + delimiter

def byte_decoder():
    bs = list(range(ord('!'), ord('~') + 1)) + list(range(ord('¡'), ord('¬') + 1)) + list(range(ord('®'), ord('ÿ') + 1))
    cs = list(bs)
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {chr(c): b for b, c in zip(bs, cs)}

def main():
    start = time.monotonic()
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert os.environ.get('USE_TORCH') == '0' and os.environ.get('USE_TF') == '0'
    protocol_path = HERE / 'protocol.json'
    manifest_path = HERE / 'sample_manifest.json'
    manifest_id = identity(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    protocol = json.loads(protocol_path.read_text())
    save('scope_clarification.json', {
        'created_utc': started,
        'authority': 'Latest controller instruction: prioritize frozen input prefix plus two candidates; no original-text retokenization needed, auxiliary next token beyond truncation may be null.',
        'change': 'Auxiliary source next token is read only from the frozen token artifact; null at its end. No original-text tokenization is performed.',
        'unchanged': 'All sampling rules, frozen sample keys, candidate IDs, prefix position semantics, and tokenizer identity checks.',
        'frozen_protocol': identity(protocol_path), 'frozen_sample_manifest': manifest_id,
    })
    check(manifest['protocol'])
    check(manifest['pool_keys'])
    for src in manifest['sources']:
        check(src)
    # Independently reproduce sampling before loading or decoding the tokenizer.
    pool = list(csv.DictReader(Path(manifest['source_csv']['path']).open(newline='')))
    pool = [r for r in pool if int(r['top1_flip']) == 1 and 0 <= float(r['reference_top1_margin']) < .05]
    pool.sort(key=lambda r: (r['doc_id'], int(r['position'])))
    selected = random.Random(20261020).sample(pool, 100)
    assert len(pool) == 876 and [(r['doc_id'], int(r['position'])) for r in selected] == [
        (s['doc_id'], s['position']) for s in manifest['samples']]
    assert protocol['frozen_before_candidate_text_decoding'] and manifest['no_candidate_token_text_decoded']
    first_identity = json.loads(Path(manifest['samples'][0]['tokenizer_identity']['path']).read_text())
    stream_ident = first_identity['document_source']
    check(stream_ident)
    stream = json.loads(Path(stream_ident['path']).read_text())
    check(stream['input_source'])
    stream_docs = {d['doc_id']: d for d in stream['documents']}
    source_docs = {d['doc_id']: d for d in (
        json.loads(line) for line in Path(stream['input_source']['path']).open())}
    tokenizer_files = {r['path']: r for r in first_identity['files']}
    assert tokenizer_files == {r['path']: r for r in stream['tokenizer_files']}
    for r in tokenizer_files.values():
        check(r)
        assert Path(r['path']).parent == MODEL
    for p in {s['tokenizer_identity']['path'] for s in manifest['samples']}:
        tid = json.loads(Path(p).read_text())
        assert tid['files'] == first_identity['files'] and tid['document_source'] == stream_ident
    from transformers import AutoTokenizer
    import transformers, tokenizers
    tok = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True, trust_remote_code=False)
    vocab = json.loads((MODEL / 'tokenizer.json').read_text())
    assert vocab['decoder']['type'] == 'ByteLevel' and vocab['model']['type'] == 'BPE'
    bd = byte_decoder()
    special = set(tok.all_special_ids)
    def decode(ids, skip=False):
        return tok.decode(ids, skip_special_tokens=skip, clean_up_tokenization_spaces=False)
    def candidate(ids, token_id):
        raw = tok.convert_ids_to_tokens(token_id)
        single = decode([token_id])
        joint = decode(ids + [token_id])
        prefix = decode(ids)
        common = 0
        for a, b in zip(prefix, joint):
            if a != b:
                break
            common += 1
        raw_bytes = bytes(bd[c] for c in raw) if token_id not in special and all(c in bd for c in raw) else None
        if raw_bytes is not None:
            assert raw_bytes.decode('utf-8', errors='replace') == single
        return {
            'id': token_id, 'tokenizer_piece': raw, 'single_token_text': single,
            'single_token_repr': repr(single), 'is_special_token': token_id in special,
            'byte_values_hex': raw_bytes.hex() if raw_bytes is not None else None,
            'single_token_contains_unicode_replacement': '\ufffd' in single,
            'joint_full_prefix_and_token': joint,
            'joint_tail64_prefix_and_token': decode(ids[-64:] + [token_id]),
            'joint_tail12_prefix_and_token': decode(ids[-12:] + [token_id]),
            'joint_full_is_prefix_text_plus_single_token': joint == prefix + single,
            'joint_full_common_prefix_characters': common,
            'joint_full_changed_suffix_repr': repr(joint[common:]),
        }
    docs_cache = {}
    results = []
    sourcechecks = []
    for sample in manifest['samples']:
        docid = sample['doc_id']
        if docid not in docs_cache:
            inp = json.loads(Path(sample['input_identity']['path']).read_text())
            sd = stream_docs[docid]
            original = source_docs[docid]
            assert inp['doc_id'] == original['doc_id'] == sd['doc_id']
            assert inp['text_sha256'] == original['text_sha256'] == sd['text_sha256'] == sample['text_sha256']
            assert hashlib.sha256(original['text'].encode('utf-8')).hexdigest() == inp['text_sha256']
            assert inp['token_artifact'] == sd['token_artifact'] == sample['token_artifact']
            assert original['domain'] == sd['domain'] == sample['domain']
            with np.load(sample['token_artifact']['path'], allow_pickle=False) as npz:
                arrays = {k: npz[k] for k in npz.files}
            assert all(a.ndim in [1, 2] for a in arrays.values())
            arrays = {k: a.reshape(1, -1) if a.ndim == 1 else a for k, a in arrays.items()}
            assert set(arrays) == {'input_ids', 'attention_mask', 'position_ids'}
            frozen_ids = arrays['input_ids'][0].tolist()
            assert arrays['input_ids'].shape == (1, inp['tokens']) and len(frozen_ids) <= 128
            assert inp['input_ids'] == arrays['input_ids'].tolist()
            assert inp['attention_mask'] == arrays['attention_mask'].tolist()
            assert np.all(arrays['attention_mask'] == 1)
            assert arrays['position_ids'][0].tolist() == list(range(len(frozen_ids)))
            # Prefix and any auxiliary source-next token come only from the actual experiment IDs.
            original_ids = frozen_ids
            assert inp['tokens'] == sd['tokens']
            docs_cache[docid] = inp, original, frozen_ids, original_ids
            sourcechecks.append({'doc_id': docid, 'tokens': len(frozen_ids),
                                 'text_SHA_equal': True, 'input_identity_equals_token_artifact': True,
                                 'original_text_SHA_matches_experiment': True,
                                 'frozen_input_identity': sample['input_identity'],
                                 'token_artifact': sample['token_artifact']})
        inp, original, frozen_ids, original_ids = docs_cache[docid]
        t = sample['position']
        ids = frozen_ids[:t + 1]
        assert len(ids) == t + 1 and 1 <= len(ids) <= 128
        ref = candidate(ids, sample['reference_top1_id'])
        cur = candidate(ids, sample['current_top1_id'])
        actual_id = original_ids[t + 1] if t + 1 < len(original_ids) else None
        actual = candidate(ids, actual_id) if actual_id is not None else None
        if t + 1 < len(frozen_ids):
            assert actual_id == frozen_ids[t + 1]
            actual_source = 'next token in frozen experiment token_artifact'
        else:
            actual_source = 'outside saved token_artifact; unavailable, null; no retokenization or EOS fabricated'
        result = {
            'sample_id': sample['sample_id'], 'sampling_order': sample['sampling_order'],
            'doc_id': docid, 'domain': sample['domain'], 'group_id': sample['group_id'],
            'position': t, 'prediction_semantics': 'next-token prediction after input_ids[t]; prefix length is t+1',
            'document_tokens': len(frozen_ids), 'prefix_tokens': len(ids),
            'reference_top1_margin': sample['reference_top1_margin'], 'softmax_tv': sample['softmax_tv'],
            'prefix_token_ids': ids, 'prefix_full': decode(ids),
            'prefix_full_without_special_tokens': decode(ids, skip=True),
            'prefix_tail64_token_ids': ids[-64:], 'prefix_tail64': decode(ids[-64:]),
            'reference': ref, 'current': cur,
            'actual_source_next_token_auxiliary_not_gold': actual,
            'actual_source_next_token_source': actual_source,
            'source_metadata': {k: original[k] for k in ['doc_id', 'domain', 'source_asset', 'source_id',
                                                        'source_split', 'text_sha256', 'source_file']},
            'input_identity': sample['input_identity'], 'token_artifact': sample['token_artifact'],
            'all_source_and_tokenizer_identity_checks_passed': True,
        }
        results.append(result)
    assert len(results) == 100 and len({(r['doc_id'], r['position']) for r in results}) == 100
    assert [r['sample_id'] for r in results] == [f'S{i:03d}' for i in range(1, 101)]
    jsonl('samples.jsonl', results)
    flat = []
    compact = []
    for r in results:
        a = r['actual_source_next_token_auxiliary_not_gold']
        flat.append({
            'sample_id': r['sample_id'], 'doc_id': r['doc_id'], 'domain': r['domain'],
            'position': r['position'], 'prefix_tokens': r['prefix_tokens'],
            'reference_top1_margin': r['reference_top1_margin'], 'softmax_tv': r['softmax_tv'],
            'prefix_token_ids': r['prefix_token_ids'], 'prefix_full': r['prefix_full'],
            'prefix_tail64': r['prefix_tail64'],
            'reference_token_id': r['reference']['id'], 'reference_token_repr': r['reference']['single_token_repr'],
            'current_token_id': r['current']['id'], 'current_token_repr': r['current']['single_token_repr'],
            'reference_tokenizer_piece': r['reference']['tokenizer_piece'],
            'current_tokenizer_piece': r['current']['tokenizer_piece'],
            'reference_joint_prefix': r['reference']['joint_full_prefix_and_token'],
            'current_joint_prefix': r['current']['joint_full_prefix_and_token'],
            'reference_joint_tail64': r['reference']['joint_tail64_prefix_and_token'],
            'current_joint_tail64': r['current']['joint_tail64_prefix_and_token'],
            'actual_source_next_token_id_auxiliary_not_gold': a['id'] if a else None,
            'actual_source_next_token_repr_auxiliary_not_gold': a['single_token_repr'] if a else None,
            'actual_source_next_token_source': r['actual_source_next_token_source'],
        })
        compact.append({
            'sample_id': r['sample_id'], 'doc_id': r['doc_id'], 'domain': r['domain'], 'position': r['position'],
            'reference_top1_margin': r['reference_top1_margin'], 'prefix_tail64': r['prefix_tail64'],
            'reference': {k: r['reference'][k] for k in ['id', 'single_token_repr', 'tokenizer_piece',
                                                         'joint_tail12_prefix_and_token', 'byte_values_hex']},
            'current': {k: r['current'][k] for k in ['id', 'single_token_repr', 'tokenizer_piece',
                                                    'joint_tail12_prefix_and_token', 'byte_values_hex']},
        })
    csvfile('samples.csv', flat)
    jsonl('review_packet.jsonl', compact)
    domain_counts = dict(sorted(Counter(r['domain'] for r in results).items()))
    domain_docs = {d: len({r['doc_id'] for r in results if r['domain'] == d}) for d in domain_counts}
    validation = {
        'execution_state': 'completed', 'sample_count': 100, 'eligible_positions': 876,
        'unique_documents': len(docs_cache), 'domain_sample_counts': domain_counts,
        'domain_unique_documents': domain_docs, 'sampling_reproduced_exactly': True,
        'original_sample_manifest_unchanged': identity(manifest_path) == manifest_id,
        'all_93_document_source_SHA_and_token_artifact_checks_passed': len(sourcechecks) == 93,
        'tokenizer_identity_matches_original_experiment': True,
        'all_prefix_lengths_equal_position_plus_one': True,
        'source_text_retokenization_performed': False,
        'prefix_from_actual_experiment_token_artifact_only': True,
        'actual_next_available': sum(r['actual_source_next_token_auxiliary_not_gold'] is not None for r in results),
        'actual_next_unavailable': sum(r['actual_source_next_token_auxiliary_not_gold'] is None for r in results),
        'actual_next_beyond_experiment_128_tokens': sum(r['position'] == 127 and r['actual_source_next_token_auxiliary_not_gold'] is not None for r in results),
        'candidate_single_token_unicode_replacement_counts': {
            k: sum(r[k]['single_token_contains_unicode_replacement'] for r in results) for k in ['reference', 'current']},
        'candidate_joint_decode_differs_from_string_concatenation_counts': {
            k: sum(not r[k]['joint_full_is_prefix_text_plus_single_token'] for r in results) for k in ['reference', 'current']},
        'semantic_annotations_performed': False, 'GPU_or_model_used': False,
        'torch_loaded': 'torch' in sys.modules,
        'transformers_version': transformers.__version__, 'tokenizers_version': tokenizers.__version__,
    }
    assert not validation['torch_loaded'] and validation['original_sample_manifest_unchanged']
    for src in manifest['sources']:
        check(src)
    save('validation.json', validation)
    save('document_identity_checks.json', {'documents': sourcechecks})
    save('decode_source_manifest.json', {
        'frozen_sample_manifest': manifest_id, 'decoder_source': identity(__file__),
        'frozen_document_stream': stream_ident, 'original_text_source': stream['input_source'],
        'tokenizer_files': list(tokenizer_files.values()),
        'versions': {'python': sys.version, 'transformers': transformers.__version__, 'tokenizers': tokenizers.__version__, 'numpy': np.__version__},
        'decoding_options': protocol['decode'],
    })
    packet = [
        '# 低 Margin Top1 翻转：100 例独立评阅包',
        '',
        '从 876 个参考 Logit Margin < 0.05 的翻转位置中，以种子 20261020 等概率、无放回抽样 100 例；涉及 93 篇文档。顺序为抽样返回顺序，未按候选内容筛选。',
        '',
        '每例前缀包含预测位置本身：位置 t 的 logits 预测 input_ids[t+1]，故输入前缀为 input_ids[:t+1]。下方展示末 64 个输入 token 解码文本。',
        '',
        '单 token 以 Python repr 显示空格和换行；候选后缀由末 12 个输入 token 与该候选联合解码，只追加一个 token。BPE 片段可能是半个词，不能把它当完整续写。完整前缀和字节信息见 samples.jsonl。',
        '',
        '参考版本是数值对照，不能据名称视为语义金标。此包不展示原文实际下一 token；该辅助信息仅单列存于 samples 文件。数据准备阶段未加主观标签。',
        '',
        '| 域 | 样本数 | 独立文档数 |', '|---|---:|---:|',
    ]
    packet += [f'| {d} | {domain_counts[d]} | {domain_docs[d]} |' for d in domain_counts]
    for r in compact:
        packet += ['', f"## {r['sample_id']}", '',
                   f"文档 `{r['doc_id']}`；域 {r['domain']}；位置 {r['position']}（从 0 开始）；参考 Logit Margin {r['reference_top1_margin']:.10g}。", '',
                   '输入前缀末 64 token：', '', fence(r['prefix_tail64']), '']
        for k, name in [('reference', '参考版本'), ('current', '当前版本')]:
            c = r[k]
            packet += [f"{name}候选：ID {c['id']}；单 token repr：", '', fence(c['single_token_repr']), '',
                       '末 12 输入 token + 该候选联合解码：', '', fence(c['joint_tail12_prefix_and_token']), '']
    with (HERE / 'review_packet.md').open('x') as f:
        f.write('\n'.join(packet) + '\n')
    save('decode_execution.json', {
        'started_utc': started, 'completed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'pid': os.getpid(), 'argv': sys.argv, 'wall_seconds': time.monotonic() - start,
        'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        'execution_state': 'completed', 'GPU_or_model_used': False,
    })
    outputs = ['samples.jsonl', 'samples.csv', 'review_packet.jsonl', 'review_packet.md', 'validation.json',
               'document_identity_checks.json', 'decode_source_manifest.json', 'decode_execution.json', 'scope_clarification.json']
    save('artifact_manifest.json', {'outputs': [identity(HERE / name) for name in outputs],
                                     'frozen_sample_manifest': manifest_id,
                                     'annotation_directories_not_modified': True})
    print(json.dumps(validation, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
