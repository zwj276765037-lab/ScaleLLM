#!/usr/bin/env python3

import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from model.export_scalellm_llama31_artifacts import (
    COLS,
    LlamaCheckpoint,
    build_rope,
    encode_scales,
    interleaved_rope_row_map,
    pack_attention_meta,
    pack_mlp_meta,
    pack_w4,
    quantize_folded_rows,
)
from model.verify_scalellm_real_mlp_artifacts import (
    decode_mlp_meta_record,
    decode_w4_channel_record,
    down_record_location,
    gate_record_location,
)


class ScaleLLMExportTests(unittest.TestCase):
    def test_checkpoint_metadata_requires_instruct_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            base_dir = root / "Llama-3.1-8B"
            base_dir.mkdir()
            with self.assertRaisesRegex(ValueError, "checkpoint directory must be"):
                LlamaCheckpoint(base_dir)

            model_dir = root / "Llama-3.1-8B-Instruct"
            model_dir.mkdir()
            config = {
                "hidden_size": 4096,
                "intermediate_size": 14336,
                "num_hidden_layers": 32,
                "num_attention_heads": 32,
                "num_key_value_heads": 8,
                "vocab_size": 128256,
                "architectures": ["LlamaForCausalLM"],
                "rms_norm_eps": 1e-5,
                "eos_token_id": [128001, 128009],
                "_name_or_path": "meta-llama/Llama-3.1-8B-Instruct",
            }
            tokenizer = {
                "name_or_path": "meta-llama/Llama-3.1-8B-Instruct",
                "chat_template": "<|start_header_id|>user<|eot_id|>",
                "eos_token": "<|eot_id|>",
            }
            special = {"eos_token": {"content": "<|eot_id|>"}}
            (model_dir / "model.safetensors.index.json").write_text(
                json.dumps({"weight_map": {}}), encoding="utf-8"
            )
            (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

            def write_metadata():
                for name, value in (
                    ("config.json", config),
                    ("tokenizer_config.json", tokenizer),
                    ("special_tokens_map.json", special),
                ):
                    (model_dir / name).write_text(json.dumps(value), encoding="utf-8")

            write_metadata()
            checkpoint = LlamaCheckpoint(model_dir)
            _, identity = checkpoint.source_identity()
            self.assertEqual(identity["model_id"],
                             "meta-llama/Llama-3.1-8B-Instruct")

            config["_name_or_path"] = "meta-llama/Llama-3.1-8B"
            write_metadata()
            with self.assertRaisesRegex(ValueError, "different model"):
                LlamaCheckpoint(model_dir)
            config["_name_or_path"] = "meta-llama/Llama-3.1-8B-Instruct"

            config["eos_token_id"] = [128001]
            write_metadata()
            with self.assertRaisesRegex(ValueError, "EOS IDs"):
                LlamaCheckpoint(model_dir)
            config["eos_token_id"] = [128001, 128009]

            tokenizer["chat_template"] = ""
            write_metadata()
            with self.assertRaisesRegex(ValueError, "chat template"):
                LlamaCheckpoint(model_dir)
            tokenizer["chat_template"] = "<|start_header_id|>user<|eot_id|>"

            special["eos_token"] = "<|end_of_text|>"
            write_metadata()
            with self.assertRaisesRegex(ValueError, "Instruct EOT"):
                LlamaCheckpoint(model_dir)

    def test_attention_and_mlp_metadata_have_distinct_frozen_layouts(self):
        codes = np.arange(1, COLS + 1, dtype=np.uint8)
        shifts = np.arange(COLS, dtype=np.uint8)
        attention = pack_attention_meta(codes, shifts)
        self.assertEqual(len(attention), 32)
        self.assertEqual(attention[:6], bytes((1, 0, 2, 1, 3, 2)))

        mlp = pack_mlp_meta(codes, shifts)
        self.assertEqual(len(mlp), 32)
        self.assertEqual(mlp[:16], codes.tobytes())
        shift_word = int.from_bytes(mlp[16:28], "little")
        self.assertEqual(
            [(shift_word >> (6 * index)) & 0x3F for index in range(16)],
            shifts.tolist(),
        )
        self.assertEqual(mlp[28:], bytes(4))

    def test_w4_lane_zero_is_low_nibble(self):
        values = np.array((-8, 7, -1, 1), dtype=np.int8)
        self.assertEqual(pack_w4(values), bytes((0x78, 0x1F)))

    def test_hadamard_fold_quantization_is_deterministic(self):
        source = np.zeros((16, 32), dtype=np.float32)
        source[:, 0] = np.linspace(-1.0, 1.0, 16, dtype=np.float32)
        quantized, codes, shifts = quantize_folded_rows(source, 4)
        self.assertEqual(quantized.shape, (16, 1, 32))
        self.assertEqual(codes.shape, (16, 1))
        self.assertTrue(np.all(shifts <= 63))
        self.assertTrue(np.all((quantized >= -8) & (quantized <= 7)))
        self.assertTrue(np.all(quantized[7] != quantized[8]))

    def test_scale_encoder_and_rope_contract(self):
        codes, shifts, decoded = encode_scales(
            np.array((0.0, 0.125, 1.0), dtype=np.float32)
        )
        np.testing.assert_array_equal(codes, (0, 128, 128))
        np.testing.assert_array_equal(shifts, (0, 10, 7))
        np.testing.assert_array_equal(decoded, (0.0, 0.125, 1.0))
        config = {
            "rope_theta": 500000.0,
            "rope_scaling": {
                "factor": 8.0,
                "low_freq_factor": 1.0,
                "high_freq_factor": 4.0,
                "original_max_position_embeddings": 8192,
                "rope_type": "llama3",
            },
        }
        rope = build_rope(config)
        self.assertEqual(len(rope), 8192)
        self.assertEqual(int.from_bytes(rope[:8], "little"), 65536)

    def test_qk_permutation_interleaves_checkpoint_halves(self):
        mapping = interleaved_rope_row_map(1)
        np.testing.assert_array_equal(mapping[:8], (0, 64, 1, 65, 2, 66, 3, 67))
        self.assertEqual(mapping[-2:].tolist(), [63, 127])

    def test_real_mlp_verifier_decodes_frozen_payloads(self):
        values = np.arange(-8, 8, dtype=np.int8)
        source = np.tile(values, 16).reshape(8, 32)
        packed = pack_w4(source)
        np.testing.assert_array_equal(
            decode_w4_channel_record(packed), source
        )

        codes = np.arange(16, dtype=np.uint8) + 1
        shifts = np.arange(16, dtype=np.uint8) * 3
        decoded_codes, decoded_shifts = decode_mlp_meta_record(
            pack_mlp_meta(codes, shifts)
        )
        np.testing.assert_array_equal(decoded_codes, codes)
        np.testing.assert_array_equal(decoded_shifts, shifts)
        with self.assertRaisesRegex(ValueError, "padding"):
            decode_mlp_meta_record(pack_mlp_meta(codes, shifts)[:-1] + b"\x01")

    def test_real_mlp_verifier_maps_gate_and_down_record_order(self):
        gate_locations = [gate_record_location(index) for index in (
            0, 127, 128, 255, 256, 383, 384, 511, 512,
        )]
        self.assertEqual(
            [(item.operation, item.output_start, item.input_group)
             for item in gate_locations],
            [
                ("gate_proj", 0, 0),
                ("gate_proj", 0, 127),
                ("up_proj", 0, 0),
                ("up_proj", 0, 127),
                ("gate_proj", 16, 0),
                ("gate_proj", 16, 127),
                ("up_proj", 16, 0),
                ("up_proj", 16, 127),
                ("gate_proj", 32, 0),
            ],
        )
        self.assertEqual(
            down_record_location(256),
            down_record_location(0).__class__(
                256, "down_proj", 0, 1
            ),
        )
        self.assertEqual(down_record_location(255).output_start, 4080)


if __name__ == "__main__":
    unittest.main()
