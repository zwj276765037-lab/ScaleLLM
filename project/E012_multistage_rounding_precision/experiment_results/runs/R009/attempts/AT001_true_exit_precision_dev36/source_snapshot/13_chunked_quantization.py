"""Bounded row chunks of the unchanged production weight quantizer.

Every reduction/transform in quantize_folded_rows is confined to one row's
Group32. Chunking the outer row dimension preserves the arithmetic and avoids
large transient arrays. This is an experimental loading optimization only.
"""
from contextlib import contextmanager

import numpy as np


def quantize_chunks(source, weight_bits, production_quantize, rows_per_chunk=128):
    if source.ndim != 2 or source.shape[1] % 32 or rows_per_chunk < 1:
        raise ValueError('invalid chunked Group32 geometry')
    rows, columns = source.shape
    q = np.empty((rows, columns // 32, 32), dtype=np.int8)
    c = np.empty((rows, columns // 32), dtype=np.uint8)
    s = np.empty_like(c)
    for begin in range(0, rows, rows_per_chunk):
        end = min(begin + rows_per_chunk, rows)
        q[begin:end], c[begin:end], s[begin:end] = production_quantize(source[begin:end], weight_bits)
    return q, c, s


@contextmanager
def chunked_weight_context(v5, rows_per_chunk=128):
    original = v5.quantize_folded_rows
    def quantize(source, weight_bits):
        return quantize_chunks(source, weight_bits, original, rows_per_chunk)
    try:
        v5.quantize_folded_rows = quantize
        yield
    finally:
        v5.quantize_folded_rows = original
