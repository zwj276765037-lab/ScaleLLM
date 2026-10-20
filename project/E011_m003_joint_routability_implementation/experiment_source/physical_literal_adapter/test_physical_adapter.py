"""Offline preservation/mutation checks; no native tool execution or G4 claim."""
from pathlib import Path
import base64,json,subprocess,tempfile,unittest
import physical_literal_adapter as a

class PhysicalOriginalPreservation(unittest.TestCase):
    def tcl(self,extra):
        text=(a.HERE/'physical_literal_adapter.tcl').read_text().split('set h [open [file join $physical_original_dir m003_physical.tcl]',1)[0]
        text=text.replace('set physical_adapter_dir [file dirname [file normalize [info script]]]','set physical_adapter_dir {'+str(a.HERE)+'}')
        with tempfile.TemporaryDirectory() as d:
            code='set ::env(HAP_REPORT_DIR) {'+d+'}\nset ::env(HAP_M003_ACTIVE) 1\nsource {'+str(a.HW/'vivado/scripts/m002_diagnostic_common.tcl')+'}\nsource {'+str(a.HW/'vivado/scripts/m003_joint_checks.tcl')+'}\n'
            code+=text+'\n'+extra
            result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stderr,'');return result.stdout.splitlines()
    def test_full_original_physical_entry_and_stage_guards_preserved(self):
        original=(a.HW/'vivado/scripts/m003_physical.tcl').read_text()
        extra='set h [open {'+str(a.HW/'vivado/scripts/m003_physical.tcl')+'} r];set body [read $h];close $h\nputs [binary encode base64 -maxlen 0 [m003_physical_adapt $body]]\n'
        [observed]=self.tcl(extra);adapted=base64.b64decode(observed).decode()
        root='set script_dir [file dirname [file normalize [info script]]]';sourced='source [file join $script_dir m003_joint_checks.tcl]'
        self.assertEqual(adapted,original.replace(root,'set script_dir '+str(a.HW/'vivado/scripts')).replace(sourced,sourced+'\nm003_physical_install_qualifier\nm003_physical_install_post'))
        for exact in ['m003::snapshot restore $report_dir','m003_command place {place_design -directive SSI_SpreadSLLs}','m003_command physopt {phys_opt_design -directive Default}','m003_command route {route_design -directive Default}','M003 checkpoint restore attempted to reapply constraints']:
            self.assertEqual(adapted.count(exact),original.count(exact));self.assertIn(exact,adapted)
    def test_POST_only_installs_qualifier_after_original_fresh_source(self):
        lines=self.tcl('set old [info body m002_post]\nm003_physical_install_post\nforeach value [list $old [info body m002_post]] {puts [binary encode base64 -maxlen 0 $value]}\n')
        old,new=[base64.b64decode(x).decode() for x in lines];needle='source [file join $::m002_script_dir m003_joint_checks.tcl]'
        self.assertEqual(old.count(needle),1);self.assertEqual(new,old.replace(needle,needle+'\n        m003_physical_install_qualifier'))
    def test_full_snapshot_body_has_one_call_substitution(self):
        lines=self.tcl('set old [info body m003::snapshot_body]\nm003_physical_install_qualifier\nforeach value [list $old [info body m003::snapshot_body]] {puts [binary encode base64 -maxlen 0 $value]}\n')
        old,new=[base64.b64decode(x).decode() for x in lines]
        needle='m003_python [file join $scripts m003_joint_evidence.py] --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]'
        replacement='m003_python {'+str(a.HERE.parent/'AT028_init_recovery/native_init_recovery.py')+'} qualify --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]'
        self.assertEqual(old.count(needle),1);self.assertEqual(new,old.replace(needle,replacement))
    def test_changed_or_duplicate_physical_targets_rejected(self):
        extra='set h [open {'+str(a.HW/'vivado/scripts/m003_physical.tcl')+'} r];set body [read $h];close $h\n'
        extra+='set needle {source [file join $script_dir m003_joint_checks.tcl]}\n'
        extra+='foreach changed [list [string map [list $needle {}] $body] "$body\n$needle"] {puts [catch {m003_physical_adapt $changed}]}\n'
        self.assertEqual(self.tcl(extra),['1','1'])
    def test_changed_qualifier_and_POST_source_rejected(self):
        extra='set body [info body m003::snapshot_body]\nproc m003::snapshot_body {phase out} [string map {m003_joint_evidence.py foreign.py} $body]\nputs [catch {m003_physical_install_qualifier}]\n'
        extra+='set body [info body m002_post]\nproc m002_post {point} [string map {m003_joint_checks.tcl foreign.tcl} $body]\nputs [catch {m003_physical_install_post}]\n'
        self.assertEqual(self.tcl(extra),['1','1'])
class PhysicalDependencyBinding(unittest.TestCase):
    def test_real_dependencies_and_changed_digest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'package.json';value=a.dependency_package(p);self.assertEqual(a.verify(p),value)
            value['sources'][0]['sha256']='0'*64;p.write_text(json.dumps(value))
            with self.assertRaises(ValueError):a.verify(p)
    def test_original_launcher_G4_and_review_checks_remain_the_same_file(self):
        import inspect
        text=inspect.getsource(a.native.main)
        for needle in ["gate.get('no_blocker') is True", "gate.get('package_sha256')==old.sha256", "old.verify_identity(review)", "review_path.is_relative_to(HW.parent.parent/'agent/A007')", "verdict.get('no_blocker') is True", "verdict.get('package_sha256')==gate['package_sha256']"]:self.assertIn(needle,text)
if __name__=='__main__':unittest.main(verbosity=2)
