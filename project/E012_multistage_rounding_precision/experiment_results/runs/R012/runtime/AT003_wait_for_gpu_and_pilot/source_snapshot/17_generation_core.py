"""Dependency-free controls for matched-prompt, independently decoded pairs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path


def token_identity(tokens):
    """Canonical JSON integer-list identity, independent of host byte order."""
    values = [int(x) for x in tokens]
    return dict(count=len(values), sha256=hashlib.sha256(
        json.dumps(values, separators=(',', ':')).encode('ascii')).hexdigest(),
        encoding='ASCII canonical compact JSON integer list')


def read_prompts(path):
    rows = [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
    identifiers = []
    for row in rows:
        key = row.get('prompt_id', row.get('id'))
        if not isinstance(key, str) or not key or not isinstance(row.get('prompt'), str) or not row['prompt'].strip():
            raise ValueError('Each prompt requires a unique nonempty string id/prompt_id and prompt')
        row['prompt_id'] = key
        identifiers.append(key)
        actual = hashlib.sha256(row['prompt'].encode()).hexdigest()
        if row.get('prompt_sha256', actual) != actual:
            raise ValueError('Prompt text hash differs: ' + key)
    if not rows or len(set(identifiers)) != len(identifiers):
        raise ValueError('Prompt collection must be nonempty with unique IDs')
    return rows


def generation_budget(prompt_tokens, max_context, max_new_tokens):
    if not 1 <= prompt_tokens < max_context <= 32768 or not 1 <= max_new_tokens <= 32768:
        raise ValueError('Invalid context or generation token budget')
    # Reject instead of silently granting different or insufficient caps by item.
    if prompt_tokens + max_new_tokens > max_context:
        raise ValueError('Full common response budget does not fit the prompt; no silent prompt truncation')
    return max_new_tokens


def decode_arm(prompt_ids, step, stop_ids, max_new_tokens, max_context, on_token=None):
    """step(prefix, first) returns one freely selected token plus diagnostics.

    Every arm starts with a new prefix, and receives only its own generated IDs.
    EOS/eot is retained in raw tokens and terminates immediately. A fixed cap is
    shared across arms; early stopping never lowers the other arm's allowance.
    """
    prompt_ids = [int(x) for x in prompt_ids]
    cap = generation_budget(len(prompt_ids), max_context, max_new_tokens)
    prefix = list(prompt_ids)
    generated = []
    steps = []
    for index in range(cap):
        token, diagnostic = step(list(prefix), index == 0)
        token = int(token)
        if token < 0:
            raise ValueError('Invalid negative generated token')
        prefix.append(token)
        generated.append(token)
        steps.append(diagnostic)
        if on_token is not None:
            on_token(index, token, diagnostic)
        if token in stop_ids:
            return dict(generated_token_ids=generated, stop_reason='stop_token',
                        stop_token_id=token, eos_seen=True, truncated=False,
                        token_identity=token_identity(generated), steps=steps)
    return dict(generated_token_ids=generated, stop_reason='max_new_tokens',
                stop_token_id=None, eos_seen=False, truncated=True,
                token_identity=token_identity(generated), steps=steps)


def pair_summary(a, b):
    x, y = a['generated_token_ids'], b['generated_token_ids']
    first = next((i for i, (u, v) in enumerate(zip(x, y)) if u != v), None)
    if first is None and len(x) != len(y):
        first = min(len(x), len(y))
    return dict(identical_token_sequences=x == y, first_divergence_index=first,
                current_tokens=len(x), output_only_tokens=len(y),
                both_complete=not a['truncated'] and not b['truncated'])
