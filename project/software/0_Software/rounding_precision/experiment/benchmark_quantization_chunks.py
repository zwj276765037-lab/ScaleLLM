"""CPU qualification of row-chunk loading on actual checkpoint weights."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time

from numerical_reference.model_compat import production_module
from numerical_reference.chunked_quantization import quantize_chunks


def digest(a): return hashlib.sha256(memoryview(a).cast('B')).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model-dir', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--wall-seconds', type=int, default=300)
    p.add_argument('--worker', action='store_true')
    a = p.parse_args()
    if not a.worker:
        from run_numerical_fidelity import cpu_supervise
        here = Path(__file__).resolve().parent
        dependencies = [here/'numerical_reference'/name for name in
                        ('chunked_quantization.py', 'model_compat.py', 'current_nodes.py', 'policy.py')]
        dependencies.extend([here.parents[2]/'model/export_scalellm_llama31_artifacts.py',
                             here.parents[2]/'0_Software/FPtoQ/experiment/v5_fullchain.py'])
        raise SystemExit(cpu_supervise(a, __file__, 'chunks', dependencies))
    a.output_dir.mkdir(parents=True, exist_ok=True)
    v5 = production_module()
    checkpoint = v5.LlamaCheckpoint(a.model_dir)
    records = []
    for name, bits in [('model.layers.0.self_attn.q_proj.weight', 8),
                       ('model.layers.0.mlp.gate_proj.weight', 4),
                       ('model.layers.0.mlp.down_proj.weight', 4)]:
        source = checkpoint.float32(name)
        begin = time.monotonic()
        expected = v5.quantize_folded_rows(source, bits)
        baseline = time.monotonic()-begin
        hashes = [digest(x) for x in expected]
        del expected
        for rows in (64, 128, 256):
            begin = time.monotonic()
            actual = quantize_chunks(source, bits, v5.quantize_folded_rows, rows)
            seconds = time.monotonic()-begin
            actual_hashes = [digest(x) for x in actual]
            if actual_hashes != hashes:
                raise AssertionError('chunked quantization changed weight codes or ScaleCode')
            record = dict(weight=name, shape=list(source.shape), bits=bits, chunk_rows=rows,
                baseline_seconds=baseline, chunk_seconds=seconds, speedup=baseline/seconds,
                output_hashes=hashes, byte_equal=True)
            records.append(record)
            print(json.dumps(record), flush=True)
            del actual
        del source
    import torch
    summary = dict(records=records, cuda_initialized=torch.cuda.is_initialized(),
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        scope='three actual layer0 full matrices; same production quantizer, outer-row chunks only')
    with (a.output_dir/'chunked_quantization_result.json').open('x') as out:
        json.dump(summary, out, indent=2)


if __name__ == '__main__': main()
