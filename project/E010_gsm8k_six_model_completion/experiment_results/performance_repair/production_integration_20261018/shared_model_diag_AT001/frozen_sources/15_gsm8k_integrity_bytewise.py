"""Full-content guard candidate; does not replace any running/frozen module.

Use ``make_integrity_class(the_already_imported_legacy_module)`` explicitly.
Loading, checkpoint SHA, native QDQ reconstruction and native cache parity remain
the legacy implementation's responsibility. Only repeated static-content checks
change: every logical tensor byte is compared with SHA-bound immutable bytes.
"""
from __future__ import annotations

import copy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import MappingProxyType

METHOD_ID = "immutable_cpu_chunks_memcmp_full_content_v1"
DEFAULT_CHUNK_BYTES = 16 * 1024 * 1024
MINIMUM_HOST_RESERVE_BYTES = 80 * (1 << 30)

_libc = ctypes.CDLL(None)
_memcmp = _libc.memcmp
_memcmp.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t)
_memcmp.restype = ctypes.c_int
_bytes_pointer = ctypes.pythonapi.PyBytes_AsString
_bytes_pointer.argtypes = (ctypes.py_object,)
_bytes_pointer.restype = ctypes.c_void_p


class BytewiseIntegrityError(RuntimeError):
    pass


def _storage(tensor):
    return {"object_id": id(tensor), "data_ptr": tensor.data_ptr(),
            "storage_base_ptr": tensor.untyped_storage().data_ptr(),
            "storage_offset": tensor.storage_offset(), "stride": list(tensor.stride()),
            "device": str(tensor.device), "shape": list(tensor.shape), "dtype": str(tensor.dtype)}


def _validate_tensor(tensor):
    import torch
    if (tensor.layout != torch.strided or tensor.is_quantized or
            tensor.device.type not in {"cpu", "cuda"} or
            not tensor.is_contiguous() or tensor.is_conj() or tensor.is_neg()):
        raise BytewiseIntegrityError("candidate supports contiguous, native-order, nonquantized CPU/CUDA tensors without conjugate/negative view bits")
    # reshape handles scalar tensors; viewing bytes preserves NaN payloads/-0.
    return tensor.detach().reshape(-1).view(torch.uint8)


def read_host_available_bytes():
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise BytewiseIntegrityError("host MemAvailable is unavailable")


def audit_capture_memory(tensors, chunk_bytes):
    """Budget the actual contiguous storage regions before allocating baseline."""
    if not isinstance(chunk_bytes, int) or chunk_bytes < 1:
        raise ValueError("chunk_bytes must be a positive integer")
    regions, logical = {}, 0
    for tensor in tensors.values():
        raw = _validate_tensor(tensor)
        size = raw.numel()
        logical += size
        regions[(str(tensor.device), tensor.data_ptr(), size)] = size
    unique = sum(regions.values())
    available = read_host_available_bytes()
    projected = available - unique - chunk_bytes
    return {"schema": "scalellm_immutable_capture_memory_guard_v1",
            "measurement_source": "proc_meminfo_MemAvailable", "mem_available_before_capture_bytes": available,
            "logical_static_bytes": logical, "unique_immutable_baseline_bytes": unique,
            "staging_buffer_bytes": chunk_bytes, "projected_available_after_capture_bytes": projected,
            "minimum_host_reserve_bytes": MINIMUM_HOST_RESERVE_BYTES,
            "passed": projected >= MINIMUM_HOST_RESERVE_BYTES, "checked_epoch_seconds": time.time()}


class ChunkTransfer:
    """One bounded reusable buffer, pinned only when CUDA is actually requested."""
    def __init__(self, chunk_bytes, *, cuda):
        import torch
        if not isinstance(chunk_bytes, int) or chunk_bytes < 1:
            raise ValueError("chunk_bytes must be a positive integer")
        self.chunk_bytes = chunk_bytes
        self.buffer = torch.empty(chunk_bytes, dtype=torch.uint8, device="cpu", pin_memory=cuda)
        self.cuda = cuda

    def begin(self, tensors):
        # Exactly one device barrier per device/phase. Other-stream producers
        # queued before the check must finish before observing any tensor.
        import torch
        devices = sorted({str(t.device) for t in tensors if t.device.type == "cuda"})
        for device in devices:
            torch.cuda.synchronize(torch.device(device))

    def copy(self, raw, offset, size):
        self.buffer[:size].copy_(raw.narrow(0, offset, size), non_blocking=self.cuda)

    def synchronize(self, raw):
        if raw.device.type == "cuda":
            import torch
            # Completion is mandatory before memcmp AND before buffer reuse.
            torch.cuda.current_stream(raw.device).synchronize()


class ImmutableTensorSnapshot:
    """Private immutable chunk bytes; no model alias or full GPU weight replica.

    Unsupported layouts fail closed. Storage aliases may share immutable chunk
    tuples, but every logical name is independently inventoried and compared.
    ``compared_bytes`` counts bytes submitted to memcmp. Successful equality
    covers every byte; libc may short circuit within a mismatching chunk.
    """
    def __init__(self, tensors, manifest, *, roles, expected_storage=None,
                 chunk_bytes=DEFAULT_CHUNK_BYTES, storage_identity=_storage,
                 transfer_factory=ChunkTransfer):
        if set(tensors) != set(manifest) or set(roles) != set(manifest):
            raise BytewiseIntegrityError("capture inventory differs from verified manifest")
        self.chunk_bytes = chunk_bytes
        self._storage_identity = storage_identity
        self.__manifest = copy.deepcopy(manifest)
        self.__roles = dict(roles)
        self.__storage = copy.deepcopy(expected_storage or {n: storage_identity(t) for n, t in tensors.items()})
        if set(self.__storage) != set(manifest):
            raise BytewiseIntegrityError("capture storage inventory differs")
        cuda = any(t.device.type == "cuda" for t in tensors.values())
        self.transfer = transfer_factory(chunk_bytes, cuda=cuda)
        self.transfer.begin(tensors.values())
        captured, dedup, per_tensor = {}, {}, {}
        for name, tensor in sorted(tensors.items()):
            raw = _validate_tensor(tensor)
            desc = self.__manifest[name]
            size = raw.numel()
            if (storage_identity(tensor) != self.__storage[name] or
                    list(tensor.shape) != desc["shape"] or str(tensor.dtype) != desc["dtype"] or
                    roles[name] != desc["role"]):
                raise BytewiseIntegrityError(f"capture metadata/storage differs: {name}")
            alias = (str(tensor.device), tensor.data_ptr(), size)
            if alias in dedup:
                chunks, digest = dedup[alias]
            else:
                chunks_list, sha = [], hashlib.sha256()
                for offset in range(0, size, chunk_bytes):
                    length = min(chunk_bytes, size - offset)
                    self.transfer.copy(raw, offset, length)
                    self.transfer.synchronize(raw)
                    # Read the completed staging buffer into a new immutable
                    # bytes object; hash THESE bytes, not an earlier live view.
                    chunk = ctypes.string_at(self.transfer.buffer.data_ptr(), length)
                    sha.update(chunk)
                    chunks_list.append(chunk)
                chunks, digest = tuple(chunks_list), sha.hexdigest()
                dedup[alias] = (chunks, digest)
            if digest != desc["sha256"]:
                raise BytewiseIntegrityError(f"immutable captured bytes SHA differs from verified baseline: {name}")
            if storage_identity(tensor) != self.__storage[name]:
                raise BytewiseIntegrityError(f"storage changed during capture: {name}")
            captured[name] = chunks
            per_tensor[name] = {"bytes": size, "sha256": digest, "sha_matches_verified_baseline": True}
        self.__chunks = MappingProxyType(captured)
        self.expected_bytes = sum(row["bytes"] for row in per_tensor.values())
        self.unique_baseline_bytes = sum(sum(map(len, chunks)) for chunks, _ in dedup.values())
        self.capture_evidence = {"method_id": METHOD_ID, "byte_order": sys.byteorder,
            "chunk_bytes": chunk_bytes, "logical_baseline_bytes": self.expected_bytes,
            "unique_immutable_baseline_bytes": self.unique_baseline_bytes,
            "staging_buffer_bytes": chunk_bytes, "staging_buffer_pinned": bool(self.transfer.buffer.is_pinned()),
            "gpu_weight_replica_bytes": 0, "capture_sha_source": "actual_saved_immutable_chunk_bytes_in_logical_order",
            "per_tensor": per_tensor}

    def baseline_manifest(self):
        return copy.deepcopy(self.__manifest)

    def compare(self, tensors, *, roles):
        observed, errors, details = {}, [], {}
        inventory_ok = set(tensors) == set(self.__manifest) and set(roles) == set(self.__manifest)
        if set(roles) != set(tensors):
            errors.append("role_inventory_mismatch")
        self.transfer.begin(tensors.values())
        for name, tensor in sorted(tensors.items()):
            if name not in self.__manifest:
                errors.append(name + ":unexpected_name")
                observed[name] = {"sha256": "unverified_unexpected_tensor", "shape": list(tensor.shape),
                                  "dtype": str(tensor.dtype), "role": roles.get(name, "unknown")}
                continue
            baseline = self.__manifest[name]
            record = {"expected_bytes": sum(map(len, self.__chunks[name])),
                      "compared_bytes": 0, "equal_bytes": 0, "all_chunks_equal": True}
            details[name] = record
            metadata_ok = (list(tensor.shape) == baseline["shape"] and str(tensor.dtype) == baseline["dtype"] and
                           roles.get(name) == baseline["role"] and self._storage_identity(tensor) == self.__storage[name])
            if not metadata_ok:
                errors.append(name + ":metadata_or_storage")
                record["all_chunks_equal"] = False
            else:
                raw = _validate_tensor(tensor)
                offset = 0
                for chunk in self.__chunks[name]:
                    size = len(chunk)
                    self.transfer.copy(raw, offset, size)
                    self.transfer.synchronize(raw)
                    equal = _memcmp(self.transfer.buffer.data_ptr(), _bytes_pointer(chunk), size) == 0
                    record["compared_bytes"] += size
                    record["equal_bytes"] += size if equal else 0
                    record["all_chunks_equal"] &= equal
                    offset += size
                if self._storage_identity(tensor) != self.__storage[name]:
                    errors.append(name + ":storage_changed_during_comparison")
                    record["all_chunks_equal"] = False
            exact = metadata_ok and record["all_chunks_equal"] and record["compared_bytes"] == record["expected_bytes"]
            record["complete"] = record["compared_bytes"] == record["expected_bytes"]
            record["exact"] = bool(exact)
            if exact:
                observed[name] = copy.deepcopy(baseline)
            else:
                observed[name] = {"sha256": "unverified_bytewise_or_metadata_mismatch", "shape": list(tensor.shape),
                                  "dtype": str(tensor.dtype), "role": roles.get(name, "unknown")}
        missing = sorted(set(self.__manifest) - set(tensors))
        errors.extend(name + ":missing_name" for name in missing)
        exact = inventory_ok and not errors and observed == self.__manifest
        evidence = {"method_id": METHOD_ID, "direct_sha256_this_phase": False,
            "hash_derivation": "verified_immutable_baseline_sha_reused_only_after_full_exact_bytewise_inventory_and_storage_match",
            "inventory_exact": inventory_ok, "expected_bytes": self.expected_bytes,
            "compared_bytes": sum(r["compared_bytes"] for r in details.values()),
            "equal_bytes": sum(r["equal_bytes"] for r in details.values()),
            "memcmp_byte_count_semantics": "submitted_chunk_lengths; equal chunks cover every byte; mismatch may short_circuit",
            "full_coverage_exact": bool(exact), "per_tensor": details,
            "missing_names": missing, "unexpected_names": sorted(set(tensors) - set(self.__manifest))}
        return observed, sorted(errors), evidence


def make_integrity_class(legacy):
    """Return a subclass without replacing/importing gsm8k_weight_integrity.

    The caller explicitly supplies its original module. No sys.modules monkey
    patch or worker import side effect is used. New runs must freeze both files.
    """
    class BytewiseStaticContentIntegrity(legacy.StaticContentIntegrity):
        def __init__(self, *args, chunk_bytes=DEFAULT_CHUNK_BYTES, **kwargs):
            self._snapshot = None
            self._runtime_evidence = None
            self._chunk_bytes = chunk_bytes
            super().__init__(*args, **kwargs)
            self.data["runtime_comparison_implementation"] = {
                "method_id": METHOD_ID, "candidate_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "legacy_source_sha256": self.data["source_sha256"],
                "loading_sha_policy": "unchanged_legacy_direct_sha_and_native_QDQ_reconstruction",
                "native_cache_policy": "unchanged_native_cache_call_parity_v2",
                "unsupported_tensor_policy": "fail_closed_noncontiguous_non_strided_quantized_conjugate_negative_or_non_CPU_CUDA"}
            self._save()

        def _runtime_entries(self):
            tensors, roles = {}, {}
            for name, (tensor, default_role) in sorted(legacy.model_tensors(self.model).items()):
                owner, _, _ = name.rpartition(".")
                tensors[name] = tensor
                roles[name] = "qdq_buffer" if owner in self.qdq_modules else self.roles.get(name, default_role)
            for name, tensor in self._cache_entries().items():
                tensors[name], roles[name] = tensor, "external_cache"
            return tensors, roles

        def _attached(self, model):
            # This includes every original full-shape native QDQ reconstruction,
            # checkpoint source SHA, static cache rebuild and direct SHA phase.
            attached_started = time.perf_counter()
            super()._attached(model)
            attached_seconds = time.perf_counter() - attached_started
            tensors, roles = self._runtime_entries()
            guard = audit_capture_memory(tensors, self._chunk_bytes)
            self.data["immutable_capture_resource_guard"] = guard
            self._save()
            if not guard["passed"]:
                raise legacy.IntegrityError("immutable baseline capture would violate host reserve 80GiB")
            capture_started = time.perf_counter()
            self._snapshot = ImmutableTensorSnapshot(tensors, self.data["baseline_manifest"], roles=roles,
                expected_storage=self.runtime_storage, chunk_bytes=self._chunk_bytes, storage_identity=legacy.storage_identity)
            capture_seconds = time.perf_counter() - capture_started
            self.data["immutable_runtime_baseline"] = self._snapshot.capture_evidence
            self.data["integrity_timing"] = {"legacy_attached_validation_seconds": attached_seconds,
                "immutable_capture_seconds": capture_seconds,
                "scope": "attached validation and immutable capture measured separately; neither is repeated per sample"}
            self._save()

        def _phase(self, label, observed, trusted, *, identity_errors=None, loading=False):
            # Same exactness/terminal behavior as the legacy phase; add explicit
            # method and byte-coverage evidence BEFORE writing the phase record.
            exact = observed == trusted and not identity_errors
            row = {"label": label, "complete": True, "exact": bool(exact),
                   "checked_names": sorted(observed), "observed_root_sha256": legacy.canonical_hash(observed)}
            if loading:
                row["trusted_root_sha256"] = legacy.canonical_hash(trusted)
            if self._runtime_evidence is not None:
                row["content_comparison"] = self._runtime_evidence
                if exact:
                    row["content_comparison"]["derived_root_sha256"] = legacy.canonical_hash(trusted)
            if not exact:
                row["missing_names"] = sorted(set(trusted) - set(observed))
                row["unexpected_names"] = sorted(set(observed) - set(trusted))
                row["changed_names"] = sorted(n for n in set(observed) & set(trusted) if observed[n] != trusted[n])
                row["identity_errors"] = identity_errors or []
            self.checks.append(row)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._save()
            if not exact:
                error = legacy.IntegrityError(f"static-content integrity failed at {label}: {row}")
                self.fail(error)
                raise error

        def check(self, label):
            if self._snapshot is None or self.data["state"] != "running":
                raise legacy.IntegrityError("immutable static content baseline unavailable or already terminal")
            try:
                tensors, roles = self._runtime_entries()
                trusted = self._snapshot.baseline_manifest()
                if self.data["baseline_manifest"] != trusted or self.data["baseline_root_sha256"] != legacy.canonical_hash(trusted):
                    raise legacy.IntegrityError("verified baseline metadata changed after immutable capture")
                comparison_started = time.perf_counter()
                observed, errors, evidence = self._snapshot.compare(tensors, roles=roles)
                evidence["comparison_elapsed_seconds"] = time.perf_counter() - comparison_started
                if not evidence["full_coverage_exact"]:
                    errors = errors + ["incomplete_or_unequal_bytewise_coverage"]
                self._runtime_evidence = evidence
                self._phase(label, observed, trusted, identity_errors=errors)
            except BaseException as error:
                if self.data["state"] == "running":
                    self.fail(error)
                raise
            finally:
                self._runtime_evidence = None

    BytewiseStaticContentIntegrity.__name__ = "BytewiseStaticContentIntegrity"
    return BytewiseStaticContentIntegrity
