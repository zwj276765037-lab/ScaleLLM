#!/usr/bin/env python3
"""Run the frozen Dell inference entry with read-only QPC command tracing.

This wrapper substitutes only the XDMA session class. It calls the frozen
runner's original main() and preserves every CSR transaction and model value.
"""

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import time


def qpc_clock():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    integer = ctypes.c_longlong
    kernel.QueryPerformanceCounter.argtypes = [ctypes.POINTER(integer)]
    kernel.QueryPerformanceCounter.restype = ctypes.c_int
    kernel.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(integer)]
    kernel.QueryPerformanceFrequency.restype = ctypes.c_int
    frequency = integer()
    if not kernel.QueryPerformanceFrequency(ctypes.byref(frequency)) or frequency.value <= 0:
        raise ctypes.WinError(ctypes.get_last_error())

    def now():
        value = integer()
        if not kernel.QueryPerformanceCounter(ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.value

    return now, frequency.value


def main():
    class PilotPrefixComplete(RuntimeError):
        pass

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--frozen-run", required=True)
    parser.add_argument("--command-trace", required=True)
    parser.add_argument("--pilot-max-commands", type=int, default=0)
    own, original_args = parser.parse_known_args()
    if sys.platform != "win32":
        raise RuntimeError("actual command tracing requires the Dell Windows host")
    frozen = Path(own.frozen_run).resolve()
    trace = Path(own.command_trace).resolve()
    if not frozen.is_file() or trace.exists() or not trace.parent.is_dir():
        raise ValueError("frozen runner must exist and command trace must be new")
    spec = importlib.util.spec_from_file_location("frozen_model_run", frozen)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import scalellm_windows_xdma as transport
    import host.scalellm_final_runtime as hardware_runtime
    from host.scalellm_final_abi import CSR, IDS, SPEC

    original_session = transport.WindowsXdmaSession
    qpc, frequency = qpc_clock()
    native_thread_id = ctypes.WinDLL("kernel32").GetCurrentThreadId
    native_thread_id.restype = ctypes.c_uint32
    words = SPEC["descriptor_words"]
    descriptor_base = CSR["DESCRIPTOR"]
    descriptor_fields = ("command_id", "layer", "opcode", "active_mask")
    trace.write_text(json.dumps({"record": "clock", "schema": "scalellm_command_qpc_v1",
                                 "qpc_frequency": frequency, "frozen_run": str(frozen),
                                 "host": os.environ.get("COMPUTERNAME"),
                                 "boot_utc": os.environ.get("SCALELLM_BOOT_UTC"),
                                 "run_id": os.environ.get("SCALELLM_RUN_ID"),
                                 "pid": os.getpid(), "thread_id": native_thread_id(),
                                 "started_ticks": qpc(), "started_utc_unix_ns": time.time_ns()}) + "\n")

    class TracedSession(original_session):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._descriptor = {}
            self._command = None
            self._input_transfer = None
            self._descriptor_write = None

        def _emit(self, record):
            with trace.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")

        def read32(self, offset):
            watched = ("STATUS", "ADMISSION_ERROR", "DONE_ERROR", "DONE_INPUT_BYTES",
                       "DONE_OUTPUT_BYTES", "DONE_CYCLES")
            if self._command is None or offset not in tuple(CSR[name] for name in watched):
                return super().read32(offset)
            before = qpc()
            try:
                value = super().read32(offset)
            except BaseException:
                self._command["read_error_at"] = offset
                self._command["read_error_before_ticks"] = before
                raise
            after = qpc()
            command = self._command
            if offset == CSR["STATUS"]:
                command["status_reads"] += 1
                observation = {"before_ticks": before, "after_ticks": after, "value": value}
                command["status_observations"].append(observation)
                if value & 1 and not value & 2:
                    if command["first_busy"] is None:
                        command["first_busy"] = observation
                    command["last_busy"] = observation
                    command["busy_reads"] += 1
                if value & 2 and command["first_done"] is None:
                    command["first_done"] = observation
                if value & 4 and command["first_error_status"] is None:
                    command["first_error_status"] = observation
            elif offset == CSR["DONE_CYCLES"]:
                command["done_cycles_read"] = {"before_ticks": before,
                                               "after_ticks": after, "value": value}
            else:
                command["completion_reads"].append({"register": next(name for name in watched if CSR[name] == offset),
                                                    "before_ticks": before, "after_ticks": after,
                                                    "value": value})
            return value

        def h2c_write_local(self, channel, data, local_offset, chunk_bytes):
            before = qpc()
            result = super().h2c_write_local(channel, data, local_offset, chunk_bytes)
            self._input_transfer = {"before_ticks": before, "after_ticks": qpc(),
                                    "bytes": len(data), "channel": channel}
            return result

        def c2h_read_local(self, channel, size, local_offset, chunk_bytes):
            before = qpc()
            result = super().c2h_read_local(channel, size, local_offset, chunk_bytes)
            if self._command is not None:
                self._command["output_transfer"] = {"before_ticks": before,
                                                   "after_ticks": qpc(), "bytes": len(result),
                                                   "channel": channel}
            return result

        def write32(self, offset, value):
            if descriptor_base <= offset < descriptor_base + 256 and offset % 4 == 0:
                index = (offset - descriptor_base) // 4
                self._descriptor[index] = value
                if index == 0:
                    self._descriptor_write = {"before_ticks": qpc(), "after_ticks": None}
                result = super().write32(offset, value)
                if index == 63 and self._descriptor_write is not None:
                    self._descriptor_write["after_ticks"] = qpc()
                return result
            if offset != CSR["ACTION"] or value not in (1, 2):
                return super().write32(offset, value)
            before = qpc()
            if value == 1:
                if self._command is not None:
                    raise RuntimeError("command trace found a second START before ACK")
                descriptor = {name: self._descriptor.get(words[name]) for name in descriptor_fields}
                raw_descriptor = struct.pack("<64I", *(self._descriptor[i] for i in range(64)))
                command = {"record": "command", "descriptor": descriptor,
                           "descriptor_words": [self._descriptor[i] for i in range(64)],
                           "descriptor_sha256": hashlib.sha256(raw_descriptor).hexdigest(),
                           "positions": [self._descriptor[32 + 2*i] for i in range(16)],
                           "epochs": [self._descriptor[33 + 2*i] for i in range(16)],
                           "core_hz": IDS["core_hz"],
                           "input_transfer": self._input_transfer,
                           "descriptor_write": self._descriptor_write,
                           "start_write": {"before_ticks": before, "after_ticks": None},
                           "first_busy": None, "last_busy": None, "first_done": None,
                           "first_error_status": None, "done_cycles_read": None,
                           "status_reads": 0, "status_observations": [], "busy_reads": 0,
                           "completion_reads": [], "output_transfer": None, "ack_write": None,
                           "trace_state": "STARTED"}
                self._command = command
            try:
                result = super().write32(offset, value)
            except BaseException:
                if self._command is not None:
                    self._command["write_error_at"] = {"offset": offset, "value": value,
                                                       "before_ticks": before}
                raise
            after = qpc()
            if value == 1:
                self._command["start_write"]["after_ticks"] = after
            elif self._command is not None:
                self._command["ack_write"] = {"before_ticks": before, "after_ticks": after}
                self._command["trace_state"] = "ACK_WRITTEN"
                self._emit(self._command)
                self._command = None
            return result

        def __exit__(self, *args):
            try:
                if self._command is not None:
                    self._command["trace_state"] = "INCOMPLETE_AT_CLOSE"
                    self._emit(self._command)
                    self._command = None
            finally:
                # Trace-file failure must never skip the original XDMA close.
                super().__exit__(*args)

    transport.WindowsXdmaSession = TracedSession
    if own.pilot_max_commands:
        if not 1 <= own.pilot_max_commands <= 3200:
            raise ValueError("pilot command limit outside 1..3200")

        original_backend = hardware_runtime.FinalBoardBackend

        class PilotBackend(original_backend):
            def run(self, descriptor, payload, validate_output=None):
                # At this point the previous command was fully ACKed, its
                # receipt was appended, and hardware is quiescent. No new
                # descriptor or input transfer has started here.
                if len(self.receipts) >= own.pilot_max_commands:
                    raise PilotPrefixComplete("planned diagnostic command prefix complete")
                return super().run(descriptor, payload, validate_output)

        hardware_runtime.FinalBoardBackend = PilotBackend
    sys.argv = [str(frozen), *original_args]
    try:
        module.main()
    except PilotPrefixComplete:
        with trace.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"record": "pilot_stop", "reason": "planned_quiescent_prefix",
                                     "max_commands": own.pilot_max_commands,
                                     "ticks": qpc()}, sort_keys=True) + "\n")
        return


if __name__ == "__main__":
    main()
