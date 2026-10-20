"""Focused independent negatives for the actual unmanaged-context recovery adapter."""
from pathlib import Path
import copy, json, os, subprocess, tempfile, unittest
from unittest.mock import patch
import native_init_recovery as r

class ContextProof(unittest.TestCase):
    def setUp(self):
        self.candidate=json.loads((r.REPORT/'m003_candidate_registration.json').read_text())
        self.actual=r.registry(r.REPORT/'xdc_registry_init.tsv')[str(r.OVERLAY)]
        self.prefix=(r.REPORT/'native_init_prefix.tcl').read_text()
        import zipfile
        self.embedded=[]
        with zipfile.ZipFile(r.REPORT/'init.dcp') as z:
            for name in z.namelist():
                if name.endswith('.xdc'):
                    self.embedded.extend(s for s in z.read(name).decode().splitlines() if s.startswith('set_property SRC_FILE_INFO '))
    def test_real_AT028_original_context_and_embedded_source(self):
        r.context_proof(self.candidate,self.actual,self.prefix,self.embedded)
    def test_original_guard_remains_strict(self):
        for key,value in [('FILE_TYPE','XDC'),('USED_IN_SYNTHESIS','1'),('USED_IN_IMPLEMENTATION','0'),('IS_ENABLED','0'),('PROCESSING_ORDER','EARLY'),('SCOPED_TO_CELLS','foreign'),('SCOPED_TO_REF','foreign')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                bad={**self.candidate,key:value};r.context_proof(bad,self.actual,self.prefix,self.embedded)
    def test_actual_flags_scope_and_order_cannot_be_generalized(self):
        for key,value in [('USED_IN_SYNTHESIS','0'),('USED_IN_IMPLEMENTATION','0'),('IS_ENABLED','0'),('PROCESSING_ORDER','NORMAL'),('SCOPED_TO_CELLS','foreign'),('SCOPED_TO_REF','foreign')]:
            with self.subTest(key=key),self.assertRaises(ValueError):r.context_proof(self.candidate,{**self.actual,key:value},self.prefix,self.embedded)
    def test_missing_duplicate_managed_or_postlink_overlay_read_rejected(self):
        needle='  read_xdc -unmanaged '+str(r.OVERLAY)
        for prefix in [self.prefix.replace(needle,''),self.prefix.replace(needle,needle+'\n'+needle),self.prefix.replace(needle,needle.replace('-unmanaged ','')),self.prefix.replace('  set_property design_mode GateLvl [current_fileset]',''),self.prefix.replace('  create_project -in_memory -part xcvu9p-flga2104-2L-e','')]:
            with self.subTest(prefix=hash(prefix)),self.assertRaises(ValueError):r.context_proof(self.candidate,self.actual,prefix,self.embedded)
    def test_missing_duplicate_scoped_wrong_order_embedded_source_rejected(self):
        selected=next(s for s in self.embedded if 'cfile:'+str(r.OVERLAY)+' ' in s)
        for embedded in [[s for s in self.embedded if s!=selected],[*self.embedded,selected],[s.replace('unmanaged:yes','unmanaged:no') if s==selected else s for s in self.embedded],[s.replace('order:LATE','order:EARLY') if s==selected else s for s in self.embedded],[s.replace(' unmanaged:yes ',' unmanaged:yes scoped_inst:foreign ') if s==selected else s for s in self.embedded]]:
            with self.subTest(change=str(embedded[-1])[:30]),self.assertRaises(ValueError):r.context_proof(self.candidate,self.actual,self.prefix,embedded)
    def test_frozen_stage_hook_replacement_preserves_every_other_command(self):
        with tempfile.TemporaryDirectory() as d:
            source=r.HW/'vivado/scripts/m002_diagnostic_common.tcl'
            tcl='set ::env(HAP_REPORT_DIR) {'+d+'}\nset ::env(HAP_M003_ACTIVE) 1\nsource {'+str(source)+'}\n'
            tcl+='set old [info body m002_post]\nset adapter_dir {'+str(r.HERE)+'}\n'
            text=(r.HERE/'recover_init.tcl').read_text();part=text.split('set body [info body m002_post]',1)[1].split('m002_put [file join $report_dir stage_hook_adapter.txt]',1)[0]
            tcl+='set body [info body m002_post]'+part
            tcl+='puts [binary encode base64 -maxlen 0 [info body m002_post]]\nputs [binary encode base64 -maxlen 0 $old]\n'
            code=subprocess.run(['tclsh'],input=tcl,text=True,capture_output=True);self.assertEqual(code.returncode,0,code.stderr);self.assertEqual(code.stderr,'')
            import base64
            new,old=[base64.b64decode(s).decode() for s in code.stdout.splitlines()]
            needle='m003_python [file join $::m002_script_dir m003_physical_evidence.py] hook-batch $point $::m002_report_dir'
            replacement='m003_python {'+str(r.HERE/'native_init_recovery.py')+'} hook-batch $point $::m002_report_dir'
            self.assertEqual(new,old.replace(needle,replacement));self.assertEqual(old.count(needle),1)

class ConstraintInheritance(unittest.TestCase):
    def test_reapply_changed_source_scope_and_new_source_rejected(self):
        for mutation in ['none','reapply','scope','bytes','new_source','missing_observation']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
                report=Path(d);source=report/'actual.xdc';source.write_text('# immutable fixture source\n');ident=r.old.file_id(source)
                fields=['synthesis implementation','1','1','1','','','LATE']
                header='path\tUSED_IN\tUSED_IN_SYNTHESIS\tUSED_IN_IMPLEMENTATION\tIS_ENABLED\tSCOPED_TO_REF\tSCOPED_TO_CELLS\tPROCESSING_ORDER\tSHA256\n'
                row=str(source)+'\t'+'\t'.join(fields)+'\tPENDING_BATCH_HASH\n'
                prior=dict(hashes={str(source):ident['sha256']},metadata={str(source):fields})
                (report/'constraints_project.json').write_text(json.dumps(prior));(report/'xdc_registry_init.tsv').write_text(header+row)
                (report/'embedded_xdc_registry_init.tsv').write_text('raw actual tool fixture\n');(report/'restore_apply_attempts.json').write_text(json.dumps(dict(before=0,after=0,delta=0)))
                value=dict(original_native_reads=[dict(source=ident)],original_actual_apply=dict(actual_native_apply_count=1),checkpoint=ident)
                package=report/'package.json';package.write_text('{}')
                if mutation=='reapply':(report/'restore_apply_attempts.json').write_text(json.dumps(dict(before=0,after=1,delta=1)))
                if mutation=='scope':(report/'xdc_registry_init.tsv').write_text(header+row.replace('\t\t\tLATE','\t\tforeign\tLATE'))
                if mutation=='bytes':source.write_text('changed')
                if mutation=='new_source':
                    extra=report/'new.xdc';extra.write_text('new');(report/'xdc_registry_init.tsv').write_text(header+row+str(extra)+'\t'+'\t'.join(fields)+'\tPENDING_BATCH_HASH\n')
                if mutation=='missing_observation':(report/'embedded_xdc_registry_init.tsv').unlink()
                with patch.object(r,'verify',return_value=value),patch.dict(os.environ,{'HAP_M003_INIT_RECOVERY_PACKAGE':str(package)}):
                    if mutation=='none':
                        result=r.constraints('init',report);self.assertEqual(result['actual_reads']['path'],str(report/'actual_xdc_reads_init.json'))
                    else:
                        with self.assertRaises(ValueError):r.constraints('init',report)
class ControlledSerialization(unittest.TestCase):
    def test_exact_native_string_zeros_and_integer_zeros(self):
        self.assertEqual(r.zero_reapply(dict(before='0',after='0',delta='0')),dict(before=0,after=0,delta=0))
        self.assertEqual(r.zero_reapply(dict(before=0,after=0,delta=0)),dict(before=0,after=0,delta=0))
    def test_missing_extra_unknown_nonzero_float_bool_nan_are_rejected(self):
        values=[None,'',False,True,0.0,float('nan'),float('inf'),'NaN','0.0','00','-0',' 0','0 ','false',1,'1',-1,'-1',[],{}]
        for name in ['before','after','delta']:
            for value in values:
                with self.subTest(name=name,value=repr(value)),self.assertRaises(ValueError):
                    r.zero_reapply({**dict(before='0',after='0',delta='0'),name:value})
        for value in [None,[],dict(before='0',after='0'),dict(before='0',after='0',delta='0',extra='0')]:
            with self.subTest(value=value),self.assertRaises(ValueError):r.zero_reapply(value)
class AdapterSymbolInterface(unittest.TestCase):
    def test_all_new_python_module_attribute_references_exist(self):
        import ast
        modules={name:getattr(r,name) for name in ['base','joint','old','stage','entry','init']}
        for path in [r.HERE/'native_init_recovery.py',r.HERE/'launch.py']:
            tree=ast.parse(path.read_text())
            active={**modules,'recovery':r}
            for node in ast.walk(tree):
                if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id in active:
                    with self.subTest(file=path.name,module=node.value.id,symbol=node.attr):self.assertTrue(hasattr(active[node.value.id],node.attr))
    def test_real_production_tcl_adapter_symbol_arguments(self):
        code='source {'+str(r.HW/'vivado/scripts/m003_joint_checks.tcl')+'}\n'
        for name in ['collection_property','resolve','prop','jobject']:
            code+='puts "'+name+'=[info args ::m003::'+name+']"\n'
        out=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
        self.assertEqual(out.returncode,0,out.stderr);self.assertEqual(out.stderr,'')
        fields=dict(line.split('=',1) for line in out.stdout.splitlines())
        self.assertEqual(fields['collection_property'],'property objects');self.assertEqual(fields['resolve'],'')
        self.assertEqual(fields['prop'],'object name');self.assertTrue(fields['jobject'])
class RealRestoreProofNegatives(unittest.TestCase):
    def test_actual_AT030_records_reject_unknown_duplicate_missing_extra_and_wrong_pool(self):
        original=r.HW/'vivado/reports/m003_E011_R002_AT030_strict_zero_reuse_INIT_to_OPT'
        events=[json.loads(line) for line in (original/'restored_effective_membership.jsonl').read_text().splitlines()]
        reused=dict(input_snapshot=r.old.file_id(r.HW/'vivado/reports/m003_E011_R002_AT029_recovered_native_init_postcheck/m003_native_init.json'))
        value=dict(reuse_init=reused,checkpoint=r.old.file_id(r.REPORT/'init.dcp'))
        firstcell=next(i for i,x in enumerate(events) if x['kind']=='cell');firstblock=next(i for i,x in enumerate(events) if x['kind']=='pblock')
        for mutation in ['extra_block','duplicate_cell','missing_cell','unknown_kind','wrong_sites','soft_block','duplicate_block']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as d:
                changed=copy.deepcopy(events);dest=Path(d)
                if mutation=='extra_block':changed[firstcell]['PBLOCKS']+=' foreign_wrong_block'
                if mutation=='duplicate_cell':changed.append(changed[firstcell])
                if mutation=='missing_cell':changed.pop(firstcell)
                if mutation=='unknown_kind':changed.append(dict(kind='unknown',NAME='foreign'))
                if mutation=='wrong_sites':changed[firstblock]['actual_sites']+=' UNKNOWN_SITE'
                if mutation=='soft_block':changed[firstblock]['IS_SOFT']='1'
                if mutation=='duplicate_block':changed.append(changed[firstblock])
                (dest/'restored_effective_membership.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in changed))
                (dest/'restore_apply_attempts.json').write_text((original/'restore_apply_attempts.json').read_text())
                with patch.object(r,'verify',return_value=value),patch.dict(os.environ,{'HAP_M003_INIT_RECOVERY_PACKAGE':'/unit-test-only'}),self.assertRaises(ValueError):r.restore_proof(dest)
class ActualOPTResetLiteral(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=r.HW/'vivado/reports/m003_E011_R002_AT031_verified_restore_parser_to_OPT/m003_native_opt.json'
        actual=r.joint.decode_grouped_snapshot(json.loads(source.read_text()))
        cls.raw=dict(reset_provenance=actual['reset_provenance'])
        cls.original=[row for row in actual['cells'] if row['role']=='core_address']
        cls.helpers=[row for row in actual['cells'] if row['role']=='address']
        cls.sources={k:set(r.joint.words(v)) for k,v in actual['control_sources'].items()}
    def checked(self,snapshot):
        observed=r.normalize_cell_literals(snapshot);errors=[]
        r.joint.validate_native_reset(snapshot,self.original,self.helpers,self.sources,lambda ok,msg:errors.append(msg) if not ok else None)
        return observed,errors
    def test_actual_OPT_all51_functions_and_raw_observations(self):
        actual=copy.deepcopy(self.raw);obs,errors=self.checked(actual)
        self.assertEqual(errors,[]);self.assertEqual(len(obs),51)
        self.assertEqual(sum(row['normalization']=='width1_binary_cell_literal' for row in obs),17)
        self.assertEqual(sum(row['raw_cell']=="1'b1" and row['raw_pin']=='1' for row in obs),17)
        self.assertEqual(sum(row['raw_cell']=='' and row['raw_pin']=='0' for row in obs),34)
        self.assertEqual(self.raw['reset_provenance'],copy.deepcopy(self.raw)['reset_provenance'])
    def test_unknown_multibit_and_truthy_cell_values_rejected(self):
        for value in ["1'bx","1'bz","2'b01","2'b11","1'b01","1'h1","1'd1","'1","1'B1",True,1,1.0,None,'TRUE-ish','yes',' 1',"1'b2"]:
            with self.subTest(value=value):
                snap=copy.deepcopy(self.raw);ep=next(x for x in snap['reset_provenance'] if x.get('kind')=='endpoint' and x['family']=='core');ep['IS_CLR_INVERTED']=value
                self.assertTrue(self.checked(snap)[1])
    def test_actual_pin_missing_unknown_conflict_and_wrong_function_rejected(self):
        for mutation in ['missing_pin','empty_pin','pin_literal','pin_x','pin_none','conflicting_cell','changed_function','missing_cell']:
            with self.subTest(mutation=mutation):
                snap=copy.deepcopy(self.raw);ep=next(x for x in snap['reset_provenance'] if x.get('kind')=='endpoint' and x['family']=='core')
                if mutation=='missing_pin':del ep['pin_IS_INVERTED']
                if mutation=='empty_pin':ep['pin_IS_INVERTED']=''
                if mutation=='pin_literal':ep['pin_IS_INVERTED']="1'b1"
                if mutation=='pin_x':ep['pin_IS_INVERTED']='x'
                if mutation=='pin_none':ep['pin_IS_INVERTED']=None
                if mutation=='conflicting_cell':ep['IS_CLR_INVERTED']="1'b0"
                if mutation=='changed_function':ep.update(IS_CLR_INVERTED="1'b0",pin_IS_INVERTED='0')
                if mutation=='missing_cell':del ep['IS_CLR_INVERTED']
                self.assertTrue(self.checked(snap)[1])
    def test_empty_or_unsupported_cell_still_requires_actual_pin_and_function(self):
        for value in ['', 'NOT_SUPPORTED', '1', 'true', "1'b1"]:
            snap=copy.deepcopy(self.raw);ep=next(x for x in snap['reset_provenance'] if x.get('kind')=='endpoint' and x['family']=='core');ep['IS_CLR_INVERTED']=value
            self.assertEqual(self.checked(snap)[1],[])
class ExactTclOPTRecovery(unittest.TestCase):
    def test_original_suffix_and_single_qualifier_change_are_exact(self):
        with tempfile.TemporaryDirectory() as d:
            source=r.HW/'vivado/scripts/m002_diagnostic_common.tcl';text=(r.HERE/'recover_init.tcl').read_text()
            start=text.index('set body [info body m002_post]');end=text.index('proc m003_recovery_command')
            code='set ::env(HAP_REPORT_DIR) {'+d+'}\nset ::env(HAP_M003_ACTIVE) 1\nsource {'+str(source)+'}\nsource {'+str(r.HW/'vivado/scripts/m003_joint_checks.tcl')+'}\nset adapter_dir {'+str(r.HERE)+'}\nset report_dir {'+d+'}\nset original [info body m002_post]\nset snap [info body m003::snapshot_body]\n'
            code+=text[start:end]+'\nm003_recovery_install_qualifier\n'
            code+='foreach value [list $original [info body m002_post] $snap [info body m003::snapshot_body] [info body m003_complete_opt_post]] {puts [binary encode base64 -maxlen 0 $value]}\n'
            out=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
            self.assertEqual(out.returncode,0,out.stderr);self.assertEqual(out.stderr,'')
            import base64
            original,post,snap,new_snap,suffix=[base64.b64decode(x).decode() for x in out.stdout.splitlines()]
            hook='m003_python [file join $::m002_script_dir m003_physical_evidence.py] hook-batch $point $::m002_report_dir'
            sourced='source [file join $::m002_script_dir m003_joint_checks.tcl]'
            expected=original.replace(hook,'m003_python {'+str(r.HERE/'native_init_recovery.py')+'} hook-batch $point $::m002_report_dir').replace(sourced,sourced+'\n        m003_recovery_install_qualifier')
            self.assertEqual(post,expected)
            needle='m003_python [file join $scripts m003_joint_evidence.py] --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]'
            self.assertEqual(snap.count(needle),1)
            replacement='m003_python {'+str(r.HERE/'native_init_recovery.py')+'} qualify --snapshot [file join $out m003_native_${phase}.json] --spec $spec_path --output [file join $out m003_qualification_${phase}.json]'
            self.assertEqual(new_snap,snap.replace(needle,replacement))
            marker='    if {$point in {place physopt route}}'
            self.assertEqual(suffix,'set point opt\nset bb [get_cells -quiet -hier -filter {IS_BLACKBOX == 1}]\n'+post[post.index(marker):])
if __name__=='__main__':unittest.main(verbosity=2)
