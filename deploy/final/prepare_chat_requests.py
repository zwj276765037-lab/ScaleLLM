#!/usr/bin/env python3
"""Render 1..16 text conversations with the licensed model's own chat template."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from final.common import CHECKPOINT_SHA, bootstrap, sha, validate_requests


def prepare(assets_path, messages_path, result):
    bootstrap()
    manifest_path = Path(assets_path).resolve(strict=True)
    assets = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (assets.get('schema') != 'scalellm_llama31_host_assets_v1' or assets.get('state') != 'COMPLETE'
            or assets.get('checkpoint_sha256') != CHECKPOINT_SHA
            or assets.get('model_id') != 'meta-llama/Llama-3.1-8B-Instruct'):
        raise ValueError('Host manifest must identify the verified Llama-3.1-8B-Instruct checkpoint')
    source_files = {}

    def actual(name):
        entry = assets['files'][name]
        path = (manifest_path.parent / entry['path']).resolve(strict=True)
        path.relative_to(manifest_path.parent)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if len(data) != entry['size'] or digest != entry['sha256']:
            raise ValueError('Tokenizer/control file differs: ' + name)
        source_files[name] = dict(path=str(path), bytes=len(data), sha256=digest)
        return data

    config = json.loads(actual('config'))
    tokenizer_config = json.loads(actual('tokenizer_config'))
    generation = json.loads(actual('generation_config'))
    if generation.get('eos_token_id') != config.get('eos_token_id'):
        raise ValueError('Original model/generation EOS metadata disagree')
    actual('tokenizer')
    from tokenizers import Tokenizer, __version__ as tokenizers_version
    from jinja2.sandbox import ImmutableSandboxedEnvironment
    from jinja2 import __version__ as jinja2_version
    tokenizer = Tokenizer.from_file(source_files['tokenizer']['path'])
    environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)

    def fail(message):
        raise ValueError(message)

    environment.globals['raise_exception'] = fail
    template_text = tokenizer_config['chat_template']
    if not isinstance(template_text, str) or not template_text:
        raise ValueError('Original string chat_template is required')
    template = environment.from_string(template_text)
    bos, eos = tokenizer_config['bos_token'], tokenizer_config['eos_token']
    bos = bos['content'] if isinstance(bos, dict) else bos
    eos = eos['content'] if isinstance(eos, dict) else eos
    if tokenizer.token_to_id(bos) != config['bos_token_id']:
        raise ValueError('BOS source identities disagree')
    conversations = json.loads(Path(messages_path).read_text(encoding='utf-8'))
    if not isinstance(conversations, list) or not 1 <= len(conversations) <= 16:
        raise ValueError('One to sixteen conversations required')
    requests, readable = [], []
    for record in conversations:
        if not isinstance(record, dict) or set(record) != {'slot', 'messages', 'max_new_tokens'}:
            raise ValueError('Conversation needs exactly slot, messages, max_new_tokens')
        messages = record['messages']
        if not isinstance(messages, list) or not messages:
            raise ValueError('Each conversation needs nonempty messages')
        for message in messages:
            if (not isinstance(message, dict) or set(message) != {'role', 'content'}
                    or message['role'] not in ('system', 'user', 'assistant')
                    or not isinstance(message['content'], str) or not message['content'].strip()):
                raise ValueError('Messages require role (system/user/assistant) and nonempty text content')
        if messages[-1]['role'] != 'user':
            raise ValueError('Conversation must end with a user message before the assistant header')
        rendered = template.render(messages=messages, bos_token=bos, eos_token=eos,
                                   add_generation_prompt=True)
        ids = tokenizer.encode(rendered, add_special_tokens=False).ids
        if not ids or ids[0] != config['bos_token_id'] or ids.count(config['bos_token_id']) != 1:
            raise ValueError('Template must contain exactly one initial BOS')
        if not rendered.endswith('<|start_header_id|>assistant<|end_header_id|>\n\n'):
            raise ValueError('Original assistant generation header missing')
        request = dict(slot=record['slot'], prompt_token_ids=ids,
                       max_new_tokens=record['max_new_tokens'])
        requests.append(request)
        readable.append(dict(**request, messages=messages, rendered_chat=rendered,
                             prompt_tokens=len(ids)))
    validate_requests(requests)
    maximum = max(len(row['prompt_token_ids']) for row in requests)
    rounds = max(len(row['prompt_token_ids']) + row['max_new_tokens'] - 1 for row in requests)
    metadata = dict(schema='scalellm_final_prepared_requests_v1', model_id=assets['model_id'],
                    checkpoint_sha256=CHECKPOINT_SHA,
                    host_manifest_sha256=sha(manifest_path), messages_sha256=sha(messages_path),
                    files=source_files,
                    template_sha256=hashlib.sha256(template_text.encode('utf-8')).hexdigest(),
                    bos_token_id=config['bos_token_id'], eos_token_ids=config['eos_token_id'],
                    generation_config=generation,
                    add_generation_prompt=True, tokenizer_add_special_tokens=False,
                    tokenizers_version=tokenizers_version, jinja2_version=jinja2_version,
                    maximum_prompt_tokens=maximum, maximum_full_rounds_without_EOS=rounds,
                    decoding='original greedy top1; original EOS retained',
                    hardware_execution='NOT_STARTED')
    out = Path(result).resolve()
    out.mkdir(parents=True, exist_ok=False)
    for name, data in (('requests.json', requests), ('requests_text.json', readable),
                       ('tokenizer_metadata.json', metadata)):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return dict(requests=str(out / 'requests.json'), count=len(requests),
                maximum_prompt_tokens=maximum, maximum_full_rounds_without_EOS=rounds,
                device_opened=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True)
    parser.add_argument('--messages', required=True)
    parser.add_argument('--result', required=True)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.assets, args.messages, args.result), indent=2))


if __name__ == '__main__':
    main()
