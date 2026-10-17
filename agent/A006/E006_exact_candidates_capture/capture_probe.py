#!/usr/bin/env python3
"""Capture the closed native nine-object property probe; never run EDA."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import tkinter
from capture_membership_resources import ATTEMPT, REPORT, identity, table, save


def main():
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    assert not (ATTEMPT/'actual_failed_batch_property_probe_closed_facts.json').exists() and not (ATTEMPT/'property_probe_capture_producer.py').exists(), 'Never overwrite captured native probe evidence or its producer'
    tcl = tkinter.Tcl()
    query = [r for r in table(REPORT / 'query_receipts.tsv') if r['query'] == 'actual_failed_batch_property_diagnostics']
    assert len(query) == 1, 'Native probe not closed'
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), native_query=query[0],
                  native_query_zero=query[0]['native_tcl_code'] == '0',
                  original_failure_scope='Original nine debug objects at R003 property alignment exception',
                  original_exception_identified_property=False, formal_signoff=False)
    files = []
    if not result['native_query_zero']:
        files.append(REPORT / 'error_actual_failed_batch_property_diagnostics.txt')
    else:
        paths = [REPORT / 'failed_batch_actual_property_columns.tsv', REPORT / 'failed_batch_actual_property_vectors.tsv']
        grouped = defaultdict(list)
        for row in table(paths[0]):
            for key in ['object', 'scalar_value']:
                value = tcl.splitlist(row[key]); assert len(value) == 1
                row[key] = value[0]
            assert int(row['expected_objects']) == 9
            assert (row['scalar_value'] == '') == (row['scalar_is_empty'] == '1')
            grouped[row['property']].append(row)
        properties = []
        for row in table(paths[1]):
            prop = row['property']; scalars = grouped.pop(prop)
            vector = tcl.splitlist(row['actual_native_vector_Tcl_list']); assert len(vector) == 1
            vector = tcl.splitlist(vector[0])
            assert len(vector) == int(row['native_vector_list_length'])
            assert len(scalars) == len({s['object'] for s in scalars}) == 9
            assert all(s['native_vector_list_length'] == row['native_vector_list_length'] for s in scalars)
            properties.append(dict(property=prop, expected_objects=9, native_vector_list_length=len(vector),
                                   native_vector_values=list(vector), scalar_objects_and_values=scalars,
                                   scalar_empty_count=sum(s['scalar_is_empty'] == '1' for s in scalars),
                                   vector_cardinality_mismatch=len(vector) != 9))
        assert not grouped and {p['property'] for p in properties} == {'NAME', 'REF_NAME', 'LOC', 'BEL', 'IS_PRIMITIVE'}
        result.update(properties=properties,
                      actual_reproduced_misaligned_property_columns=[p['property'] for p in properties if p['vector_cardinality_mismatch']],
                      interpretation='Actual same-DCP nine-object batch and scalar replay. A reproduced cardinality mismatch identifies the current native column; the original exception itself did not export a property name.')
        files += paths
    producer = ATTEMPT / 'property_probe_capture_producer.py'
    shutil.copy2(Path(__file__), producer)
    result.update(artifacts=[identity(p) for p in files], producer=identity(producer))
    target = ATTEMPT / 'actual_failed_batch_property_probe_closed_facts.json'
    save(target, result)
    print(identity(target))


if __name__ == '__main__':
    main()
