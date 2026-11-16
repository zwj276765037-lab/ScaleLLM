"""Explicit deployment policies and fixed-position benchmark acceptance."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable

from .common import ROOT, sha, validate_requests

DECODE = 'decode'
BENCHMARK_KV128 = 'benchmark-kv128'
ORIGINAL_REQUESTS_SHA = '9d0db082e3504b2077971f0a3a1370f70c27474dd746dc7309ebca6c818444ed'


@dataclass
class RunHooks:
    before_command: Callable | None = None
    after_command: Callable | None = None
    before_step: Callable | None = None
    after_step: Callable | None = None
    finalize: Callable | None = None

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            callback = getattr(self, name)
            if callback is not None and not callable(callback):
                raise ValueError('Run hook must be callable: ' + name)


def policy_description(name=DECODE):
    if name == DECODE:
        return dict(name=name, greedy_top1=True, eos_retirement=True,
                    max_new_tokens=32, fixed_positions=None)
    if name == BENCHMARK_KV128:
        return dict(name=name, greedy_top1=True, eos_retirement=False,
                    generation_budget='129 - prompt_length', fixed_positions=128,
                    active_mask=0xffff, hardware_commands=8192)
    raise ValueError('Unsupported execution policy: ' + str(name))


def benchmark_requests(source=None):
    source = Path(source or ROOT / 'examples/requests16.json')
    if sha(source) != ORIGINAL_REQUESTS_SHA:
        raise ValueError('KV128 benchmark requires the published original 16 requests')
    original = validate_requests(json.loads(source.read_text(encoding='utf-8')))
    if [request['slot'] for request in original] != list(range(16)):
        raise ValueError('KV128 benchmark requires slots 0..15 in order')
    return [dict(slot=request['slot'], prompt_token_ids=list(request['prompt_token_ids']),
                 max_new_tokens=129 - len(request['prompt_token_ids']))
            for request in original]


def validate_execution_requests(requests, policy=DECODE):
    policy_description(policy)
    if policy == DECODE:
        return validate_requests(requests)
    if requests != benchmark_requests():
        raise ValueError('KV128 requests must retain the published prompts and fixed-position budgets')
    # Equality alone accepts booleans as integers. Validate every original
    # field with the ordinary request contract before comparing budgets.
    ordinary = [dict(request, max_new_tokens=32) for request in requests]
    validate_requests(ordinary)
    if any(type(request['max_new_tokens']) is not int for request in requests):
        raise ValueError('KV128 generation budgets must be integers')
    return requests


def create_runtime(backend, model, assets, eos_token_ids=(), *, execution_policy=DECODE):
    from host.scalellm_final_runtime import FinalDecodeRuntime
    policy = policy_description(execution_policy)
    stops = eos_token_ids if policy['eos_retirement'] else ()
    return FinalDecodeRuntime(backend, model, assets, stops)


def allocate_requests(runtime, requests, *, execution_policy=DECODE):
    validate_execution_requests(requests, execution_policy)
    for request in requests:
        maximum = request['max_new_tokens']
        if execution_policy == BENCHMARK_KV128:
            # Position 127 produces one final prediction without consuming it
            # as a position-128 input, matching the historical benchmark.
            runtime.allocate(request['slot'], request['prompt_token_ids'], maximum - 1)
            runtime.slots[request['slot']].max_new_tokens = maximum
        else:
            runtime.allocate(request['slot'], request['prompt_token_ids'], maximum)


def validate_benchmark_report(report, eos_token_ids=()):
    requests = validate_execution_requests(report['requests'], BENCHMARK_KV128)
    steps, receipts = report['steps'], report['receipts']
    if len(steps) != 128 or len(receipts) != 8192:
        raise ValueError('KV128 requires 128 committed steps and 8192 commands')
    for index, step in enumerate(steps):
        if (step['index'] != index or step['active_mask'] != 0xffff
                or step['positions_before'] != [index] * 16 or len(step['slots']) != 16):
            raise ValueError('KV128 committed step position/active mask mismatch')
        for state, request in zip(step['slots'], requests):
            expected_count = max(0, index + 2 - len(request['prompt_token_ids']))
            if (state['epoch'] != 1 or state['position'] != index + 1
                    or state['finished'] != (index == 127)
                    or len(state['generated']) != expected_count):
                raise ValueError('KV128 slot commit/retirement mismatch')
    for index, receipt in enumerate(receipts):
        if (receipt['command_id'] != index + 1 or receipt['active_mask'] != 0xffff
                or receipt['layer'] != (index % 64) // 2
                or receipt['opcode'] != 1 + index % 2):
            raise ValueError('KV128 command identity/active mask mismatch')
    eos = set(eos_token_ids)
    first_eos, counts = {}, {}
    for request in requests:
        slot = str(request['slot'])
        tokens = report['outputs'][slot]
        if (len(tokens) != request['max_new_tokens']
                or tokens != steps[-1]['slots'][request['slot']]['generated']
                or any(type(token) is not int or not 0 <= token < 128256 for token in tokens)):
            raise ValueError('KV128 output token count/content mismatch')
        counts[slot] = len(tokens)
        first_eos[slot] = next((dict(generated_index_one_based=index + 1, token_id=token)
                                for index, token in enumerate(tokens) if token in eos), None)
    return dict(schema='scalellm_kv128_fixed_length_acceptance_v1', verdict='PASS',
                committed_steps=128, commands=8192, active_slots=16,
                active_mask_each_step=[step['active_mask'] for step in steps],
                last_position_committed=127, full_output_round_committed=True,
                eos_retirement=False, eos_token_ids=sorted(eos),
                first_eos_by_slot=first_eos, generated_token_counts=counts,
                numerical_verification=report['numerical_verification'])
