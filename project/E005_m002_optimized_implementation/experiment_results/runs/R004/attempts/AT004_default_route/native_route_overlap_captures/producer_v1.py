#!/usr/bin/env python3
"""Append newly observed native route counts, preserving exact phase and log prefix."""
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
ATTEMPT = ROOT/'project/E005_m002_optimized_implementation/experiment_results/runs/R004/attempts/AT004_default_route'
REPORT = ROOT/'project/hardware/vivado/reports/m002_E005_R004_AT004_default_route'


def identity(path):
    return dict(path=str(path),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    ledger = ATTEMPT/'native_route_overlap_counts.jsonl'
    known = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    seen = {(row['native_line'],row['raw']) for row in known}
    raw = (REPORT/'vivado.log').read_bytes()
    phase = None;phase_line = None;new = []
    for number,line in enumerate(raw.decode(errors='replace').splitlines(),1):
        if line.startswith('Phase ') and '| Checksum:' not in line:
            phase = line;phase_line = number
        match = re.search(r'Number of Nodes with overlaps\s*=\s*([0-9,]+)',line)
        if match and (number,line) not in seen:
            assert phase is not None
            new.append(dict(native_line=number,raw=line,overlap_nodes=int(match[1].replace(',','')),
                native_phase=phase,native_phase_line=phase_line,
                scope='clock_nets_only_not_whole_route' if 'Global Clock Net Routing' in phase else
                      'native_phase_progress_not_terminal_routability_verdict'))
    if not new:
        print(json.dumps(dict(new_counts=0,total_preserved_counts=len(known))))
        return
    out = ATTEMPT/'native_route_overlap_captures';out.mkdir(exist_ok=True)
    index = len(list(out.glob('capture_*_facts.json')))+1
    prefix = out/f'capture_{index:03d}_log_prefix.txt'
    with prefix.open('xb') as stream:stream.write(raw)
    now = datetime.now(timezone.utc).isoformat();bound = identity(prefix)
    records = [dict(observed_utc=now,prefix=bound,**row) for row in new]
    facts = out/f'capture_{index:03d}_facts.json'
    value = dict(observed_utc=now,source_log=str(REPORT/'vivado.log'),source_scope='immutable observed prefix; original continues',
        producer=identity(Path(__file__)),preserved_prefix=bound,new_count_records=records,
        instruction='Preserve exact native phase; no new gate, early failure or cross-phase count comparison')
    with facts.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    with ledger.open('a') as stream:
        for row in records:stream.write(json.dumps(row)+'\n')
    print(json.dumps(dict(new_counts=len(new),total_preserved_counts=len(known)+len(new),facts=identity(facts),
        records=[{key:row[key] for key in ('native_line','native_phase','overlap_nodes','scope')} for row in records]),indent=2))


if __name__ == '__main__':main()
