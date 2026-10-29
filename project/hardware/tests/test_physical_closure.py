# SPDX-License-Identifier: Apache-2.0
"""CPU checks of the real repair Tcl/launcher using simulated native commands."""
import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
SCRIPT=ROOT/'project/hardware/vivado/scripts/release_hold_repair.tcl'
spec=importlib.util.spec_from_file_location('release_builder',ROOT/'deploy/final/build_hardware.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class RepairFlowTests(unittest.TestCase):
    def run_flow(self,method='hold_fix',after_fully=1,physical_error=0,route_error=0,row=None,bad_hash=False,initial_fully=1,bad_part=False):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);source=out/'input.dcp';source.write_text('CPU fixture, not a native DCP')
            digest='0'*64 if bad_hash else hashlib.sha256(source.read_bytes()).hexdigest()
            values=row or '0.017 0 0 100 0.002 0 0 100 0.000 0 0 100'
            setup=f'''set out {{{out}}}
set ::events {{}}
set ::changed 0
set ::rerouted 0
set ::after_fully {after_fully}
set ::initial_fully {initial_fully}
set ::physical_error {physical_error}
set ::route_error {route_error}
set ::bad_part {int(bad_part)}
set ::row {{{values}}}
set ::env(HAP_STAGE) hold
set ::env(HAP_JOBS) 4
set ::env(HAP_REPORT_DIR) $out
set ::env(HAP_SOURCE_DCP) {{{source}}}
set ::env(HAP_SOURCE_DCP_SHA256) {digest}
set ::env(HAP_HOLD_METHOD) {{{method}}}
'''
            mocks=r'''
proc note {value} {lappend ::events $value}
proc set_param {args} {}
proc version {args} {return 2025.2}
proc open_checkpoint {args} {note open}
proc current_design {} {return scalellm_final_decode16_bd_wrapper}
proc get_pins {args} {return [lindex $args end]}
proc get_clocks {args} {return [lindex $args end]}
proc get_property {property object} {
    if {$property eq {PART}} {if {$::bad_part} {return wrong_part};return xcvu9p-flga2104-2L-e}
    if {$property eq {NAME}} {return $object}
    if {$property eq {PERIOD}} {if {[string match *core_clk $object]} {return 12.5};return 5.0}
    error "unexpected property $property"
}
proc report_route_status {args} {
    if {[lindex $args 0] eq {-boolean_check}} {
        if {[lindex $args 1] eq {ERRORS_IN_ROUTES}} {return 0}
        if {$::rerouted} {return 1}
        if {$::changed} {return $::after_fully}
        return $::initial_fully
    }
    note report_route_status
}
proc phys_opt_design {args} {
    note "phys_opt_design $args"
    set ::changed 1
    if {$::physical_error} {error {simulated physical failure}}
}
proc write_checkpoint {path} {
    note "checkpoint [file tail $path]"
    set f [open $path w];puts $f preserved;close $f
}
proc route_design {args} {
    note "route_design $args"
    if {$::route_error} {error {simulated route failure}}
    set ::rerouted 1
}
proc report_utilization {args} {note report_utilization}
proc report_clocks {args} {note report_clocks}
proc check_timing {args} {note check_timing}
proc report_drc {args} {note report_drc}
proc get_drc_violations {args} {return {}}
proc report_timing_summary {args} {
    note report_timing_summary
    set at [lsearch -exact $args -file]
    set f [open [lindex $args [expr {$at+1}]] w]
    puts $f {WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints}
    puts $f -----;puts $f $::row;close $f
}
proc close_design {} {note close}
'''
            script=setup+mocks+f'\nset rc [catch {{source {{{SCRIPT}}}}} message]\n'+'''puts "RESULT $rc $message"
puts "EVENTS [join $::events |]"
if {$rc} {exit 1}
'''
            result=subprocess.run(['tclsh'],input=script,text=True,capture_output=True)
            events=next(line[7:].split('|') for line in result.stdout.splitlines() if line.startswith('EVENTS '))
            return result,events,{p.name for p in out.iterdir()}

    def test_exact_methods_save_before_reports(self):
        for method in ('sll_reg_hold_fix','hold_fix'):
            with self.subTest(method=method):
                r,events,files=self.run_flow(method=method)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)
                i=events.index('phys_opt_design -'+method)
                self.assertEqual(events[i+1],'checkpoint post_physopt.dcp')
                self.assertNotIn('route_design -preserve',events)
                self.assertIn('routed.dcp',files)

    def test_reroute_is_conditional_and_preserved_first(self):
        r,events,_=self.run_flow(after_fully=0)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        i=events.index('route_design -preserve');self.assertEqual(events[i+1],'checkpoint routed.dcp')
        self.assertLess(i+1,events.index('report_utilization'))

    def test_physical_failure_still_preserves_checkpoint(self):
        r,events,files=self.run_flow(physical_error=1)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(events[-2:],['checkpoint post_physopt.dcp','close'])
        self.assertIn('post_physopt.dcp',files);self.assertNotIn('routed.dcp',files)

    def test_route_failure_preserves_failed_scene(self):
        r,events,files=self.run_flow(after_fully=0,route_error=1)
        self.assertNotEqual(r.returncode,0);self.assertIn('failed_route.dcp',files)
        self.assertEqual(events[events.index('route_design -preserve')+1],'checkpoint failed_route.dcp')

    def test_remaining_hold_failure_retains_scene_without_pass(self):
        r,_,files=self.run_flow(row='0.017 0 0 100 -0.025 -0.025 1 100 0 0 0 100')
        self.assertNotEqual(r.returncode,0);self.assertIn('routed.dcp',files)
        self.assertNotIn('SCALELLM_RELEASE_STAGE_PASS',r.stdout)

    def test_wrong_inputs_do_not_invoke_physical_command(self):
        for opts in ({'bad_hash':True},{'bad_part':True},{'method':'aggressive_hold_fix'},{'initial_fully':0}):
            with self.subTest(opts=opts):
                r,events,_=self.run_flow(**opts)
                self.assertNotEqual(r.returncode,0)
                self.assertFalse(any(v.startswith('phys_opt_design') for v in events))

class RepairLauncherTests(unittest.TestCase):
    def test_checkpoint_selection_and_method_wiring(self):
        for stage,expected_method in [('hold-sll','sll_reg_hold_fix'),('hold','hold_fix'),('bitstream',None)]:
            with self.subTest(stage=stage),tempfile.TemporaryDirectory() as tmp:
                work=Path(tmp);source=work/'fresh_routed.dcp';source.write_text('CPU fixture')
                (work/'build.json').write_text(json.dumps(dict(source_inputs={},board_inputs={},board_files=str(work),vivado='mock-vivado')))
                args=argparse.Namespace(work=work,stage=stage,source_dcp=source,threads=4,cpus='0,1,2,3',timeout=7200,rss_gib=32)
                captured={}
                def launch(argv,**kw):
                    captured.update(argv=argv,env=kw['env'])
                    kw['stdout'].write('SCALELLM_RELEASE_STAGE_PASS stage='+stage+'\n');kw['stdout'].flush()
                    class Done:
                        returncode=0
                        def poll(self):return 0
                    return Done()
                with patch.object(builder.subprocess,'Popen',launch),patch.object(builder,'mem_available',return_value=128*builder.GIB),patch.object(builder.os,'sched_getaffinity',return_value={0,1,2,3}),patch.object(builder.os,'sched_setaffinity'),redirect_stdout(io.StringIO()):
                    builder.stage(args)
                self.assertEqual(captured['env']['HAP_SOURCE_DCP'],str(source))
                self.assertEqual(captured['env']['HAP_SOURCE_DCP_SHA256'],hashlib.sha256(source.read_bytes()).hexdigest())
                if expected_method:self.assertEqual(captured['env']['HAP_HOLD_METHOD'],expected_method)
                selected=next(v for v in captured['argv'] if v.endswith('.tcl'))
                self.assertTrue(selected.endswith('release_hold_repair.tcl' if expected_method else 'release_build_board.tcl'))
                self.assertEqual(json.loads((work/stage/'result.json').read_text())['source_checkpoint']['sha256'],hashlib.sha256(source.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()
