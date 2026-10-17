#!/usr/bin/env python3
"""Preserve native phase, overlap and intermediate timing from immutable prefixes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
ATTEMPT = ROOT / 'project/E005_m002_optimized_implementation/experiment_results/runs/R004/attempts/AT004_default_route'
LOG = ROOT / 'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route/vivado.log'


def identity(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    directory = ATTEMPT / 'native_route_progress_captures'
    directory.mkdir(exist_ok=True)
    producer = directory / 'producer_v3.py'
    script_bytes = Path(__file__).read_bytes()
    if not producer.exists():
        with producer.open('xb') as stream:
            stream.write(script_bytes)
    assert producer.read_bytes() == script_bytes, 'retain a new producer version before editing observer'
    ledger = ATTEMPT / 'native_route_progress.jsonl'
    known = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    seen = {(row['native_line'], row['raw']) for row in known}
    snapshot = LOG.read_bytes()
    phase = None
    phase_line = None
    completed_phase = None
    completed_phase_line = None
    records = []
    for number, line in enumerate(snapshot.decode(errors='replace').splitlines(), 1):
        record = None
        if line.startswith('Phase ') and '| Checksum:' not in line:
            phase, phase_line = line, number
            record = dict(kind='phase')
        if line.startswith('Phase ') and '| Checksum:' in line:
            completed_phase = line.split(' | Checksum:', 1)[0]
            completed_phase_line = number
            record = dict(kind='phase_completion', completed_phase=completed_phase,
                          checksum=line.split('| Checksum:', 1)[1].strip())
        elapsed = re.match(r'^Time \(s\): cpu = ([0-9:.]+) ; elapsed = ([0-9:.]+)', line)
        if elapsed and completed_phase is not None:
            record = dict(kind='native_cumulative_time', completed_phase=completed_phase,
                          completed_phase_native_line=completed_phase_line,
                          cumulative_cpu=elapsed[1], cumulative_elapsed=elapsed[2],
                          scope='native cumulative time after most recent completion; not phase duration')
        overlap = re.search(r'Number of Nodes with overlaps\s*=\s*([0-9,]+)', line)
        if overlap:
            assert phase is not None
            record = dict(kind='overlap_nodes', overlap_nodes=int(overlap[1].replace(',', '')),
                          scope='clock_nets_only_not_whole_route' if 'Global Clock Net Routing' in phase else
                          'intermediate_count_not_terminal_routability')
        if '[Route 35-416] Intermediate Timing Summary' in line:
            values = dict(re.findall(r'\b(WNS|TNS|WHS|THS)\s*=\s*(N/A|[-+]?\d+(?:\.\d+)?)', line))
            assert set(values) == {'WNS', 'TNS', 'WHS', 'THS'}, line
            record = dict(kind='intermediate_timing', native_values=values,
                          values_ns={key: None if value == 'N/A' else float(value)
                                     for key, value in values.items()},
                          scope='native_intermediate_only_not_formal_routed_timing; N/A_is_not_PASS')
        if (line.startswith('ERROR:') or
                ('CRITICAL WARNING:' in line and '[Route ' in line) or
                re.search(r'\[Route 35-(?:2|17|447|448|581)\]|route_design (?:failed|completed)|M002_FAILED_ROUTE', line)):
            record = dict(kind='native_condition',
                          scope='raw_native_message_with_phase; not_independent_terminal_verdict')
        if record is not None and (number, line) not in seen:
            records.append(dict(native_line=number, raw=line, native_phase=phase,
                                native_phase_line=phase_line, **record))
    if not records:
        print(json.dumps(dict(new_records=0, preserved_records=len(known))))
        return
    index = len(list(directory.glob('capture_*_facts.json'))) + 1
    prefix = directory / f'capture_{index:03d}_log_prefix.txt'
    with prefix.open('xb') as stream:
        stream.write(snapshot)
    now = datetime.now(timezone.utc).isoformat()
    bound = identity(prefix)
    records = [dict(observed_utc=now, prefix=bound, **row) for row in records]
    facts = directory / f'capture_{index:03d}_facts.json'
    value = dict(producer_version=3, observed_utc=now, source_log=str(LOG), producer=identity(Path(__file__)),
                 retained_producer=identity(producer), preserved_prefix=bound, records=records,
                 interpretation='Process evidence only. No strategy/gate change; no early terminal verdict; no cross-phase delta.')
    with facts.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    with ledger.open('a') as stream:
        for record in records:
            stream.write(json.dumps(record) + '\n')
    print(json.dumps(dict(new_records=len(records), preserved_records=len(known) + len(records),
                          facts=identity(facts), last_records=[{key: row[key] for key in row if key not in
                          {'prefix', 'observed_utc'}} for row in records[-5:]]), indent=2))


if __name__ == '__main__':
    main()
