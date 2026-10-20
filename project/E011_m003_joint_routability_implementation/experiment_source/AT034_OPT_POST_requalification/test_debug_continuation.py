"""Preserve all real debug logic and validate the new continuation module interfaces."""
from pathlib import Path
import ast,base64,subprocess,tempfile,unittest
import qualified_opt_evidence as e
class FullDebugPreservation(unittest.TestCase):
    def test_exact_OPT_replacement_full_debug_and_native_restore_intact(self):
        text=(e.HERE/'qualified_opt_debug.tcl').read_text();prefix=text.split('uplevel #0 $adapted_body',1)[0]
        prefix=prefix.replace('set qualified_opt_dir [file dirname [file normalize [info script]]]','set qualified_opt_dir {'+str(e.HERE)+'}')
        out=subprocess.run(['tclsh'],input=prefix+'\nforeach value [list $original_body $adapted_body $old_dir $old_opt $new_opt] {puts [binary encode base64 -maxlen 0 $value]}\n',text=True,capture_output=True)
        self.assertEqual(out.returncode,0,out.stderr);self.assertEqual(out.stderr,'')
        original,actual,old_dir,old_opt,new_opt=[base64.b64decode(x).decode() for x in out.stdout.splitlines()]
        self.assertEqual(actual,original.replace(old_dir,'set adapter_dir '+str(e.r.HERE)).replace(old_opt,new_opt))
        suffix='set cores [get_debug_cores -quiet]'
        self.assertEqual(original[original.index(suffix):],actual[actual.index(suffix):])
        for guard in ['m003::require_project','m003::require_synthesis_runs','restore_apply_attempts.json','restore-proof init $report_dir','implement_debug_core','m002_post debug_materialized','m003_stage.py] preplace']:
            self.assertIn(guard,actual)
        self.assertNotIn('m003_complete_opt_post\n} else',actual)
    def test_new_python_project_module_symbols_exist(self):
        import run_qualified_opt_debug as runner
        modules=dict(r=e.r,q=e.q,e=e,native=runner.native)
        for name in ['run_qualified_opt_debug.py','qualified_opt_evidence.py']:
            for node in ast.walk(ast.parse((e.HERE/name).read_text())):
                if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id in modules:
                    with self.subTest(file=name,module=node.value.id,symbol=node.attr):self.assertTrue(hasattr(modules[node.value.id],node.attr))
if __name__=='__main__':unittest.main(verbosity=2)
