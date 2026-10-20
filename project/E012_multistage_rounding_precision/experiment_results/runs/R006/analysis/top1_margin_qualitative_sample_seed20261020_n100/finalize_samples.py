"""Independently verify completed decoded rows and finish the review packet on CPU."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, os, random, re, resource, sys, time
from tokenizers import Tokenizer
import tokenizers

HERE = Path(__file__).resolve().parent

def identity(path):
    p = Path(path).resolve()
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return {'path': str(p), 'bytes': p.stat().st_size, 'sha256': h.hexdigest()}

def readlines(name):
    with (HERE / name).open() as f:
        return [json.loads(line) for line in f]

def save(name, obj):
    with (HERE / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def check(item):
    assert identity(item['path']) == item, item['path']

def fence(text):
    n = max([len(x) for x in re.findall(r'`+', text)] + [2]) + 1
    delimiter = '`' * max(3, n)
    return delimiter + 'text\n' + text + '\n' + delimiter

def main():
    start = time.monotonic()
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    manifest = json.loads((HERE / 'sample_manifest.json').read_text())
    sources = manifest['sources']
    for src in sources:
        check(src)
    rows = readlines('samples.jsonl')
    compact = readlines('review_packet.jsonl')
    with (HERE / 'samples.csv').open(newline='') as f:
        csvrows = list(csv.DictReader(f))
    assert len(rows) == len(compact) == len(csvrows) == 100
    pool = list(csv.DictReader(Path(manifest['source_csv']['path']).open(newline='')))
    pool = sorted([r for r in pool if int(r['top1_flip']) == 1 and 0 <= float(r['reference_top1_margin']) < .05],
                  key=lambda r: (r['doc_id'], int(r['position'])))
    assert len(pool) == 876
    draws = random.Random(20261020).sample(pool, 100)
    assert [(r['doc_id'], int(r['position'])) for r in draws] == [(r['doc_id'], r['position']) for r in rows]
    tid = json.loads(Path(manifest['samples'][0]['tokenizer_identity']['path']).read_text())
    for item in tid['files']:
        check(item)
    tokenizer_file = next(i for i in tid['files'] if Path(i['path']).name == 'tokenizer.json')
    tokenizer = Tokenizer.from_file(tokenizer_file['path'])
    def decode(ids):
        return tokenizer.decode(ids, skip_special_tokens=False)
    seen = set()
    docchecks = {}
    for i, (r, m, c, flat) in enumerate(zip(rows, manifest['samples'], compact, csvrows), 1):
        assert r['sample_id'] == m['sample_id'] == c['sample_id'] == flat['sample_id'] == f'S{i:03d}'
        assert (r['doc_id'], r['position']) not in seen
        seen.add((r['doc_id'], r['position']))
        assert r['doc_id'] == m['doc_id'] == c['doc_id'] == flat['doc_id']
        assert r['position'] == m['position'] == c['position'] == int(flat['position'])
        assert r['reference_top1_margin'] == m['reference_top1_margin'] == c['reference_top1_margin'] == float(flat['reference_top1_margin'])
        inp = json.loads(Path(m['input_identity']['path']).read_text())
        ids = inp['input_ids'][0][:r['position'] + 1]
        assert ids == r['prefix_token_ids'] == json.loads(flat['prefix_token_ids'])
        assert r['prefix_tokens'] == len(ids) == r['position'] + 1 <= 128
        assert decode(ids) == r['prefix_full'] == flat['prefix_full']
        assert decode(ids[-64:]) == r['prefix_tail64'] == flat['prefix_tail64'] == c['prefix_tail64']
        assert ids[-64:] == r['prefix_tail64_token_ids']
        assert not any('actual' in k for k in c)
        for family, idkey in [('reference', 'reference_top1_id'), ('current', 'current_top1_id')]:
            candidate = r[family]
            token_id = candidate['id']
            assert token_id == m[idkey] == c[family]['id'] == int(flat[family + '_token_id'])
            assert decode([token_id]) == candidate['single_token_text']
            assert repr(decode([token_id])) == candidate['single_token_repr'] == flat[family + '_token_repr']
            assert decode(ids + [token_id]) == candidate['joint_full_prefix_and_token'] == flat[family + '_joint_prefix']
            assert decode(ids[-64:] + [token_id]) == candidate['joint_tail64_prefix_and_token'] == flat[family + '_joint_tail64']
            assert decode(ids[-12:] + [token_id]) == candidate['joint_tail12_prefix_and_token'] == c[family]['joint_tail12_prefix_and_token']
        assert r['reference']['id'] != r['current']['id']
        actual = r['actual_source_next_token_auxiliary_not_gold']
        if r['position'] + 1 < inp['tokens']:
            assert actual['id'] == inp['input_ids'][0][r['position'] + 1]
        else:
            assert actual is None
        assert inp['doc_id'] == r['doc_id'] and inp['text_sha256'] == r['source_metadata']['text_sha256']
        docchecks[r['doc_id']] = {'doc_id': r['doc_id'], 'input_identity': m['input_identity'],
                                 'token_artifact': m['token_artifact'], 'prefix_from_saved_ids_verified': True}
    assert len(docchecks) == 93 and 'torch' not in sys.modules
    domain_counts = dict(sorted(Counter(r['domain'] for r in rows).items()))
    domain_docs = {d: len({r['doc_id'] for r in rows if r['domain'] == d}) for d in domain_counts}
    validation = {
        'execution_state': 'completed', 'data_validation': 'PASS',
        'eligible_positions': 876, 'sample_count': 100, 'unique_documents': len(docchecks),
        'domain_sample_counts': domain_counts, 'domain_unique_documents': domain_docs,
        'seed': 20261020, 'equal_probability_without_replacement': True,
        'sampling_reproduced_exactly': True, 'all_frozen_sources_SHA_unchanged': True,
        'sample_manifest': identity(HERE / 'sample_manifest.json'),
        'position_semantics_verified': 'Every prefix is exactly saved input_ids[:t+1]; logits at t predict next token',
        'all_candidate_ids_and_margins_match_frozen_manifest': True,
        'JSONL_CSV_compact_packet_all_100_rows_agree': True,
        'all_single_and_joint_decodes_verified_with_independent_tokenizers_backend': True,
        'tokenizer_files_SHA_match_original_experiment': True,
        'source_text_retokenization_performed': False,
        'actual_next_available_inside_saved_artifact': sum(r['actual_source_next_token_auxiliary_not_gold'] is not None for r in rows),
        'actual_next_unavailable_at_saved_artifact_end': sum(r['actual_source_next_token_auxiliary_not_gold'] is None for r in rows),
        'single_token_contains_unicode_replacement_counts': {
            k: sum(r[k]['single_token_contains_unicode_replacement'] for r in rows) for k in ['reference', 'current']},
        'joint_decode_differs_from_string_concatenation_counts': {
            k: sum(not r[k]['joint_full_is_prefix_text_plus_single_token'] for r in rows) for k in ['reference', 'current']},
        'semantic_annotations_performed': False, 'GPU_or_model_used': False,
        'finalizer_torch_loaded': False,
        'prior_execution_note': 'v3 completed all100 decoded rows then failed an extra assertion that torch was not indirectly imported by AutoTokenizer. No CUDA/model call occurred. This finalizer uses tokenizers only and independently verifies every row. v1/v2/v3 sources and native1 receipts are preserved.',
    }
    packet = [
        '# 低 Margin Top1 翻转：100 例独立评阅包', '',
        '从 876 个参考 Logit Margin < 0.05 的翻转位置中，以种子 20261020 等概率、无放回抽样 100 例；涉及 93 篇文档。顺序为抽样返回顺序，未按候选内容筛选。', '',
        '每例前缀包含预测位置本身：位置 t 的 logits 预测下一 token，输入前缀严格为 input_ids[:t+1]。下方展示末 64 个输入 token 解码文本。', '',
        '单 token 用 Python repr 显示空格和换行；候选后缀由末 12 个输入 token 与该候选联合解码，只追加一个 token。BPE 片段可能是半个词，不能当完整续写。完整前缀和字节信息见 samples.jsonl。', '',
        '参考版本是数值对照，不能据名称视为语义金标。此包不展示原文实际下一 token；该辅助信息仅单列存于 samples 文件，超过已保存输入的范围记为 null。数据准备阶段未加主观标签。', '',
        '| 域 | 样本数 | 独立文档数 |', '|---|---:|---:|']
    packet += [f'| {d} | {domain_counts[d]} | {domain_docs[d]} |' for d in domain_counts]
    for r in compact:
        packet += ['', f"## {r['sample_id']}", '',
                   f"文档 `{r['doc_id']}`；域 {r['domain']}；位置 {r['position']}（从 0 开始）；参考 Logit Margin {r['reference_top1_margin']:.10g}。", '',
                   '输入前缀末 64 token：', '', fence(r['prefix_tail64']), '']
        for k, name in [('reference', '参考版本'), ('current', '当前版本')]:
            candidate = r[k]
            packet += [f"{name}候选：ID {candidate['id']}；单 token repr：", '', fence(candidate['single_token_repr']), '',
                       '末 12 输入 token + 该候选联合解码：', '', fence(candidate['joint_tail12_prefix_and_token']), '']
    with (HERE / 'review_packet.md').open('x') as f:
        f.write('\n'.join(packet) + '\n')
    save('validation.json', validation)
    save('document_identity_checks.json', {'documents': list(docchecks.values()), 'count': len(docchecks)})
    save('decode_source_manifest.json', {
        'protocol': identity(HERE / 'protocol.json'), 'frozen_sample_manifest': identity(HERE / 'sample_manifest.json'),
        'decoder_consumed_source': identity(HERE / 'decode_samples_v3.py'),
        'independent_finalizer_source': identity(__file__),
        'tokenizer_files': tid['files'], 'original_document_stream': tid['document_source'],
        'finalizer_versions': {'python': sys.version, 'tokenizers': tokenizers.__version__},
        'decode_options': {'skip_special_tokens': False, 'clean_up_tokenization_spaces': False},
        'clarification': identity(HERE / 'scope_clarification.json'),
    })
    save('finalization_execution.json', {
        'started_utc': started, 'completed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'pid': os.getpid(), 'argv': sys.argv, 'wall_seconds': time.monotonic() - start,
        'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        'execution_state': 'completed', 'GPU_or_model_used': False,
    })
    names = ['samples.jsonl', 'samples.csv', 'review_packet.jsonl', 'review_packet.md', 'validation.json',
             'document_identity_checks.json', 'decode_source_manifest.json', 'finalization_execution.json']
    save('artifact_manifest.json', {'outputs': [identity(HERE / n) for n in names],
                                     'annotation_directories_not_modified': True})
    print(json.dumps(validation, ensure_ascii=False), flush=True)

if __name__ == '__main__':
    main()
