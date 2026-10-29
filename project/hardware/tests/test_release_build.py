# SPDX-License-Identifier: Apache-2.0
"""CPU tests for the actual Tcl publication guard, without invoking Vivado."""
from pathlib import Path
import subprocess
import tempfile
import unittest

HW=Path(__file__).resolve().parents[1]

class TimingGateTests(unittest.TestCase):
    def run_gate(self,row='0.017 0 0 100 0.002 0 0 100 0.000 0 0 100',fully=1,errors=0,drc=''):
        text=(HW/'vivado/scripts/release_reports.tcl').read_text()
        procedure=text[text.index('proc require_timing '):]
        with tempfile.TemporaryDirectory() as tmp:
            # A separately authored Vivado-shaped row exercises the real parser.
            report='WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints\n-----\n'+row+'\n'
            Path(tmp,'fixture.txt').write_text(report)
            script='''proc report_timing_summary {args} {
                set at [lsearch -exact $args -file]
                file copy -force [file join $::out fixture.txt] [lindex $args [expr {$at+1}]]
            }
            proc report_route_status {args} {
                if {[lindex $args 0] eq {-boolean_check}} {
                    if {[lindex $args 1] eq {ROUTED_FULLY}} {return $::fully}
                    return $::errors
                }
            }
            proc report_drc {args} {}
            proc get_drc_violations {args} {return $::drc}
            '''+procedure+f'\nset out {{{tmp}}}\nset fully {fully}\nset errors {errors}\nset drc {{{drc}}}\n'+'''if {[catch {require_timing $out} problem]} {puts "REJECT $problem";exit 1}
            puts ACCEPT
            '''
            return subprocess.run(['tclsh'],input=script,text=True,capture_output=True)

    def test_closed_timing_accepts(self):
        result=self.run_gate();self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('ACCEPT',result.stdout)

    def test_negative_margins_and_failures_reject(self):
        original='0.017 0 0 100 0.002 0 0 100 0.000 0 0 100'.split()
        for index in (0,4,8,1,2,5,6,9,10):
            with self.subTest(column=index):
                values=original.copy();values[index]='-0.001' if index in (0,4,8) else '1'
                self.assertNotEqual(self.run_gate(' '.join(values)).returncode,0)

    def test_incomplete_route_and_drc_reject(self):
        for args in ({'fully':0},{'errors':1},{'drc':'critical_violation'}):
            with self.subTest(args=args):self.assertNotEqual(self.run_gate(**args).returncode,0)

    def test_unparseable_report_rejects(self):
        self.assertNotEqual(self.run_gate('unavailable').returncode,0)

if __name__=='__main__':unittest.main()
