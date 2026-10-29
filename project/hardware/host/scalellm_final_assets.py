"""Real final deployment bindings: frozen weights, per-row RoPE and Host Down."""
from __future__ import annotations

import hashlib

import numpy as np

from .scalellm_final_layout import ROPE_BASE, layer_spans


def build_row_rope(config, rows):
    """Original Llama3 scaling/half-away packing for sixteen actual positions."""
    from model.export_scalellm_llama31_artifacts import build_rope
    if len(rows) != 16:
        raise ValueError("RoPE requires sixteen fixed request rows")
    cache = {}
    output = bytearray()
    for row in rows:
        if row.active:
            if not 0 <= row.position <= 127 or row.epoch == 0:
                raise ValueError("invalid active RoPE owner")
            if row.position not in cache:
                # The first row of the original generator gives this absolute
                # position with precisely the original scaling and rounding.
                cache[row.position] = build_rope(config, query_start=row.position)[:512]
            output.extend(cache[row.position])
        else:
            output.extend(bytes(512))
    if len(output) != 8192:
        raise AssertionError("row RoPE size drift")
    return bytes(output)


class FinalAssetStore:
    def __init__(self, backend, artifacts, host_assets):
        self.backend, self.artifacts, self.host_assets = backend, artifacts, host_assets
        self.recovery_generation = backend.recovery_generation if backend is not None else None
        self.resident = False
        self.generation = 0
        self.prepared_layer = None
        self.down_weights = None
        self.receipts = []

    def _quiescent(self):
        self._require_session()
        self.backend.require_quiescent()

    def _require_session(self):
        if self.backend is not None and self.backend.recovery_generation != self.recovery_generation:
            self.resident = False
            self.prepared_layer = None
            self.down_weights = None
            raise RuntimeError("reset invalidated asset residency; create a new final asset store")

    def _write(self, channel, address, payload, label):
        session = self.backend.session
        if session.h2c_write_local(channel, payload, address, 1 << 20) != len(payload):
            raise IOError("short final asset write: " + label)
        actual = session.c2h_read_local(channel, len(payload), address, 1 << 20)
        if actual != payload:
            raise IOError("final asset DDR readback mismatch: " + label)
        self.receipts.append(dict(label=label, channel=channel, address=address,
                                  bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest()))

    def load_resident(self):
        self._quiescent()
        if self.resident:
            raise RuntimeError("resident assets already owned by this session")
        for layer in range(32):
            for name, span in layer_spans(layer).items():
                data = self.artifacts.original.layer_artifact(layer, name).read_verified()
                if len(data) != span.size:
                    raise ValueError("final resident artifact size mismatch")
                self._write(span.channel, span.address, data, f"layer{layer}/{name}")
        self.resident = True

    def prepare_layer(self, layer, rows):
        self._quiescent()
        if not self.resident:
            raise RuntimeError("final resident assets not loaded")
        for name, address in (("mlp_gate_up_c0", 0), ("mlp_gate_up_c1", 0x01c00000)):
            payload = self.artifacts.original.layer_artifact(layer, name).read_verified()
            self._write(1, address, payload, f"layer{layer}/{name}")
        self._write(0, ROPE_BASE, build_row_rope(self.host_assets.config, rows), "row_rope")
        self.down_weights = self.artifacts.down_weights(layer)
        self.prepared_layer = layer
        if self.generation == 0xffffffff:
            raise OverflowError("weight staging identity exhausted")
        self.generation += 1
        return self.generation

    def run(self, layer, down_input):
        from .scalellm_mlp_linear import unpack_a8_rec576
        from .scalellm_mlp_gu_only import down_blocked_int64
        self._require_session()
        if layer != self.prepared_layer or self.down_weights is None:
            raise RuntimeError("Host Down weight owner mismatch")
        q, metadata = unpack_a8_rec576(down_input, groups=448)
        return down_blocked_int64(q, metadata, self.down_weights)


class FinalHostAssetsModel:
    """Bind exported read-only CPU assets to the runtime's host model seam."""
    def __init__(self, assets, lm_head_chunk_rows=2048):
        self.assets = assets
        self.norm_weights = assets.weights
        self.lm_head_chunk_rows = lm_head_chunk_rows

    def embed(self, tokens):
        return self.assets.embed(tokens)

    def evaluate(self, normalized, target_tokens, top_k=1):
        from .scalellm_final_lm_head import streaming_lm_head
        return streaming_lm_head(normalized, target_tokens, self.assets.lm_head.shape[0],
                                 lambda start, stop: np.asarray(self.assets.lm_head[start:stop]),
                                 self.lm_head_chunk_rows, top_k)
