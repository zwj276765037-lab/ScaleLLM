#!/usr/bin/env python3
"""Focused actual-collector logging lifecycle checks; no new native design work."""
import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = ROOT/'agent/A006/directed_candidate_top_port_index/E008_entry'
sys.path.insert(0, str(HERE))
import directed_evidence as d
import evidence_adapter as adapter


def procedures(directory, report):
    t = tkinter.Tcl()
    for key, value in [('SLR2_CANDIDATE_ROOT','CPU_TEST_LITERAL_ROOT'),('SLR2_CANDIDATE_ID','C01'),('HAP_REPORT_DIR',str(report))]:
        t.setvar('env('+key+')', value)
    t.call('source', str(ROOT/'project/hardware/vivado/scripts/m002_diagnostic_common.tcl'))
    t.call('source', str(directory/'candidate_hooks.tcl'))
    return {name.removeprefix('::'):t.call('info','body',name) for name in t.splitlist(t.call('info','procs','slr2::*'))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--r006-source', type=Path, required=True)
    args = parser.parse_args()
    assert Path(args.tag).name == args.tag
    out = HERE/'CPU_checks'/args.tag
    out.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, set(range(8)))
    os.setpriority(os.PRIO_PROCESS, 0, 5)
    before, after = procedures(BASE, out), procedures(HERE, out)
    added = {'slr2::directed_alias_trace_open','slr2::directed_alias_trace','slr2::directed_alias_trace_close'}
    assert set(after) == set(before) | added
    assert all(after[name] == body for name, body in before.items() if name not in {'slr2::directed_alias','slr2::cut'})
    assert after['slr2::directed_alias'] == before['slr2::directed_alias'].replace('directed_trace ALIAS_', 'directed_alias_trace ALIAS_')
    # There are exactly six redirected event sites; all native statements and
    # cache branches in the actual alias resolver remain identical.
    assert after['slr2::directed_alias'].count('directed_alias_trace ALIAS_') == 6
    body=after['slr2::cut'];start=body.index('    directed_alias_trace_open $point');end=body.index('    directed_trace LOCAL_PIN_NET_MAPPING END $point')
    assert body[:start]+'    directed_local_scope $point\n'+body[end:]==before['slr2::cut']
    fixture = ROOT/'agent/A006/directed_candidate_top_port_index/check_native_index_phase_mock.tcl'
    prefix = fixture.read_text().split('foreach name {index_universe ingress',1)[0]
    assert prefix != fixture.read_text()
    script = prefix + r'''
rename get_property original_mock_get_property
proc get_property args {
    set a $args
    if {[lindex $a 0] eq "-quiet"} {set a [lrange $a 1 end]}
    lassign $a property objects
    if {!$::injected && $property eq "NAME" && $objects eq "n1" && $::mode in {native_error log_error native_and_log_error}} {
        set ::injected 1
        if {$::mode in {log_error native_and_log_error}} {close $::slr2::aliasTraceChannel}
        if {$::mode in {native_error native_and_log_error}} {return -code error -errorcode {CPU_EXPECTED_ALIAS_NATIVE_FAILURE} "ORIGINAL_NATIVE_FAILURE\nsecond line"}
    }
    return [uplevel 1 [linsert $args 0 original_mock_get_property]]
}
rename fconfigure original_mock_fconfigure
proc fconfigure args {
    if {$::mode eq "configure_error" && [lindex $args 0] eq $::slr2::aliasTraceChannel} {return -code error -errorcode {CPU_EXPECTED_ALIAS_CONFIG_FAILURE} ORIGINAL_CONFIG_FAILURE}
    return [uplevel 1 [linsert $args 0 original_mock_fconfigure]]
}
foreach mode {normal native_error log_error native_and_log_error open_existing configure_error} {
    set ::mode $mode;set ::injected 0
    setup index_universe
    set ::m002_report_dir [file join $outputDir $mode]
    file mkdir $::m002_report_dir
    foreach tag {RAW S P} {
        set h [open [file join $::m002_report_dir candidate_${tag}_${point}.tsv] {WRONLY CREAT EXCL}]
        puts $h "NAME\tREF_NAME"
        dict for {member ref} [set ::slr2::$tag] {puts $h "$member\t$ref"}
        close $h
    }
    if {$mode eq "open_existing"} {
        set h [open [file join $::m002_report_dir candidate_alias_api_trace_${point}.tcllist] {WRONLY CREAT EXCL}];puts $h PREEXISTING_TRACE;close $h
    }
    set code [catch {slr2::cut $point} result options]
    if {$mode eq "normal"} {check {!$code} "Normal mapping failed: $result"} else {check {$code} "Failure case unexpectedly succeeded"}
    if {$mode in {native_error native_and_log_error}} {
        check {$result eq "ORIGINAL_NATIVE_FAILURE\nsecond line"} "Original native result replaced"
        check {[dict get $options -errorcode] eq "CPU_EXPECTED_ALIAS_NATIVE_FAILURE"} "Original native error options replaced"
    }
    if {$mode eq "configure_error"} {check {[dict get $options -errorcode] eq "CPU_EXPECTED_ALIAS_CONFIG_FAILURE"} "Original configuration error replaced"}
    check {$::slr2::aliasTraceChannel eq ""} "Alias trace channel ownership not released"
    if {$mode ne "normal"} {check {![file exists [file join $::m002_report_dir candidate_cut_${point}_closed.txt]]} "Failure published candidate cut"}
    set h [open [file join $::m002_report_dir actual_result.tcllist] {WRONLY CREAT EXCL}]
    puts $h [list mode $mode code $code result $result options $options sidecar_channel $::slr2::aliasTraceChannel]
    close $h
    puts "LOGGING_CASE\t$mode\tPASS"
}
'''
    lifecycle = script[len(prefix):]
    test = out/'actual_collector_logging_lifecycle.tcl'
    test.write_text(script)
    run = subprocess.run(['tclsh',str(test),str(HERE),str(out/'collector'),'pre_place'],capture_output=True,text=True)
    (out/'stdout.txt').write_text(run.stdout)
    (out/'stderr.txt').write_text(run.stderr)
    cases = [line.split('\t') for line in run.stdout.splitlines() if line.startswith('LOGGING_CASE\t')]
    assert run.returncode == 0 and len(cases) == 6 and all(row[2]=='PASS' for row in cases), (cases,run.stderr)
    assert not any('operation '+name in run.stdout for name in ['ALIAS_NET_NAME','ALIAS_NATIVE_SEGMENTS','ALIAS_SEGMENT_NAME'])
    for token in ['CLASS_SCHEMA','LOCAL_PIN_NET_MAPPING','TOP_PORT_UNIVERSE','TOP_GROUP_FORWARD_PORTS','NONLOAD_LEAF','TOP_PORT_INDEX_JOIN']:
        assert 'operation '+token+' event BEGIN' in run.stdout and 'operation '+token+' event END' in run.stdout
    report = out/'collector/normal'
    value = adapter.cut_summary('pre_place',report)
    assert value['directed_boundary_complete'] and value['top_port_acquisition']['exhaustive_native_reciprocal_qualification']
    events = []
    for line in (report/'candidate_alias_api_trace_pre_place.tcllist').read_text().splitlines():
        fields = d.split(line)
        assert fields[0] == 'DIRECTED_API'
        assert len(fields)%2==1 and len(set(fields[1::2]))==len(fields[1::2])
        events.append(dict(zip(fields[1::2],fields[2::2])))
    marker = d.marker(report/'candidate_alias_api_trace_pre_place_closed.txt')
    assert marker['normal_final_flush']=='1' and marker['mapping_tcl_code']=='0' and int(marker['recorded_events'])==len(events)>0
    assert [int(row['sequence']) for row in events] == list(range(1,len(events)+1))
    assert all(row['point']=='pre_place' and int(row['epoch_ms'])>0 for row in events)
    assert [row['event'] for row in events].count('BEGIN') == [row['event'] for row in events].count('END')
    native_marker = d.marker(out/'collector/native_error/candidate_alias_api_trace_pre_place_closed.txt')
    assert native_marker['mapping_tcl_code']=='1' and native_marker['normal_final_flush']=='1'
    assert (out/'collector/log_error/candidate_alias_api_trace_pre_place_close_error.tcllist').is_file()
    assert (out/'collector/native_and_log_error/candidate_alias_api_trace_pre_place_close_error.tcllist').is_file()
    assert (out/'collector/open_existing/candidate_alias_api_trace_pre_place.tcllist').read_text()=='PREEXISTING_TRACE\n'
    baseline = BASE/'CPU_checks/CT005_index_phase/pre_place/index_universe'
    same = []
    for tag in ['RAW','S','P','pins','local_owners','segments','local_pin_net','nets','endpoints','boundary_timing_scope']:
        name = f'candidate_{tag}_pre_place.tsv'
        assert (report/name).read_bytes() == (baseline/name).read_bytes(), name
        same.append(name)
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(),filename=str(path))
    retry = args.r006_source.resolve()
    assert (retry/'directed_exporter.tcl').read_bytes() == (HERE/'directed_exporter.tcl').read_bytes()
    retry_fixture = ROOT/'agent/A006/directed_candidate_top_port_index/check_native_index_mock.tcl'
    retry_prefix = retry_fixture.read_text().split('foreach name {index_universe ingress',1)[0]
    retry_test = out/'actual_R006_logging_lifecycle.tcl'
    retry_test.write_text(retry_prefix+'\nset point test\n'+lifecycle)
    retry_run = subprocess.run(['tclsh',str(retry_test),str(retry),str(out/'R006_collector')],capture_output=True,text=True)
    (out/'R006_stdout.txt').write_text(retry_run.stdout)
    (out/'R006_stderr.txt').write_text(retry_run.stderr)
    retry_cases = [line.split('\t') for line in retry_run.stdout.splitlines() if line.startswith('LOGGING_CASE\t')]
    assert retry_run.returncode==0 and len(retry_cases)==6 and all(row[2]=='PASS' for row in retry_cases), (retry_cases,retry_run.stderr)
    retry_validate = subprocess.run(['/usr/bin/python3',str(retry/'directed_evidence.py'),'cut','test',str(out/'R006_collector/normal')],capture_output=True,text=True)
    (out/'R006_validator_stdout.txt').write_text(retry_validate.stdout)
    (out/'R006_validator_stderr.txt').write_text(retry_validate.stderr)
    assert retry_validate.returncode==0, retry_validate.stderr
    retry_baseline = ROOT/'agent/A006/directed_candidate_top_port_index/CPU_checks/CT004_full_combination/collector/index_universe'
    for tag in ['RAW','S','P','pins','local_owners','segments','local_pin_net','nets','endpoints','boundary_timing_scope']:
        name=f'candidate_{tag}_test.tsv'
        assert (out/'R006_collector/normal'/name).read_bytes()==(retry_baseline/name).read_bytes(), name
    result = dict(recorded_utc=datetime.now(timezone.utc).isoformat(),EDA_executed=False,
                  checks=dict(all_unaffected_procedures_identical=True,six_trace_dispatch_only_alias_change=True,
                              six_actual_collector_lifecycle_cases=True,all_events_buffered_and_final_flush=True,
                              original_native_error_result_and_options_preserved=True,secondary_log_failure_not_masking_native=True,
                              log_open_and_configure_failure_explicit_no_false_cut=True,top_native_BEGIN_END_and_stage_progress_retained=True,
                              complete_index_and_directed_validator_actual_combination=True,ten_native_semantic_ledgers_equal=True,
                              same_buffered_collector_actual_R006_normal_and_six_lifecycle_cases=True),
                  actual_cases=[row[1] for row in cases], normal_sidecar_events=len(events), identical_semantic_ledgers=same,
                  source_identities=[d.identity(path) for path in sorted(HERE.glob('*.py'))+sorted(HERE.glob('*.tcl'))],
                  reused_fixture=d.identity(fixture), derived_lifecycle_fixture=d.identity(test),
                  R006_fixture=d.identity(retry_fixture), R006_derived_fixture=d.identity(retry_test),
                  R006_shared_collector=d.identity(retry/'directed_exporter.tcl'),
                  limitations=['Finite native graph mocks; no new native design, physical phase or speed claim',
                               'Queries/cache/qualification/physical flow reused unchanged; affected logging lifecycle checked only'])
    d.save(out/'results.json',result)
    print(json.dumps(dict(path=str(out/'results.json'),checks=result['checks'])))


if __name__=='__main__':
    main()
