#!/usr/bin/env python3
"""Preserve the genuine failed-route checkpoint after its own write returns zero."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATTEMPT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R004/attempts/AT004_default_route'
REPORT = ROOT / 'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route'


def identity(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    after = path.stat()
    assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    return dict(path=str(path), bytes=after.st_size, sha256=digest.hexdigest())


def exclusive(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)


def main():
    output = ATTEMPT / 'failed_checkpoint_saved_observation.json'
    assert not output.exists(), 'Do not overwrite this observation'
    receipt = REPORT / 'route_failed_capture_receipts.tsv'
    receipt_bytes = receipt.read_bytes()
    rows = [dict(zip(receipt_bytes.decode().splitlines()[0].split('\t'), line.split('\t', 4)))
            for line in receipt_bytes.decode().splitlines()[1:]]
    row, = [row for row in rows if row['label'] == 'checkpoint']
    dcp = REPORT / 'route_failed.dcp'
    assert row['code'] == '0' and row['result'] == str(dcp)
    assert int(row['ended_epoch']) >= int(row['started_epoch']) > 0
    checkpoint = identity(dcp)
    prefix = ATTEMPT / 'failed_checkpoint_saved_log_prefix.txt'
    exclusive(prefix, (REPORT / 'vivado.log').read_bytes())
    receipt_prefix = ATTEMPT / 'failed_checkpoint_saved_receipt_prefix.tsv'
    exclusive(receipt_prefix, receipt_bytes)
    producer = ATTEMPT / 'failed_checkpoint_saved_observer.py'
    exclusive(producer, Path(__file__).read_bytes())
    original_error = REPORT / 'route_failed_original_error.tcllist'
    value = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                 disposition='diagnostic_failed_route', eligible_as_successful_route_parent=False,
                 write_checkpoint_native_tcl_code=0, checkpoint_receipt=row,
                 checkpoint=checkpoint, original_error=identity(original_error),
                 original_error_text=original_error.read_text(),
                 retained_receipt_prefix=identity(receipt_prefix), retained_log_prefix=identity(prefix),
                 retained_producer=identity(producer), source_receipt=str(receipt),
                 entire_supervisor_terminal_at_observation=(ATTEMPT / 'status.json').exists(),
                 scope='Only this checkpoint write is complete. Receipt/log prefixes are immutable observations while other failed-route diagnostics may continue. Not routed signoff or complete POST.')
    with output.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(observation=identity(output), checkpoint=checkpoint,
                         supervisor_terminal_at_observation=value['entire_supervisor_terminal_at_observation']), indent=2))


if __name__ == '__main__':
    main()
