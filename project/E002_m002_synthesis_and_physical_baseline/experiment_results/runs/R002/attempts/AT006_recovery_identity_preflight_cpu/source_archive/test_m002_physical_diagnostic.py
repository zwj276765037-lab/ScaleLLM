"""Diagnostic admission regressions. Fixtures never invoke EDA."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'vivado/scripts'
sys.path.insert(0, str(SCRIPTS))
import m002_physical_evidence as m


def put(path, text='fixture'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def manifest(path, files):
    put(path, ''.join(f'{m.sha256(p)}  {p}\n' for p in files))


def cdc(rows):
    return ('CDC Report\nCDC-3 Info 1 synchronized\n' +
            (f'CDC-10 Critical {len(rows)} Combinational\n' if rows else '') +
            'Source Clock: source\nDestination Clock: dest\n0  CDC-3  Info  Synchronized  4  False Path  info_src/C  info_dest/D\n' + ''.join(
            f'{i}  CDC-10  Critical  Logic  4  Asynch Clock Groups  src{i}/C  {r}\n' for i, r in enumerate(rows)))


def timing(path, no_clock=(), unconstrained=(), inputs=(), outputs=()):
    values = dict(no_clock=no_clock, unconstrained_internal_endpoints=unconstrained, no_input_delay=inputs,
                  no_output_delay=outputs, multiple_clock=(), generated_clocks=(), loops=(), pulse_width_clock=())
    put(path, ''.join(f'{i}. checking {k} ({len(v)})\n----\n There are objects\n\n' + '\n'.join(v) + '\n\n'
                     for i, (k, v) in enumerate(values.items(), 1)))


class Temp(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)


class Lineage(Temp):
    def setUp(self):
        super().setUp()
        self.project, self.report, self.attempt = [self.root / p for p in ('project', 'report', 'attempt')]
        manifest(self.report / 'inputs.sha256', [put(self.root / 'src' / str(i), str(i)) for i in range(339)])
        put(self.report / 'build_identity.txt'); put(self.report / 'fresh_synth_complete.txt')
        put(self.report / 'launcher_status.txt', f'stage=synth\nexit_code=0\nnative_exit_code=0\nproject={self.project}\n')
        put(self.attempt / 'status.json', json.dumps(dict(stage='synth', project=str(self.project), report=str(self.report),
            exit_code=0, native_exit_code=0, stop_reason=None, owned_survivors=[])))
        self.binding = dict(project=str(self.project), run_records=[], consumed_ip_records=[], checkpoints={})
        files = []
        for i in range(23):
            name = 'synth_1' if not i else f'scalellm_vcu118_f05_bd_ip{i}_synth_1'
            stem = 'scalellm_vcu118_f05_bd_wrapper' if not i else name.removesuffix('_synth_1')
            run = self.project / 'scalellm_vcu118_f05.runs' / name
            dcp = put(run / (stem + '.dcp'), str(i)); receipt = put(run / '.vivado.end.rst', '')
            self.binding['run_records'].append(dict(run=name, checkpoint=str(dcp), end_receipt=str(receipt)))
            files.append(dcp)
            if i:
                consumed = put(self.project / 'scalellm_vcu118_f05.gen' / str(i) / (stem + '.dcp'), str(i))
                self.binding['consumed_ip_records'].append(dict(path=str(consumed), cell=f'scalellm_vcu118_f05_bd_i/ip{i}'))
                files.append(consumed)
        self.binding['checkpoints'] = {str(p): m.file_id(p) for p in files}
        manifest(self.attempt / 'synth_checkpoint_bindings.sha256', files)
        self.save()
        self.anchors = {}
        self.reanchor()
        self.patcher = patch.object(m, 'SYNTH_ANCHORS', self.anchors); self.patcher.start(); self.addCleanup(self.patcher.stop)

    def save(self):
        put(self.attempt / 'synth_checkpoint_bindings.json', json.dumps(self.binding))

    def reanchor(self):
        for n in m.SYNTH_ANCHORS:
            p = (self.report if n in {'inputs.sha256', 'build_identity.txt', 'fresh_synth_complete.txt'} else self.attempt) / n
            self.anchors[n] = m.sha256(p)

    def check(self):
        return m.synth_lineage(self.project, self.report, self.attempt)

    def test_complete(self):
        self.assertEqual(self.check()['checkpoint_paths'], 45)

    def test_input_tamper(self):
        put(self.root / 'src/4', 'modified Tcl')
        with self.assertRaisesRegex(ValueError, 'changed input'): self.check()

    def test_manifest_anchor(self):
        put(self.report / 'inputs.sha256', 'rewritten')
        with self.assertRaisesRegex(ValueError, 'identity record changed'): self.check()

    def test_missing_source_row(self):
        p = self.report / 'inputs.sha256'; put(p, '\n'.join(p.read_text().splitlines()[:-1]) + '\n'); self.reanchor()
        with self.assertRaisesRegex(ValueError, 'incomplete frozen'): self.check()

    def test_duplicate_source(self):
        p = self.report / 'inputs.sha256'; put(p, p.read_text() + p.read_text().splitlines()[0] + '\n'); self.reanchor()
        with self.assertRaisesRegex(ValueError, 'duplicate input'): self.check()

    def test_missing_dcp(self):
        p = self.attempt / 'synth_checkpoint_bindings.sha256'; put(p, '\n'.join(p.read_text().splitlines()[:-1]) + '\n'); self.reanchor()
        with self.assertRaisesRegex(ValueError, 'incomplete frozen'): self.check()

    def test_duplicate_run(self):
        self.binding['run_records'][1] = self.binding['run_records'][2]; self.save(); self.reanchor()
        with self.assertRaisesRegex(ValueError, 'duplicate/foreign synthesis run'): self.check()

    def test_foreign_consumed(self):
        self.binding['consumed_ip_records'][0]['path'] = str(self.root / 'foreign.dcp'); self.save(); self.reanchor()
        with self.assertRaisesRegex(ValueError, 'duplicate/foreign consumed'): self.check()

    def test_wrong_consumed_bytes(self):
        p = Path(self.binding['consumed_ip_records'][0]['path']); put(p, 'foreign bytes')
        manifest(self.attempt / 'synth_checkpoint_bindings.sha256', [Path(n) for n in self.binding['checkpoints']])
        self.binding['checkpoints'][str(p)] = m.file_id(p); self.save(); self.reanchor()
        with self.assertRaisesRegex(ValueError, 'frozen synthesized copy'): self.check()

    def test_status_project(self):
        p = self.attempt / 'status.json'; d = json.loads(p.read_text()); d['project'] = 'foreign'; put(p, json.dumps(d)); self.reanchor()
        with self.assertRaisesRegex(ValueError, 'identity mismatch'): self.check()

    def test_failed_native_receipt(self):
        put(Path(self.binding['run_records'][1]['end_receipt']).with_name('.vivado.error.rst'))
        with self.assertRaisesRegex(ValueError, 'missing/failed'): self.check()


class Coverage(Temp):
    def test_timing_negative_zero_counts_totals_nan(self):
        d = dict.fromkeys(('wns','whs','wpws','tns','ths','tpws','setup_failing_endpoints','hold_failing_endpoints','pw_skew_failing_endpoints'), 0.)
        self.assertEqual(m.timing_verdict(d), 'PASS')
        d['whs'] = -.000; d['hold_failing_endpoints'] = 1
        self.assertEqual(m.timing_verdict(d), 'FAIL')
        d['hold_failing_endpoints'] = 0; d['tns'] = -1
        self.assertEqual(m.timing_verdict(d), 'FAIL')
        d['tns'] = float('nan'); self.assertEqual(m.timing_verdict(d), 'NOT_EVALUABLE')

    def test_real_reports(self):
        r = SCRIPTS.parent / 'reports/m002_E002_R001_AT002_fresh_synth'
        self.assertEqual(m.timing_verdict(m.timing_metrics(r / 'timing_post_synth.rpt')), 'FAIL')
        self.assertEqual(len(m.cdc_critical_records(r / 'cdc_post_synth.rpt')), 6)
        self.assertEqual(len(m.timing_objects(r / 'check_timing_post_synth.rpt','no_clock')),530)

    def test_debug_complete_fanout_required(self):
        p = self.root / 'timing'
        cell = 'scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_top/u_ddr_cal/U_XSDB_SLAVE/r'
        timing(p,[cell+'/C'],[cell+'/D'])
        self.assertTrue(m.debug_gap_coverage(p,{cell+'/C'},True))
        self.assertFalse(m.debug_gap_coverage(p,set(),True))
        self.assertFalse(m.debug_gap_coverage(p,{cell+'/C'},False))
        timing(p); self.assertFalse(m.debug_gap_coverage(p,set(),True))
        timing(p,['foreign/r/C'],['foreign/r/D']); self.assertFalse(m.debug_gap_coverage(p,{'foreign/r/C'},True))

    def test_truncated_and_unparsed_timing(self):
        p=self.root/'timing'; timing(p,['scope/r/C']); put(p,p.read_text().replace('scope/r/C\n',''))
        with self.assertRaisesRegex(ValueError,'count mismatch'): m.timing_objects(p,'no_clock')
        timing(p,['MALFORMED'])
        with self.assertRaisesRegex(ValueError,'unparsed timing'): m.timing_objects(p,'no_clock')

    def test_unknown_io(self):
        p=self.root/'timing'; timing(p,inputs=['data_in'])
        with self.assertRaisesRegex(ValueError,'unclassified untimed IO'): m.reset_io_coverage(p)

    def test_new_critical_and_empty_cdc(self):
        old,new=self.root/'old',self.root/'new'; put(old,cdc([f'known{i}/D' for i in range(6)])); put(new,old.read_text())
        self.assertEqual(m.critical_coverage(new,old)['remaining_known'],6)
        put(new,cdc([f'known{i}/D' for i in range(5)]+['unknown/D']))
        with self.assertRaisesRegex(ValueError,'new/unclassified'): m.critical_coverage(new,old)
        put(new,'')
        with self.assertRaisesRegex(ValueError,'missing actual CDC'): m.cdc_critical_records(new)
        put(new,cdc(['r/D']).replace('CDC-10 Critical 1','CDC-10 Critical 2'))
        with self.assertRaisesRegex(ValueError,'unparsed/missing'): m.cdc_critical_records(new)

    def test_truncated_summary_cannot_masquerade_as_zero_critical(self):
        p=put(self.root/'cdc','CDC Report\nCDC-3 Info 434 synchronized\n')
        with self.assertRaisesRegex(ValueError,'incomplete summary'):m.cdc_critical_records(p)
        put(p,cdc([]));self.assertEqual(m.cdc_critical_records(p),set())

    def test_actual_route_counts(self):
        p=self.root/'route'; text='\n'.join(f'# of {n} : {v}' for n,v in [('routable nets',100),('fully routed nets',100),('unrouted nets',0),('partially routed nets',0),('nets with routing errors',0)])
        put(p,text); self.assertTrue(m.route_counts(p)['complete'])
        put(p,text.replace('fully routed nets : 100','fully routed nets : 99').replace('unrouted nets : 0','unrouted nets : 1'))
        self.assertFalse(m.route_counts(p)['complete']); put(p,'report exists')
        with self.assertRaisesRegex(ValueError,'missing actual route'): m.route_counts(p)


class Constraints(Temp):
    def setUp(self):
        super().setUp()
        self.report,self.project=self.root/'report',self.root/'project'
        self.xdc=put(self.root/'board.xdc','create_clock')
        self.header='path\tUSED_IN\tUSED_IN_SYNTHESIS\tUSED_IN_IMPLEMENTATION\tIS_ENABLED\tSCOPED_TO_REF\tSCOPED_TO_CELLS\tPROCESSING_ORDER\tSHA256\n'
        self.row=f'{self.xdc}\tsynthesis implementation\t1\t1\t1\tref\tcell\tLATE\tPENDING\n'
        p=patch.dict(os.environ,HAP_PROJECT_DIR=str(self.project),HAP_STAGE='place');p.start();self.addCleanup(p.stop)
        put(self.project/'scalellm_vcu118_f05.runs/impl_1/runme.log',f'Parsing XDC File [{self.xdc}] for cell \'cell\'\n')
        self.registry('project');m.constraint_chain('project',self.report);self.registry('init');m.constraint_chain('init',self.report)

    def registry(self,phase,row=None): put(self.report/f'xdc_registry_{phase}.tsv',self.header+(self.row if row is None else row))

    def test_changed_bytes(self):
        put(self.xdc,'changed clock');self.registry('opt')
        with self.assertRaisesRegex(ValueError,'constraint changed'):m.constraint_chain('opt',self.report)

    def test_changed_scope_used_in(self):
        for before,after in [('\tref\t','\tforeign\t'),('\t1\t1\t1\t','\t1\t0\t1\t')]:
            self.registry('opt',self.row.replace(before,after))
            with self.assertRaisesRegex(ValueError,'scope/order/USED_IN'):m.constraint_chain('opt',self.report)

    def test_missing_metadata(self):
        p=put(self.root/'new.xdc');self.registry('opt',self.row.replace(str(self.xdc),str(p)))
        with self.assertRaisesRegex(ValueError,'XDC missing'):m.constraint_chain('opt',self.report)

    def test_new_constraint_requires_tool_owner(self):
        p=put(self.root/'debug.xdc');self.registry('opt',self.row+self.row.replace(str(self.xdc),str(p)))
        with self.assertRaisesRegex(ValueError,'unclassified new'):m.constraint_chain('opt',self.report)
        put(self.report/'tool_debug_xdc_opt.txt',str(p)+'\n')
        self.assertEqual(len(m.constraint_chain('opt',self.report)['hashes']),2)

    def test_duplicate_registry(self):
        self.registry('opt',self.row+self.row)
        with self.assertRaisesRegex(ValueError,'duplicate XDC'):m.constraint_chain('opt',self.report)


class Provenance(Temp):
    def setUp(self):
        super().setUp(); self.report=self.root/'report';self.source=put(self.root/'scripts/test.tcl','original')
        self.archived=put(self.report/'stage_sources/test.tcl','original')
        manifest(self.report/'stage_inputs.sha256',[self.source]);manifest(self.report/'archived_sources.sha256',[self.archived])
        self.stage,self.archive=m.file_id(self.report/'stage_inputs.sha256'),m.file_id(self.report/'archived_sources.sha256')

    def test_old_archive_allows_live_route_helper_fix(self):
        put(self.source,'new route-only helper')
        m.validate_stage_archive(self.report,self.stage,self.archive)

    def test_parent_archive_tamper(self):
        put(self.archived,'modified evidence')
        with self.assertRaisesRegex(ValueError,'changed input'):m.validate_stage_archive(self.report,self.stage,self.archive)

    def test_old_manifest_tamper(self):
        put(self.report/'stage_inputs.sha256','rewritten')
        with self.assertRaisesRegex(ValueError,'identity changed'):m.validate_stage_archive(self.report,self.stage,self.archive)

    def test_native_checkpoint_tamper(self):
        p=put(self.root/'native.dcp');identity=m.file_id(p);put(p,'changed')
        with self.assertRaisesRegex(ValueError,'identity changed'):m.verify_identity(identity)

    def test_empty_completion_receipt_has_hash(self):
        p=put(self.root/'.vivado.end.rst','');identity=m.artifact_id(p);m.verify_identity(identity)
        self.assertEqual(identity['bytes'],0)


class InheritedConstraints(Temp):
    def setUp(self):
        super().setUp();self.log=put(self.root/'route.log','Restoring checkpoint with embedded constraints\n')
        self.constraints=put(self.root/'constraints_physopt.json','{}\n')
        self.reads=put(self.root/'actual_parent_reads.json','{"records":[{"path":"original.xdc"}]}\n')
        self.evidence=put(self.root/'parent.json',json.dumps({'constraints':m.file_id(self.constraints),'actual_xdc_reads':m.file_id(self.reads)}))
        self.parent={'evidence':m.file_id(self.evidence),'checkpoint':{'path':'frozen_physopt.dcp'}}

    def test_empty_route_reads_can_inherit_validated_parent(self):
        output=self.root/'actual_route.json';m.loaded_constraints(self.log,output,self.parent)
        value=json.loads(output.read_text());self.assertEqual(value['records'],[])
        self.assertEqual(value['inherited']['mode'],'checkpoint_inherited')
        self.assertEqual(value['inherited']['parent_actual_reads'],m.file_id(self.reads))

    def test_inherited_parent_read_evidence_tamper_rejected(self):
        put(self.reads,'tampered')
        with self.assertRaisesRegex(ValueError,'identity changed'):m.loaded_constraints(self.log,self.root/'output',self.parent)


class TclGuards(Temp):
    def test_syntax_and_literal_glob(self):
        code='''set ::env(HAP_REPORT_DIR) /tmp
source {%s}
foreach p [glob {%s/*.tcl}] {
 set h [open $p r];set source [read $h];close $h
 if {![info complete $source]} {error "incomplete Tcl $p"}
}
proc fake {args} {return [lindex $args end]}
puts [m002_exact fake {scope/reg[0]/D}]
''' % (SCRIPTS/'m002_diagnostic_common.tcl',SCRIPTS)
        result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stderr,'')
        self.assertEqual(result.stdout.strip(),'NAME == "scope/reg[0]/D"')

    def test_empty_structure_never_qualifies(self):
        p=put(self.root/'graph','TARGET\tunknown/D\n');result=m.reset_structure(p)
        self.assertFalse(result['qualified']);self.assertGreater(len(result['issues']),10)

    def test_stage_order_and_thread_limit(self):
        text=(SCRIPTS/'m002_diagnostic_common.tcl').read_text();hook=text[text.index('proc m002_post'):text.index('proc hash_file')]
        self.assertLess(hook.index('write_checkpoint'),hook.index('report_timing_summary'))
        self.assertLess(hook.index('report_cdc'),hook.index('hook-batch'))
        self.assertIn('m002_dump_xdc $point',hook);self.assertNotIn('m002_pending_debug_only',text)
        self.assertIn('set_param general.maxThreads 8',(SCRIPTS/'m002_impl_threads.tcl').read_text())

    def test_own_hooks_can_retry_but_foreign_hooks_reject(self):
        text=(SCRIPTS/'m002_physical.tcl').read_text();a=text.index('        set expected_pre');b=text.index('        set_property STEPS.$step.TCL.PRE',a)
        body=text[a:b].replace('            exec python3 [file join $script_dir m002_physical_evidence.py] prior-hooks $step $project_dir','            set provenance_checked 1')
        prefix=f'set script_dir {{{SCRIPTS}}}\nset name init\nset step INIT_DESIGN\n'
        for pre,post,valid in [(str(SCRIPTS/'m002_impl_threads.tcl'),str(SCRIPTS/'m002_diagnostic_init_post.tcl'),True),('/foreign/pre.tcl','',False)]:
            code=prefix+f'set pre {{{pre}}}\nset post {{{post}}}\n'+f'set body {{{body}}}\nputs [catch {{eval $body}} message]\nputs $message\n'
            result=subprocess.run(['tclsh'],input=code,text=True,capture_output=True)
            self.assertEqual(result.stdout.splitlines()[0],'0' if valid else '1',result.stdout)


class ResetStructure(Temp):
    def setUp(self):
        super().setUp();self.rows=[];self.pinrows={};self.cellrows={}
        base='scalellm_vcu118_f05_bd_i/';core='clk_out1_scalellm_vcu118_f05_bd_clk_core_0'
        def pin(name,direction,net,driver='',clock='',refpin=None):
            self.pinrows[name]=f'PIN\t{name}\t{refpin or name.rsplit("/",1)[-1]}\t{direction}\t{net}\t{clock}\t{driver}'
        def cell(name,ref,init='',async_reg=''):
            self.cellrows[name]=f'CELL\t{name}\t{ref}\t{init}\t{async_reg}'
        def logic(name,init,inputs):
            cell(name,'LUT'+str(len(inputs)),f"{2**len(inputs)}'h{init}")
            for i,source in enumerate(inputs):pin(name+f'/I{i}','IN',source,source)
            pin(name+'/O','OUT',name+'/O',name+'/O');return name+'/O'
        cell('VCC','VCC');pin('VCC/P','OUT','VCC/P','VCC/P')
        cell('GND','GND');pin('GND/G','OUT','GND/G','GND/G')
        for gate,clock,modules in [('core_gate',core,['u_base_reset_cdc','u_ready0_cdc','u_ready1_cdc']),
            ('d0_gate','mmcm_clkout0',['u_base_reset_cdc','u_ready_cdc']),('d1_gate','mmcm_clkout0_1',['u_base_reset_cdc','u_ready_cdc'])]:
            for module in modules:
                input_name='base_aresetn' if module=='u_base_reset_cdc' else 'async_ready'+module.removeprefix('u_ready').removesuffix('_cdc')
                source=base+gate+'/inst/'+input_name
                if input_name.startswith('async_ready'):
                    d=(input_name[-1] if gate=='core_gate' else gate[1]);prefix=base+f'ddr4_{d}/inst/'
                    starts=[prefix+'calib_complete_reg/Q',prefix+'div_clk_rst_r1_reg/Q']
                    qualifier=logic(prefix+'ready','2',starts)
                    self.rows.append('GATE_INPUT\t'+source+'\t'+' '.join(starts))
                    pin(source,'IN',qualifier,qualifier)
                else:pin(source,'IN',source)
                # Alias the same synthesized qualifier net for core and DDR gate.
                signal=self.pinrows[source].split('\t')[4]
                inverted=logic(base+gate+'/inst/'+module+'/inv','1',[signal])
                for i in range(4):
                    name=base+gate+'/inst/'+module+f'/arststages_ff_reg[{i}]'
                    cell(name,'FDCE',"1'b1",'TRUE')
                    pin(name+'/C','IN',clock,clock,clock);pin(name+'/CE','IN','VCC/P','VCC/P')
                    pin(name+'/CLR','IN',inverted,inverted)
                    driver='VCC/P' if not i else base+gate+'/inst/'+module+f'/arststages_ff_reg[{i-1}]/Q'
                    pin(name+'/D','IN',driver,driver);pin(name+'/Q','OUT',name+'/Q',name+'/Q')
        for d in (0,1):
            self.rows.append('TARGET\t'+base+f'core_gate/inst/u_ready{d}_cdc/arststages_ff_reg[0]/CLR')
            terms=[base+f'd{d}_gate/inst/{x}/arststages_ff_reg[3]/Q' for x in ('u_base_reset_cdc','u_ready_cdc')]
            for psr in ('psr0','psr_aclk1'):
                root=base+f'd{d}_smc/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX'
                inverted=logic(root+'/input','7',terms)
                for i in range(4):
                    name=root+f'/syncstages_ff_reg[{i}]';cell(name,'FDRE',"1'b0",'TRUE')
                    pin(name+'/C','IN',core,core,core);pin(name+'/CE','IN','VCC/P','VCC/P');pin(name+'/R','IN','GND/G','GND/G')
                    driver=inverted if not i else root+f'/syncstages_ff_reg[{i-1}]/Q'
                    pin(name+'/D','IN',driver,driver);pin(name+'/Q','OUT',name+'/Q',name+'/Q')
                self.rows.append('TARGET\t'+root+'/syncstages_ff_reg[0]/D')
            self.rows.append(f'IO_OUTPUT\tddr4_sdram_c{d+1}_reset_n\t{base}ddr4_{d}/inst/reset_reg/Q')
        self.rows.append('IO_RECEIVER\tpcie_perstn\t'+base+'rst_ddr0/U0/EXT_LPF/ACTIVE_LOW_EXT.ACT_LO_EXT/syncstages_ff_reg[0]/D\tFDRE')
        self.path=self.root/'graph'
        self.write()

    def write(self):put(self.path,'\n'.join(self.rows+list(self.cellrows.values())+list(self.pinrows.values()))+'\n')
    def check(self):return m.reset_structure(self.path)

    def test_complete_primitive_connectivity_and_truth_table_proof(self):
        result=self.check();self.assertTrue(result['qualified'],result['issues'])
        self.assertEqual(len(result['async_reset_chains']),7);self.assertEqual(len(result['aux_chains']),4)

    def test_async_init_cannot_change(self):
        name=next(n for n in self.cellrows if 'arststages_ff_reg[0]' in n)
        self.cellrows[name]=self.cellrows[name].replace("1'b1","1'b0");self.write()
        self.assertFalse(self.check()['qualified'])

    def test_wrong_aux_polarity_cannot_pass(self):
        name=next(n for n in self.cellrows if n.endswith('ACT_LO_AUX/input'))
        self.cellrows[name]=self.cellrows[name].replace("4'h7","4'h8");self.write()
        self.assertFalse(self.check()['qualified'])

    def test_shift_chain_disconnected_cannot_pass(self):
        name=next(n for n in self.pinrows if 'arststages_ff_reg[1]/D' in n)
        self.pinrows[name]='\t'.join(self.pinrows[name].split('\t')[:4]+['GND/G','','GND/G']);self.write()
        self.assertFalse(self.check()['qualified'])

    def test_unknown_pcie_reset_receiver_cannot_pass(self):
        self.rows.append('IO_RECEIVER\tpcie_perstn\tuser_data/reg/D\tFDRE');self.write()
        self.assertFalse(self.check()['qualified'])


class ParentStatus(Temp):
    def setUp(self):
        super().setUp();self.project=self.root/'project';self.report=self.root/'report';self.attempt=self.root/'attempt'
        self.lineage={'project':str(self.project)}
        self.value={'schema':m.SCHEMA,'stage':'place','execution_state':'completed','diagnostic_eligible':True,
                    'project':str(self.project),'physical_signoff':False,'synthesis':self.lineage,'managed_attempt':str(self.attempt)}
        put(self.report/'launcher_status.txt',f'stage=place\nexit_code=0\nnative_exit_code=0\nproject={self.project}\nreports={self.report}\n')
        self.status=dict(stage='place',project=str(self.project),report=str(self.report),exit_code=0,native_exit_code=0,stop_reason=None,owned_survivors=[])
        self.save()

    def save(self):put(self.attempt/'status.json',json.dumps(self.status));put(self.report/'diagnostic_evidence.json',json.dumps(self.value))
    def check(self):return m.parent_place(self.report/'diagnostic_evidence.json',self.project,self.lineage)

    def test_failed_parent_launcher_rejected_before_artifacts(self):
        p=self.report/'launcher_status.txt';put(p,p.read_text().replace('exit_code=0','exit_code=1'))
        with self.assertRaisesRegex(ValueError,'launcher did not actually succeed'):self.check()

    def test_parent_supervisor_survivors_rejected(self):
        self.status['owned_survivors']=[123];self.save()
        with self.assertRaisesRegex(ValueError,'supervisor did not actually finish'):self.check()

    def test_parent_supervisor_failure_rejected(self):
        self.status['exit_code']=1;self.save()
        with self.assertRaisesRegex(ValueError,'supervisor did not actually finish'):self.check()


class RecoveryParent(Temp):
    def setUp(self):
        super().setUp();self.source=self.root/'vivado/reports/failed';self.report=self.root/'vivado/reports/new';self.report.mkdir(parents=True)
        self.project=self.root/'vivado/project/fresh';self.attempt=self.root/'attempt';self.lineage={'project':str(self.project)}
        self.patcher=patch.object(m,'ROOT',self.root);self.patcher.start();self.addCleanup(self.patcher.stop)
        script=put(self.root/'script.tcl','old');archive=put(self.source/'stage_sources/script.tcl','old')
        manifest(self.source/'stage_inputs.sha256',[script]);manifest(self.source/'archived_sources.sha256',[archive])
        put(self.source/'command.json',json.dumps({'managed_attempt':str(self.attempt),'synthesis':self.lineage}))
        self.status={'project':str(self.project),'report':str(self.source),'stage':'place','exit_code':1,'native_exit_code':1,'stop_reason':None,'owned_survivors':[]}
        put(self.attempt/'status.json',json.dumps(self.status))
        put(self.source/'launcher_status.txt',f'exit_code=1\nnative_exit_code=1\nproject={self.project}\n')
        put(self.source/'init_result.txt','completed=0\nphase=init\n')
        dcp=self.source/'init.dcp'
        import zipfile
        xml='<Checkpoint>'+''.join(f'<{k} Name="{v}"/>' for k,v in {'Part':'xcvu9p-flga2104-2L-e','Top':'scalellm_vcu118_f05_bd_wrapper','BoardPart':'xilinx.com:vcu118:part0:2.0','BUILD_NUMBER':'6299465','PRODUCT':'Vivado v2025.2 (64-bit)'}.items())+'</Checkpoint>'
        with zipfile.ZipFile(dcp,'w') as z:z.writestr('dcp.xml',xml)
        self.xdc=put(self.root/'constraints/0.xdc','constraint 0')
        files=[self.xdc]+[put(self.root/f'constraints/{i}.xdc',str(i)) for i in range(1,162)]
        header='path\tUSED_IN\tUSED_IN_SYNTHESIS\tUSED_IN_IMPLEMENTATION\tIS_ENABLED\tSCOPED_TO_REF\tSCOPED_TO_CELLS\tPROCESSING_ORDER\tSHA256\n'
        rows=''.join(f'{p}\tsynthesis implementation\t1\t1\t1\tref\tcell\tLATE\t{m.sha256(p)}\n' for p in files)
        put(self.source/'xdc_registry_project_hashed.tsv',header+rows)
        self.log=put(self.source/'implementation_run.log',f"Parsing XDC File [{self.xdc}] for cell 'scope'\nlink_design completed successfully\nsource m002_diagnostic_init_post.tcl\nThe checkpoint '{dcp}' has been generated\n")
        for name in ('implementation_settings.txt','effective_build_identity.txt','timing_init.rpt','utilization_init.rpt','drc_init.rpt','reset_register_probe_init.tsv'):put(self.source/name)

    def check(self):return m.recovery_parent(self.source,self.project,self.lineage,self.report)

    def test_failed_post_checkpoint_is_valid_inherited_state(self):
        value=self.check();self.assertEqual(value['original_impl_run_remains'],'FAIL');self.assertEqual(len(value['source_metadata']),162)
        self.assertEqual(value['actual_reads'][0]['scope'],'scope')

    def test_prior_success_cannot_replace_failed_post_identity(self):
        self.status['exit_code']=0;put(self.attempt/'status.json',json.dumps(self.status))
        with self.assertRaisesRegex(ValueError,'completed failed'):self.check()

    def test_wrong_phase_or_later_opt_cannot_be_called_init(self):
        put(self.log,self.log.read_text()+'\nCommand: opt_design\n')
        with self.assertRaisesRegex(ValueError,'before-opt'):self.check()

    def test_pre_link_xdc_bytes_are_frozen(self):
        put(self.xdc,'changed constraints')
        with self.assertRaisesRegex(ValueError,'registered XDC changed'):self.check()

    def test_missing_actual_xdc_reads_is_not_inherited_coverage(self):
        put(self.log,'\n'.join(x for x in self.log.read_text().splitlines() if not x.startswith('Parsing XDC')))
        with self.assertRaisesRegex(ValueError,'no original actual XDC'):self.check()

    def test_old_archive_can_survive_new_helper_but_not_evidence_tamper(self):
        put(self.root/'script.tcl','new recovery helper');self.check()
        put(self.source/'stage_sources/script.tcl','tampered old evidence')
        with self.assertRaisesRegex(ValueError,'changed input'):self.check()


class RestoredIdentityGuards(Temp):
    def test_package_foreign_part_rejected(self):
        import zipfile
        p=self.root/'foreign.dcp'
        with zipfile.ZipFile(p,'w') as z:z.writestr('dcp.xml','<Checkpoint><Part Name="foreign"/></Checkpoint>')
        with self.assertRaisesRegex(ValueError,'package part/top/board/tool'):m.checkpoint_package(p)

    def test_display_name_is_recorded_not_compared_to_logical_top(self):
        text=(SCRIPTS/'m002_resume_physical.tcl').read_text()
        self.assertNotIn('[get_property NAME $design] ne',text)
        self.assertIn('actual_project_part=',text);self.assertIn('actual_fileset_top=',text)
        self.assertLess(text.index('restored_design_properties.tsv'),text.index('if {[llength $preflight_issues]}'))
        self.assertLess(text.index('foreach target $::m002_cdc_targets'),text.index('if {[llength $preflight_issues]}'))


if __name__=='__main__': unittest.main()
