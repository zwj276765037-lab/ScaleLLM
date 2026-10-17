#!/usr/bin/env python3

import threading
import time
import unittest

from host.scalellm_runtime import (
    ATTENTION_COMPLETION,
    MLP_COMPLETION,
    CommandIdentity,
    Completion,
    CompletionFailure,
    CompletionScoreboard,
    CompletionStatus,
    DualCohortRuntime,
    Engine,
    RuntimeContractError,
    decode_completion,
)


class FakeBackend:
    def __init__(self):
        self.lock = threading.Lock()
        self.intervals = []

    def execute(self, engine, identity):
        start = time.monotonic_ns()
        time.sleep(0.003 if engine is Engine.ATTENTION else 0.002)
        end = time.monotonic_ns()
        with self.lock:
            self.intervals.append((engine, identity, start, end))
        return Completion(identity, CompletionStatus.SUCCESS)


class FakeHost:
    def after_attention(self, cohort_id, layer_id, buffer_id):
        time.sleep(0.0002)

    def after_mlp(self, cohort_id, layer_id, buffer_id):
        time.sleep(0.0002)


class ScaleLLMRuntimeTests(unittest.TestCase):
    def test_runtime_requires_exactly_two_cohorts(self):
        with self.assertRaisesRegex(ValueError, "exactly two"):
            DualCohortRuntime(
                FakeBackend(), FakeHost(), layers=1,
                cohort_ids=(0, 1, 2),
            )

    def test_runtime_accepts_explicit_unique_request_and_command_ids(self):
        backend = FakeBackend()
        runtime = DualCohortRuntime(
            backend, FakeHost(), layers=1, cohort_ids=(10, 11),
            request_ids=(101, 202), command_id_start=900,
        )
        report = runtime.run()
        identities = [item[1] for item in backend.intervals]
        self.assertEqual({item.request_id for item in identities}, {101, 202})
        self.assertEqual(
            sorted(item.command_id for item in identities),
            [900, 901, 902, 903],
        )
        self.assertEqual(report.commands_completed, 4)
        with self.assertRaisesRegex(ValueError, "request_ids"):
            DualCohortRuntime(
                FakeBackend(), FakeHost(), layers=1,
                request_ids=(1, 1),
            )
        with self.assertRaisesRegex(ValueError, "command_id_start"):
            DualCohortRuntime(
                FakeBackend(), FakeHost(), layers=1, command_id_start=0,
            )

    def test_decode_attention_and_mlp_completion(self):
        values = {
            0x078: 0xDEADBEEF, 0x07C: 7, 0x080: 0x00550023,
            0x084: 31, 0x088: (0 << 19) | (0 << 16) | 0x0055,
            0x288: 0xCAFEBABE, 0x28C: 8, 0x290: 0x00AA0042,
            0x294: 17, 0x298: (3 << 19) | (1 << 16) | 0x00AA,
            0x29C: 1,
        }
        attention = decode_completion(values.__getitem__, ATTENTION_COMPLETION)
        self.assertEqual(attention.identity, CommandIdentity(
            0xDEADBEEF, 7, 0x23, 0x55, 31, 0))
        self.assertIs(attention.status, CompletionStatus.SUCCESS)
        mlp = decode_completion(values.__getitem__, MLP_COMPLETION)
        self.assertEqual(mlp.identity, CommandIdentity(
            0xCAFEBABE, 8, 0x42, 0xAA, 17, 1))
        self.assertIs(mlp.status, CompletionStatus.FORMAT_ERROR)
        values[0x29C] = 0
        with self.assertRaises(RuntimeContractError):
            decode_completion(values.__getitem__, MLP_COMPLETION)

    def test_scoreboard_rejects_identity_and_status_errors(self):
        board = CompletionScoreboard()
        identity = CommandIdentity(1, 1, 2, 3, 4, 0)
        board.submit(Engine.ATTENTION, identity)
        wrong = CommandIdentity(1, 1, 2, 4, 4, 0)
        with self.assertRaises(RuntimeContractError):
            board.complete(Engine.ATTENTION,
                           Completion(wrong, CompletionStatus.SUCCESS))
        board.complete(Engine.ATTENTION,
                       Completion(identity, CompletionStatus.SUCCESS))
        error_identity = CommandIdentity(1, 2, 2, 3, 4, 1)
        board.submit(Engine.MLP, error_identity)
        with self.assertRaises(CompletionFailure):
            board.complete(Engine.MLP,
                           Completion(error_identity,
                                      CompletionStatus.DDR_ERROR))
        self.assertFalse(board.outstanding)

    def test_dual_cohort_pipeline_preserves_dependencies_and_overlaps(self):
        backend = FakeBackend()
        runtime = DualCohortRuntime(
            backend, FakeHost(), layers=3, cohort_ids=(10, 11))
        report = runtime.run()
        self.assertEqual(report.completed_rows, 32)
        self.assertEqual(report.commands_submitted, 12)
        self.assertEqual(report.commands_completed, 12)
        self.assertFalse(runtime.scoreboard.outstanding)

        by_engine = {engine: [] for engine in Engine}
        per_cohort = {10: [], 11: []}
        for engine, identity, start, end in backend.intervals:
            by_engine[engine].append((start, end))
            per_cohort[identity.cohort_id].append(identity)
        for identities in per_cohort.values():
            self.assertEqual(
                [(item.layer_id, item.op_id) for item in identities],
                [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)])
        overlap = any(
            max(a_start, m_start) < min(a_end, m_end)
            for a_start, a_end in by_engine[Engine.ATTENTION]
            for m_start, m_end in by_engine[Engine.MLP])
        self.assertTrue(overlap, "Attention and MLP never overlapped")


if __name__ == "__main__":
    unittest.main()
