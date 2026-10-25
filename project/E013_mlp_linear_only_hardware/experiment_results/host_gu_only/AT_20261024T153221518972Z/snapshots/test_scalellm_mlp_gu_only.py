"""CPU format05 tests: independent scalar/full-K and einsum/floor-div gold."""
import functools
import hashlib
import json
import os
from pathlib import Path
import resource
import tempfile
import time
import unittest

import numpy as np

from host import scalellm_mlp_gu_only as down
from host.scalellm_artifacts import ArtifactRecord
from host.scalellm_mlp_gu_only_artifacts import normalize_weight_manifest_header
from host.scalellm_mlp_gu_only_abi import IDS
from host.scalellm_runtime import RuntimeContractError
from model.mlp_fixed import mlp_recover_down_guard_s45, round_shift_away_zero


def pack_reference(w, codes, shifts):
    """Export-layout producer; no production decoder/packing helper is called."""
    groups, columns, _ = w.shape
    tiles = columns // 16
    grouped = w.reshape(groups, tiles, 16, 32)
    halves = []
    for first in (0, 8):
        lanes = grouped[:, :, first:first + 8].reshape(groups, tiles, 256).astype(np.int16) & 15
        halves.append((lanes[..., 0::2] | (lanes[..., 1::2] << 4)).astype(np.uint8).tobytes())
    result = bytearray(groups * tiles * 32)
    for group in range(groups):
        for tile in range(tiles):
            word = 0
            for lane in range(16):
                col = tile * 16 + lane
                word |= int(codes[group, col]) << (lane * 8)
                word |= int(shifts[group, col]) << (128 + lane * 6)
            offset = (group * tiles + tile) * 32
            result[offset:offset + 32] = word.to_bytes(32, "little")
    return *halves, bytes(result)


@functools.lru_cache(maxsize=2)
def fixture(columns=48):
    g = np.arange(448, dtype=np.int64)[:, None, None]
    c = np.arange(columns, dtype=np.int64)[None, :, None]
    k = np.arange(32, dtype=np.int64)[None, None, :]
    w = ((7 * g + 3 * c + 11 * k) % 16 - 8).astype(np.int8)
    codes = (1 + (3 * g[..., 0] + 5 * c[..., 0]) % 7).astype(np.uint8)
    shifts = (6 + 10 * ((g[..., 0] + c[..., 0]) % 3) + g[..., 0] % 2).astype(np.uint8)
    r = np.arange(16, dtype=np.int64)[:, None, None]
    gq = np.arange(448, dtype=np.int64)[None, :, None]
    zp = 120 + np.arange(16, dtype=np.int64)[:, None] % 9
    q = (zp[..., None] + (3 * gq + 5 * r + 7 * k) % 31 - 15).astype(np.uint8).reshape(16, 14336)
    ac = np.broadcast_to(1 + np.arange(16)[:, None] % 7, (16, 448))
    ash = 6 + (np.arange(16)[:, None] + np.arange(448)[None, :]) % 2
    meta = (zp | (ac << 8) | (ash << 16)).astype(np.uint32)
    return w, codes, shifts, q, meta


def independent_vector_reference(q, metadata, w, codes, shifts):
    """Distinct dot/restore core: group-major einsum and floor integer division.

    It uses mathematical producer arrays, not DownWeights decoded arrays or
    optimized matmul/alignment/finalization helpers.
    """
    acc = np.zeros((16, w.shape[1]), np.int64)
    for group in range(448):
        m = metadata[:, group].astype(np.int64)
        a = q[:, group * 32:(group + 1) * 32].astype(np.int64) - (m & 255)[:, None]
        dot = np.einsum("rk,ck->rc", a, w[group].astype(np.int64), dtype=np.int64, optimize=False)
        raw = dot * ((m >> 8) & 255)[:, None] * codes[group].astype(np.int64)[None, :]
        shift = ((m >> 16) & 63)[:, None] + shifts[group].astype(np.int64)[None, :]
        live = (((m >> 8) & 255)[:, None] != 0) & (codes[group][None, :] != 0)
        shift = np.where(live, shift, 24)
        left = np.power(np.int64(2), np.maximum(24 - shift, 0))
        denominator = np.power(np.int64(2), np.maximum(shift - 24, 0))
        acc += np.floor_divide(raw * left, denominator)
    positive = np.floor_divide(np.abs(acc) + 128, 256)
    result = np.where(acc < 0, -positive, positive)
    return np.minimum(2147483647, np.maximum(-2147483648, result))


class HostDownTests(unittest.TestCase):
    def test_full_shape_16x4096_independent_reference_and_scalar_samples(self):
        started = time.perf_counter()
        w, codes, shifts, q, meta = fixture(4096)
        packed = pack_reference(w, codes, shifts)
        packed_at = time.perf_counter()
        decoded = down.DownWeights.from_records(*packed, layer_id=3)
        decoded_at = time.perf_counter()
        np.testing.assert_array_equal(decoded.values, w)
        np.testing.assert_array_equal(decoded.codes, codes)
        np.testing.assert_array_equal(decoded.shifts, shifts)
        actual = down.down_blocked_int64(q, meta, decoded)
        optimized_at = time.perf_counter()
        expected = independent_vector_reference(q, meta, w, codes, shifts)
        reference_at = time.perf_counter()
        np.testing.assert_array_equal(actual, expected)
        cols = [0, 7, 8, 15, 16, 31, 47, 255, 2047, 4080, 4087, 4088, 4094, 4095]
        scalar = down.down_scalar_oracle(q, meta, decoded, rows=tuple(range(16)), columns=cols)
        np.testing.assert_array_equal(scalar, expected[:, cols])
        scalar_at = time.perf_counter()
        metrics = dict(shape=[16,4096],groups=448,macs=939524096,
                       synthetic=True,real_model=False,warmup=False,
                       fixture_and_export_seconds=packed_at-started,
                       strict_decode_seconds=decoded_at-packed_at,
                       optimized_down_seconds=optimized_at-decoded_at,
                       independent_vector_seconds=reference_at-optimized_at,
                       bounded_scalar_seconds=scalar_at-reference_at,
                       bounded_scalar_coordinates=16*len(cols),
                       rss_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       threads={k:os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS")},
                       input_sha256={name:hashlib.sha256(value.tobytes()).hexdigest() for name,value in
                         (("q",q),("metadata",meta),("W4",w),("weight_code",codes),("weight_shift",shifts))},
                       original_records_sha256=decoded.source_sha256,
                       output_sha256=hashlib.sha256(actual.astype("<i4").tobytes()).hexdigest())
        evidence = os.environ.get("HOST_GU_ONLY_EVIDENCE_DIR")
        if evidence:
            target = Path(evidence)
            (target/"full_shape_metrics.json").write_text(json.dumps(metrics,indent=2)+"\n")
            np.savez_compressed(target/"full_shape_outputs.npz",actual=actual,independent=expected,scalar=scalar,scalar_columns=cols)
        print("HOST_DOWN_FULL_SHAPE",json.dumps(metrics,sort_keys=True))

    def test_small_columns_completeK_and_block_tails(self):
        w,c,s,q,m = fixture()
        weights = down.DownWeights.from_records(*pack_reference(w,c,s),columns=48)
        expected = independent_vector_reference(q,m,w,c,s)
        scalar = down.down_scalar_oracle(q,m,weights,rows=(0,7,8,10,15),columns=(0,7,8,15,16,31,32,47))
        np.testing.assert_array_equal(scalar,expected[np.ix_((0,7,8,10,15),(0,7,8,15,16,31,32,47))])
        for cb,gb in ((17,7),(48,448),(1,64)):
            np.testing.assert_array_equal(down.down_blocked_int64(q,m,weights,column_block=cb,group_block=gb,require_production_shape=False),expected)

    def test_original_record_byte_indices_all_group_tile_half_boundaries(self):
        w,c,s,_,_ = fixture()
        p0,p1,pm = pack_reference(w,c,s)
        got = down.DownWeights.from_records(p0,p1,pm,columns=48)
        for g in (0,1,127,128,255,447):
            for col in (0,7,8,15,16,31,32,39,40,47):
                record=g*3+col//16
                for k in (0,1,15,16,30,31):
                    half=(col%16)//8
                    nibble=((col%8)*32+k)
                    raw=(p0,p1)[half][record*128+nibble//2]
                    expected=(raw>>(4*(nibble%2)))&15
                    if expected>=8:expected-=16
                    self.assertEqual(int(got.values[g,col,k]),expected)
                word=int.from_bytes(pm[record*32:record*32+32],"little")
                self.assertEqual(int(got.codes[g,col]),(word>>((col%16)*8))&255)
                self.assertEqual(int(got.shifts[g,col]),(word>>(128+(col%16)*6))&63)

    def test_decoder_rejects_padding_sizes_and_zero_shift(self):
        w,c,s,_,_=fixture();p0,p1,pm=pack_reference(w,c,s)
        for record in (0,3*128+2,3*448-1):
            broken=bytearray(pm);broken[record*32+31]=1
            with self.assertRaisesRegex(down.HostDownFormatError,"padding"):
                down.DownWeights.from_records(p0,p1,broken,columns=48)
        for values in ((p0[:-1],p1,pm),(p0,p1+b"x",pm),(p0,p1,pm[:-32])):
            with self.assertRaises(down.HostDownFormatError):down.DownWeights.from_records(*values,columns=48)
        bad=c.copy();bad[447,47]=0
        with self.assertRaisesRegex(down.HostDownFormatError,"zero weight code"):
            down.DownWeights.from_records(*pack_reference(w,bad,s),columns=48)

    def test_immutable_layer_handle_cannot_be_overwritten(self):
        w,c,s,_,_=fixture();handle=down.DownWeights(w,c,s,layer_id=2)
        for array in (handle.values,handle.codes,handle.shifts):
            with self.assertRaises(ValueError):array.setflags(write=True)
            with self.assertRaises(ValueError):array.flat[0]=0

    def test_zero_codes_and_signed_right_shift(self):
        w,c,s,q,m=[x.copy() for x in fixture()]
        c[::2]=0;s[::2]=0
        q[15]=0;m[15]=0
        handle=down.DownWeights(w,c,s)
        actual=down.down_blocked_int64(q,m,handle,require_production_shape=False)
        np.testing.assert_array_equal(actual,independent_vector_reference(q,m,w,c,s))
        self.assertTrue(np.all(actual[15]==0))
        self.assertEqual(down.recover_down_guard_scalar(-1,25),-1)
        self.assertEqual(down.recover_down_guard_scalar(-129,25),-65)

    def test_shift_boundaries_do_not_wrap_u6_sum(self):
        w,c,s,q,m=[x.copy() for x in fixture()]
        m[:]=(255<<8)|(6<<16)|128
        for total in (12,20,23,24,44):
            s[:]=total-6;h=down.DownWeights(w,c,s)
            got=down.down_blocked_int64(q,m,h,require_production_shape=False)
            np.testing.assert_array_equal(got,independent_vector_reference(q,m,w,c,s))
        for ash,wsh in ((6,5),(6,39),(63,63)):
            m[:]=(1<<8)|(ash<<16)|128;s[:]=wsh
            h=down.DownWeights(w,c,s)
            with self.assertRaisesRegex(down.HostDownFormatError,"shift"):
                down.down_blocked_int64(q,m,h,require_production_shape=False)
            with self.assertRaises(down.HostDownFormatError):down.down_scalar_oracle(q,m,h)

    def test_S45_S54_edges_ties_and_S32_saturation(self):
        for raw in (-(1<<32),(1<<32)-1,-1,1,-4244832000,4244832000):
            for shift in (12,23,24,25,44):
                self.assertEqual(down.recover_down_guard_scalar(raw,shift),mlp_recover_down_guard_s45(raw,shift))
        for acc in (-(1<<53),(1<<53)-1,-384,-128,-127,127,128,384,(2147483647<<8)+128,-(2147483648<<8)-128):
            expected=max(-2147483648,min(2147483647,round_shift_away_zero(acc,8)))
            self.assertEqual(down.finalize_down_scalar(acc),expected)
        for acc in (-(1<<53)-1,1<<53):
            with self.assertRaises(down.HostDownFormatError):down.finalize_down_scalar(acc)

    def test_extreme_dot_and_codes_fullK_saturate_exactly(self):
        q=np.zeros((16,14336),np.uint8);q[::2]=255
        m=np.full((16,448),(6<<16)|(255<<8),np.uint32);m[1::2]|=255
        w=np.full((448,16,32),-8,np.int8)
        codes=np.full((448,16),255,np.uint8);shifts=np.full((448,16),6,np.uint8)
        h=down.DownWeights(w,codes,shifts)
        got=down.down_blocked_int64(q,m,h,require_production_shape=False)
        self.assertTrue(np.all(got[::2]==-2147483648));self.assertTrue(np.all(got[1::2]==2147483647))
        np.testing.assert_array_equal(got,independent_vector_reference(q,m,w,codes,shifts))

    def test_malformed_activation_and_scalar_bound_are_rejected(self):
        w,c,s,q,m=fixture();h=down.DownWeights(w,c,s)
        with self.assertRaises(TypeError):down.down_blocked_int64(q.astype(float),m,h,require_production_shape=False)
        for changed in (m|(1<<22),np.zeros((8,448),np.uint32)):
            with self.assertRaises(down.HostDownFormatError):down.down_blocked_int64(q,changed,h,require_production_shape=False)
        with self.assertRaises(down.HostDownFormatError):down.down_blocked_int64(q,np.zeros_like(m),h,require_production_shape=False)
        with self.assertRaises(ValueError):down.down_scalar_oracle(q,m,h,rows=tuple(range(16)),columns=tuple(range(48)))
        with self.assertRaises(down.HostDownFormatError):down.down_blocked_int64(q,m,h)

    def test_verified_artifact_reads_reject_tamper_before_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"weights.bin";p.write_bytes(b"correct")
            record=ArtifactRecord(p,7,hashlib.sha256(b"correct").hexdigest())
            p.write_bytes(b"corrupt")
            with self.assertRaises(RuntimeContractError):
                down.DownWeights.from_artifact_records(record,record,record,layer_id=0)

    def test_schema2_v5_weights_and_schema3_are_independent_of_runtime_v7(self):
        common=dict(schema_version=2,model_id="meta-llama/Llama-3.1-8B-Instruct",checkpoint_id="a"*64,
                    checkpoint_sha256="a"*64,layer_count=32,attention_format_id=0x48384103,
                    attention_abi=0x00020000,mlp_format_id=0x48384605,mlp_abi=0x00050000,rope={},layers=[])
        self.assertEqual(normalize_weight_manifest_header(common)["weight_layout_id"],IDS["weight_layout"])
        schema3={**common,"schema_version":3,"mlp_weight_layout_id":IDS["weight_layout"]};del schema3["mlp_abi"]
        self.assertEqual(normalize_weight_manifest_header(schema3)["schema_version"],3)
        for changed in ({**common,"mlp_abi":0x00070000},{**common,"mlp_abi":0x00060000},
                        {**schema3,"mlp_weight_layout_id":0x00070000},{**schema3,"unknown":0}):
            with self.assertRaises(RuntimeContractError):normalize_weight_manifest_header(changed)


if __name__=="__main__":unittest.main()
