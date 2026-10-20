"""Real-data CPU mutation tests; no native observations or historical receipts fabricated."""
from pathlib import Path
import copy,json,shutil,tempfile,unittest
from unittest.mock import patch
import qualify_actual_OPT_POST as q
class CurrentCompleteReports(unittest.TestCase):
    def fixture(self,d):
        d=Path(d)
        for i in range(4):
            p=q.ACTUAL/f'cdc_changed_opt_{i}.rpt';(d/p.name).write_text(p.read_text().replace(str(q.ACTUAL),str(d)))
        shutil.copyfile(q.ACTUAL/'cdc_opt.rpt',d/'cdc_opt.rpt')
        rows=[line.replace(str(q.ACTUAL),str(d)) for line in (q.ACTUAL/'cdc_changed_reset_opt.tsv').read_text().splitlines() if line.startswith('TARGETED_CDC_')]
        raw=d/'cdc_changed_reset_opt.tsv';raw.write_text('\n'.join(rows)+'\n')
        binding=dict(reports=[q.r.old.file_id(d/f'cdc_changed_opt_{i}.rpt') for i in range(4)])
        return raw,binding
    def test_actual_reports_relocated_fixture_complete_and_unknown_retained(self):
        with tempfile.TemporaryDirectory() as d:
            raw,binding=self.fixture(d);out=q.r.old.auxiliary_cdc_limits(raw,_e005_binding=binding)
            self.assertEqual(out['coverage'],'coverage_limited');self.assertEqual(out['critical_rows'],8)
            self.assertEqual(len(out['raw_sentinels']),4);self.assertEqual(out['object_counts'],[668,668,768,769]);self.assertEqual(out['object_limit'],64)
    def test_identity_header_tuple_union_command_count_and_unknown_mutations_rejected(self):
        mutations=['stale_identity','wrong_tool','wrong_design','wrong_device','wrong_state','wrong_header_command','wrong_tuple','incomplete_summary','empty_details','wrong_cap_count','missing_UNKNOWN','duplicate_UNKNOWN','wrong_raw_command','wrong_full_union']
        for mutation in mutations:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
                raw,binding=self.fixture(d);report=Path(d)/'cdc_changed_opt_0.rpt';text=report.read_text()
                if mutation=='stale_identity':report.write_text(text+'\nchanged\n')
                if mutation=='wrong_tool':text=text.replace('Vivado v.2025.2','Vivado v.2025.1')
                if mutation=='wrong_design':text=text.replace('scalellm_vcu118_f05_bd_wrapper','foreign_wrapper')
                if mutation=='wrong_device':text=text.replace('xcvu9p-flga2104','xcvu7p-flga2104')
                if mutation=='wrong_state':text=text.replace('Optimized','Placed')
                if mutation=='wrong_header_command':text=text.replace('-all_checks_per_endpoint','-summary_only')
                if mutation=='wrong_tuple':text=text.replace('arststages_ff_reg[0]/CLR','arststages_ff_reg[0]/D')
                if mutation=='incomplete_summary':text=text.replace('Critical      3','Critical      4')
                if mutation=='empty_details':text='\n'.join(x for x in text.splitlines() if not __import__('re').match(r'^\s*\d+\s+CDC-',x))
                if mutation in ['wrong_tool','wrong_design','wrong_device','wrong_state','wrong_header_command','wrong_tuple','incomplete_summary','empty_details']:
                    self.assertNotEqual(report.read_text(),text);report.write_text(text);binding['reports'][0]=q.r.old.file_id(report)
                if mutation=='wrong_cap_count':raw.write_text(raw.read_text().replace('\t668\tLIMIT=64','\t667\tLIMIT=64',1))
                if mutation=='missing_UNKNOWN':raw.write_text('\n'.join(x for x in raw.read_text().splitlines() if 'VIOLATIONS_UNKNOWN\tm002_changed_reset_opt_0' not in x)+'\n')
                if mutation=='duplicate_UNKNOWN':raw.write_text(raw.read_text()+'TARGETED_CDC_VIOLATIONS_UNKNOWN\tm002_changed_reset_opt_0\n')
                if mutation=='wrong_raw_command':raw.write_text(raw.read_text().replace('-severity Critical','-severity Warning',1))
                if mutation=='wrong_full_union':
                    full=Path(d)/'cdc_opt.rpt';full.write_text(full.read_text().replace('arststages_ff_reg[0]/CLR','arststages_ff_reg[0]/D',1))
                with self.assertRaises(ValueError):q.r.old.auxiliary_cdc_limits(raw,_e005_binding=binding)
class M003ActualProvenance(unittest.TestCase):
    def test_actual_chain_current_source_binding_and_no_safety_success_claim(self):
        value=q.provenance();self.assertEqual(value['schema'],'M003_same_actual_OPT_targeted_CDC_binding_v1')
        self.assertEqual(value['formal_reset_cdc_safety'],'OPEN');self.assertTrue(value['raw_UNKNOWN_retained']);self.assertEqual(len(value['reports']),4)
    def test_wrong_terminal_phase_checkpoint_and_failure_scope_rejected_in_memory(self):
        original=Path.read_text
        cases=[(q.JOB/'status.json','native_exit_code',0),(q.JOB/'status.json','stop_reason','forced'),(q.ACTUAL/'M003_init_recovery_parent.json','OPT_executed',True),(q.ACTUAL/'M003_init_recovery_parent.json','restored_phase','debug_materialized'),(q.ACTUAL/'integrity_opt.json','gate_issues',[])]
        for source,key,value in cases:
            with self.subTest(key=key):
                def changed(path,*args,**kwargs):
                    text=original(path,*args,**kwargs)
                    if path==source:
                        data=json.loads(text);data[key]=value;return json.dumps(data)
                    return text
                with patch.object(Path,'read_text',changed),self.assertRaises(ValueError):q.provenance()
if __name__=='__main__':unittest.main(verbosity=2)
