#!/usr/bin/env python3
"""Extract the native first-ten overlap witnesses; no EDA or inferred SLR map."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(text):
    start = text.index('Below is a list of the top 10 physical nodes with signal overlaps')
    end = text.index(' Verification failed', start)
    fragment = text[start:end]
    pattern = re.compile(r'(?m)^(\d+)\. \([^)]+\) (NODE_\S+) Hist: (\d+) Tile Name: (\S+) Node: (\S+) Overlapping Nets: (\d+)')
    headings = list(pattern.finditer(fragment))
    records = []
    for i, match in enumerate(headings):
        body = fragment[match.end():headings[i + 1].start() if i + 1 < len(headings) else len(fragment)]
        nets_section = body.split('\nNets:\n', 1)[1]
        nets = [line.strip() for line in nets_section.splitlines()
                if line.startswith('scalellm_vcu118_f05_bd_i/')]
        if not nets or len(nets) > 5:
            raise ValueError('Unexpected native witness signal-list length')
        categories = set()
        for net in nets:
            if '/u_meta_bank/' in net:
                categories.add('metadata')
            elif '/u_shared_compute/u_branch0/' in net:
                categories.add('MLP_shared_branch0')
            elif '/u_shared_compute/u_branch1/' in net:
                categories.add('MLP_shared_branch1')
            elif '/d0_mig_slice/' in net:
                categories.add('DDR0_slice')
            elif '/d1_mig_slice/' in net:
                categories.add('DDR1_slice')
            elif '/d0_smc/' in net:
                categories.add('DDR0_smartconnect')
            elif '/d1_smc/' in net:
                categories.add('DDR1_smartconnect')
            elif '/u_attention/' in net:
                categories.add('Attention')
            else:
                categories.add('other')
        records.append(dict(index=int(match[1]), resource_type=match[2],
                            native_history=int(match[3]), tile=match[4], node=match[5],
                            native_overlapping_nets=int(match[6]), listed_nets=nets,
                            listed_scope_categories=sorted(categories),
                            slr='NOT_INFERRED_FROM_TILE_COORDINATES'))
    if [r['index'] for r in records] != list(range(1, 11)):
        raise ValueError('Native ten-witness sequence is incomplete')
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('log', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    records = extract(args.log.read_text())
    result = dict(source_log=str(args.log.resolve()), source_log_sha256=digest(args.log),
                  extractor_sha256=digest(__file__), witnesses=records,
                  scope='native_first_10_physical_nodes_up_to5_signals_each_not_population_or_driver_ranking',
                  source_stage='actual_failed_route_log_not_physopt_netlist',
                  slr_mapping='not_inferred_cpu_side')
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    table = args.output.with_suffix('.tsv')
    with table.open('x') as f:
        f.write('index\ttile\tnode\tnative_overlapping_nets\tlisted_nets\tscope_categories\n')
        for r in records:
            f.write(f"{r['index']}\t{r['tile']}\t{r['node']}\t{r['native_overlapping_nets']}\t{len(r['listed_nets'])}\t{','.join(r['listed_scope_categories'])}\n")
    print(json.dumps(dict(witnesses=len(records), output=str(args.output),
                         json_sha256=digest(args.output), tsv_sha256=digest(table))))


if __name__ == '__main__':
    main()
