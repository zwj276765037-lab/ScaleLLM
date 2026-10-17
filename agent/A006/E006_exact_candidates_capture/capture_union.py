#!/usr/bin/env python3
"""Audit the newly closed unchanged UNION scope, preserving legacy direction limits."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import sys
import tkinter
from capture_membership_resources import ROOT, ATTEMPT, REPORT, HOTSPOT, identity, table, save

sys.path.insert(0, str(ROOT/'agent/A006/E006_lean_capture'))
from capture_graph_stage import graph, ranked


def main():
    os.sched_setaffinity(0, set(range(8)));os.setpriority(os.PRIO_PROCESS, 0, 5)
    stage='hotspot_connections'
    assert not any((ATTEMPT/name).exists() for name in ['hotspot_connections_closed_stage_facts.json', 'hotspot_connections_closed_stage_summary.json', 'capture_hotspot_connections_producer.py']), 'Never overwrite captured UNION evidence or its producer'
    receipt=[r for r in table(REPORT/'stage_receipts.tsv') if r['stage']==stage]
    assert len(receipt)==1, 'Actual UNION stage has not closed'
    facts=dict(observed_utc=datetime.now(timezone.utc).isoformat(), stage=stage, native_closed_stage_receipt=receipt[0],
               native_stage_zero=receipt[0]['native_tcl_code']=='0', formal_signoff=False,
               endpoint_scope='UNION unchanged legacy leaf IN/OUT only, excludes INOUT/top. Candidate all-direction scope is separate.',
               graph_scope='Original E005 physopt graph, not failed route graph', fixed_window_congestion='UNAVAILABLE')
    files=[REPORT/f'stage_{stage}_closed.txt']
    if not facts['native_stage_zero']:
        tcl=tkinter.Tcl();outer=tcl.splitlist(receipt[0]['failed_queries']);assert len(outer)==1
        files += [REPORT/f'error_{q}.txt' for q in tcl.splitlist(outer[0])]
        facts['execution']='native stage failed; partial output is not complete UNION evidence'
    else:
        selected={r['cell'] for r in table(HOTSPOT)}
        summary=REPORT/'hotspot_union_canonical_net_locations.tsv'
        endpoints=REPORT/'hotspot_union_canonical_net_endpoints.tsv'
        result=graph(summary,endpoints,selected)
        assert not result['totals'].get('repeated_canonical_summary_rows',0)
        edges=result.pop('edges');fields=['metric','source_owner','source_SLR','load_owner','load_SLR','terminal_category']
        native=Counter()
        for row in table(REPORT/'hotspot_union_module_SLR_edges.tsv'):
            key=tuple(row[k] for k in fields);assert key not in native;native[key]=int(row['count'])
        assert native==edges
        result['module_SLR_terminal_edges']=ranked(edges,fields)
        aliases={}; alias_counts=Counter()
        for row in table(REPORT/'hotspot_union_canonical_segments.tsv'):
            assert row['segment'] not in aliases
            aliases[row['segment']]=row['canonical_net'];alias_counts[row['canonical_net']]+=1
        canonical_count=0
        for row in table(summary):
            name=row['canonical_net'];assert aliases.get(name)==name and alias_counts[name]==int(row['segment_count'])
            canonical_count+=1
        assert canonical_count==len(alias_counts)==result['totals']['unique_canonical_nets']
        coverage=dict(line.split('\t',1) for line in (REPORT/'connection_coverage.tsv').read_text().splitlines())
        assert int(coverage['selected_hotspot_union_primitive_cells'])==len(selected)==103313
        assert int(coverage['unique_canonical_complete_nets'])==canonical_count
        assert int(coverage['resolved_segment_closure_entries'])==len(aliases)
        facts.update(parsed_graph=result, connection_coverage=coverage, independent_endpoint_edges_equal_native=True,
                     complete_alias_counts_equal_native=True, canonical_segments=len(aliases), execution='closed_UNION_consistency_verified')
        files += [summary,endpoints,REPORT/'hotspot_union_module_SLR_edges.tsv',REPORT/'hotspot_union_canonical_segments.tsv',
                  REPORT/'connection_coverage.tsv',HOTSPOT]
    producer=ATTEMPT/'capture_hotspot_connections_producer.py';shutil.copy2(Path(__file__),producer)
    facts.update(artifacts=[identity(p) for p in files],producer=identity(producer),
                 imported_graph_validator=identity(ROOT/'agent/A006/E006_lean_capture/capture_graph_stage.py'),
                 graph_validator_table_dependency=identity(ROOT/'agent/A006/E006_lean_capture/capture_stage.py'))
    output=ATTEMPT/'hotspot_connections_closed_stage_facts.json';save(output,facts)
    short={k:v for k,v in facts.items() if k!='parsed_graph'}
    if 'parsed_graph' in facts:short['graph_totals']=facts['parsed_graph']['totals']
    short['full_facts']=identity(output);target=ATTEMPT/'hotspot_connections_closed_stage_summary.json';save(target,short)
    print(dict(facts=identity(output),summary=identity(target)))


if __name__=='__main__':main()
