#!/usr/bin/env python3
"""Publish only verified display files; retain historical raw results unchanged."""
import argparse
import json
import os
from pathlib import Path
import shutil
from gsm8k_protocol import atomic_json, sha256_file


def publish(run_root, plan_path):
    plan = json.loads(plan_path.read_text())
    destination = Path(plan['paths']['user_display_results']).resolve()
    merged, display = run_root / 'merged', run_root / 'display'
    validation = json.loads((merged / 'validation.json').read_text())
    render = json.loads((display / 'render_manifest.json').read_text())
    if (validation.get('full_validated') is not True or validation.get('groups_validated') != 30
            or validation.get('formal_rows_validated') != 39570 or validation.get('errors') or validation.get('missing')
            or render.get('gsm8k_groups_validated') != 30):
        raise ValueError('All 30 groups and 39570 independently rescored rows are required')
    for name, digest in validation['artifacts'].items():
        if Path(name).name != name or sha256_file(merged / name) != digest:
            raise ValueError('Validated CSV artifact changed')
    if (render['source_csv_sha256'] != sha256_file(merged / 'six_task_with_gsm8k.csv')
            or render['validation_report_sha256'] != sha256_file(merged / 'validation.json')):
        raise ValueError('Display is not bound to the validated CSV')
    names = ['accuracy_table.md', 'accuracy_table.png', 'accuracy_table.pdf']
    for name in names:
        if sha256_file(display / name) != render['artifacts'][name]:
            raise ValueError('Rendered display artifact changed')
    # A complete snapshot precedes any replacement. Never overwrite this snapshot.
    backup = run_root / 'display_before_publication'
    backup.mkdir(exist_ok=False)
    for name in [*names, 'README.md', 'gsm8k_publication.json']:
        if (destination / name).exists():
            shutil.copy2(destination / name, backup / name)
    receipt = {'schema': 'scalellm_gsm8k_display_publication_v1', 'run_root': str(run_root),
               'plan_sha256': sha256_file(plan_path), 'source_validation': str(merged / 'validation.json'),
               'validation_sha256': sha256_file(merged / 'validation.json'),
               'render_manifest_sha256': sha256_file(display / 'render_manifest.json'),
               'backup': str(backup), 'destination': str(destination),
               'display_artifacts': {name: sha256_file(display / name) for name in names}}
    for name in names:
        temporary = destination / ('.' + name + '.gsm8k.tmp')
        with temporary.open('xb') as handle:
            handle.write((display / name).read_bytes()); handle.flush(); os.fsync(handle.fileno())
        temporary.replace(destination / name)
    readme = destination / 'README.md'
    previous = readme.read_text() if readme.exists() else ''
    banner = ('# GSM8K 补测已完成并独立复算\n\n'
              '当前表已补齐六模型×五配置，共 30/30 组、39,570 条正式 test 输出。'
              '每组1319题，GSM8K为5-shot greedy strict EM，其余五任务为原0-shot likelihood；'
              'Avg.使用六项未舍入分数等权平均，不含PPL。\n\n'
              f'[正式验证报告]({merged / "validation.json"}) · [当前表](accuracy_table.md) · '
              f'[本批原始证据]({run_root / "README.md"})。下方为补测前整理记录；'
              '其中“待测/未启动”属于历史状态，原始历史CSV和manifest保持。\n\n---\n\n')
    temporary = destination / '.README.md.gsm8k.tmp'
    with temporary.open('x') as handle:
        handle.write(banner + previous); handle.flush(); os.fsync(handle.fileno())
    temporary.replace(readme)
    atomic_json(destination / 'gsm8k_publication.json', receipt)
    atomic_json(run_root / 'display_publication.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(publish(args.run_root.resolve(), args.plan.resolve()), ensure_ascii=False))
