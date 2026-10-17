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


def phy_archive(attempt):
    original=attempt/'original_tool_worker'
    archive=attempt/'generated_phy_snapshot'
    files={}
    for d in (0,1):
        module=f'scalellm_vcu118_f05_bd_ddr4_{d}_0_phy'
        for path in (original/(module+'.dcp'),original/'out'/(module+'.0')/'result.dcp',
                     original/'.cache/ip'/str(d)/(module+'.dcp')):files[path]=f'current generated phy {d}'
        files[original/f'phy{d}.xdc']=f'worker constraint {d}'
    files[original/'vivado.log']=''.join(f"DBG: no cache hit, so run synth\nParsing XDC File [{original/f'phy{d}.xdc'}]\nsynth_design completed successfully\n" for d in (0,1))+'Exiting Vivado\n'
    rows=[]
    for source,body in files.items():
        copy=put(archive/source.relative_to(original),body);rows.append({'source_path':str(source),**m.file_id(copy)})
    put(attempt/'generated_phy_evidence.json',json.dumps({'source_root':str(original),'archive_root':str(archive),
        'cache_miss_count':2,'actual_synth_success_count':2,'files':rows}))
    manifest(attempt/'generated_phy_snapshot.sha256',[Path(row['path']) for row in rows])
    return archive


def debug_archive(attempt):
    original=attempt/'original_debug_worker';archive=attempt/'generated_debug_snapshot'
    files={original/'dbg_hub_CV.0/out/get_cs_ip.tcl':f'set ip_vlnv xilinx.com:ip:xsdbm:3.0\nset ip_module_name dbg_hub\nset output_dcp {original}/dbg_hub_CV.0/out/result.dcp\n',
        original/'dbg_hub_CV.0/out/result.dcp':'current generated hub',original/'dbg_hub_CV.0/out/hub.xdc':'generated main hub constraints',
        original/'dc_drv.0/vivado.log':'synth_design completed successfully\nExiting Vivado\n'}
    rows=[]
    for source,body in files.items():
        copy=put(archive/source.relative_to(original),body);rows.append({'source_path':str(source),**m.file_id(copy)})
    put(attempt/'generated_debug_evidence.json',json.dumps({'source_root':str(original),'archive_root':str(archive),'module':'dbg_hub',
        'ipdef':'xilinx.com:ip:xsdbm:3.0','main_core_cell':'dbg_hub_CV','generation_phase':'opt_design_phase_1.1.2',
        'files':rows,'worker_actual_xdc_reads':[],'worker_read_bytes_limit':'fixture has no original worker source-byte claim'}))
    manifest(attempt/'generated_debug_snapshot.sha256',[Path(row['path']) for row in rows])
    return archive


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
        self.registry('opt');m.constraint_chain('opt',self.report)
        p=put(self.root/'debug.xdc');self.registry('debug_materialized',self.row+self.row.replace(str(self.xdc),str(p)))
        with self.assertRaisesRegex(ValueError,'unclassified new'):m.constraint_chain('debug_materialized',self.report)
        put(self.report/'tool_debug_xdc_debug_materialized.txt',str(p)+'\n')
        self.assertEqual(len(m.constraint_chain('debug_materialized',self.report)['hashes']),2)

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
        self.assertLess(hook.index('report_cdc'),hook.rindex('hook-batch'))
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
            extra='\tIS_C_INVERTED=0\tIS_D_INVERTED=0\tIS_CLR_INVERTED=0\tIS_R_INVERTED=0' if ref in {'FDCE','FDRE'} else ''
            self.cellrows[name]=f'CELL\t{name}\t{ref}\t{init}\t{async_reg}'+extra
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
                    starts=[prefix+'calDone_gated_reg/Q',prefix+'div_clk_rst_r1_reg/Q']
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

    def test_bounded_explicit_primitive_exports_resolve_absent_logical_properties(self):
        groups={}
        for name,row in list(self.cellrows.items()):
            f=row.split('\t')
            if f[2] not in {'FDCE','FDRE'}:continue
            root,leaf=name.rsplit('/',1);groups.setdefault(root,[]).append((leaf,f[2],f[3]))
            self.cellrows[name]='\t'.join(f[:5]+[x.split('=')[0]+'=' for x in f[5:]])
        for i,(scope,registers) in enumerate(groups.items()):
            path=self.root/f'reset_block_{i}.v'
            source='module bounded();\n'
            for leaf,ref,init in registers:
                parameters=[('INIT',init),('IS_C_INVERTED',"1'b0"),('IS_D_INVERTED',"1'b0"),
                            ('IS_CLR_INVERTED' if ref=='FDCE' else 'IS_R_INVERTED',"1'b0")]
                source+=ref+' #(\n'+',\n'.join('.'+k+'('+v+')' for k,v in parameters)+') \\'+leaf+' ();\n'
            put(path,source+'endmodule\n');self.rows.append('NETLIST_SCOPE\t'+scope+'\t'+str(path))
        self.write();result=self.check();self.assertTrue(result['qualified'],result['issues'])
        self.assertEqual(len(result['explicit_primitive_exports']),11)
        path=self.root/'reset_block_0.v';put(path,path.read_text().replace(".IS_D_INVERTED(1'b0)",'.UNRECOGNIZED_D(0)',1))
        self.assertFalse(self.check()['qualified'])

    def test_unknown_actual_inversion_cannot_be_assumed_zero(self):
        name=next(n for n in self.cellrows if 'arststages_ff_reg[0]' in n)
        self.cellrows[name]=self.cellrows[name].replace('IS_C_INVERTED=0','IS_C_INVERTED=');self.write()
        self.assertFalse(self.check()['qualified'])
        self.rows.append('PIN_PROPERTY\t'+name+'/C\tIS_INVERTED\t0');self.write()
        self.assertTrue(self.check()['qualified'])

    def test_later_stage_clear_inversion_must_match(self):
        name=next(n for n in self.cellrows if 'arststages_ff_reg[2]' in n)
        self.cellrows[name]=self.cellrows[name].replace('IS_CLR_INVERTED=0','IS_CLR_INVERTED=1');self.write()
        self.assertFalse(self.check()['qualified'])

    def test_effective_reset_semantics_accepts_legal_clear_inversion_folding(self):
        base='scalellm_vcu118_f05_bd_i/'
        for d in (0,1):
            root=base+f'core_gate/inst/u_ready{d}_cdc'
            source=self.pinrows[base+f'core_gate/inst/async_ready{d}'].split('\t')
            for i in range(4):
                cell=root+f'/arststages_ff_reg[{i}]';self.cellrows[cell]=self.cellrows[cell].replace('IS_CLR_INVERTED=0','IS_CLR_INVERTED=1')
                f=self.pinrows[cell+'/CLR'].split('\t');f[4]=source[4];f[6]=source[6];self.pinrows[cell+'/CLR']='\t'.join(f)
        self.write();result=self.check();self.assertTrue(result['qualified'],result['issues'])
        name=base+'ddr4_0/inst/ready';self.cellrows[name]=self.cellrows[name].replace("4'h2","4'h8")
        self.write();self.assertFalse(self.check()['qualified'])

    def add_hosts(self):
        base='scalellm_vcu118_f05_bd_i/';q=base+'xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/Q'
        for psr,clock in (('psr_aclk1','mmcm_clkout0'),('psr0','mmcm_clkout0_1'),('psr_aclk2','mmcm_clkout0_1')):
            root=base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX'
            for i in range(4):
                name=root+f'/syncstages_ff_reg[{i}]'
                self.cellrows[name]=f"CELL\t{name}\tFDRE\t1'b0\tTRUE\tIS_C_INVERTED=0\tIS_D_INVERTED=0\tIS_R_INVERTED=0"
                driver=q if not i else root+f'/syncstages_ff_reg[{i-1}]/Q'
                for terminal,net in [('C',clock),('CE','VCC/P'),('R','GND/G'),('D',driver),('Q',name+'/Q')]:
                    self.pinrows[name+'/'+terminal]=f'PIN\t{name}/{terminal}\t{terminal}\t'+('OUT' if terminal=='Q' else 'IN')+f'\t{net}\t'+(clock if terminal=='C' else '')+f'\t{net}'
            consumer=base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/lpf_asr_reg'
            self.cellrows[consumer]=f"CELL\t{consumer}\tFDRE\t1'b0\tFALSE"
            self.pinrows[consumer+'/C']=f'PIN\t{consumer}/C\tC\tIN\t{clock}\t{clock}\t{clock}'
            driver=root+'/syncstages_ff_reg[3]/Q'
            self.pinrows[consumer+'/D']=f'PIN\t{consumer}/D\tD\tIN\t{driver}\t\t{driver}'
        self.write()

    def test_host_reset_chain_effective_init_clock_and_exact_consumer(self):
        self.add_hosts();value=self.check();self.assertTrue(value['qualified'],value['issues'])
        self.assertEqual(len(value['host_split_reset_chains']),3)
        name=next(n for n in self.cellrows if 'host_split/' in n and 'syncstages_ff_reg[0]' in n)
        self.cellrows[name]=self.cellrows[name].replace("1'b0","1'b1");self.write()
        self.assertFalse(self.check()['qualified'])

    def test_host_reset_wrong_source_polarity_or_consumer_clock_rejects(self):
        self.add_hosts();name=next(n for n in self.pinrows if 'host_split/' in n and 'syncstages_ff_reg[0]/D' in n)
        original=self.pinrows[name];self.pinrows[name]=original.replace('user_reset_reg/Q','foreign/Q');self.write()
        self.assertFalse(self.check()['qualified'])
        self.pinrows[name]=original;name=next(n for n in self.pinrows if 'lpf_asr_reg/C' in n)
        self.pinrows[name]=self.pinrows[name].replace('mmcm_clkout0','foreign_clock');self.write()
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



class DebugMaterialization(Temp):
    def pending(self, phase='opt', foreign=False):
        cell='scalellm_vcu118_f05_bd_i/ddr4_0/inst/u_ddr4_mem_intfc/u_ddr_cal_top/u_ddr_cal/U_XSDB_SLAVE/r'
        if foreign: cell='functional/r'
        timing(self.root/f'check_timing_{phase}.rpt',[cell+'/C'],[cell+'/D'])
        put(self.root/f'debug_proof_{phase}.txt','verified=1\n')
        put(self.root/f'debug_{phase}.tsv','DEBUG_CLOCK_FANOUT\tx\t'+cell+'/C\n')
        return m.check_timing_counts(self.root/f'check_timing_{phase}.rpt')

    def test_only_known_opt_placeholder_can_reach_debug_not_place(self):
        counts=self.pending()
        self.assertEqual(m.phase_coverage('opt',self.root,counts,1,True),'PENDING_TOOL_DEBUG_MATERIALIZATION')
        for phase,restored in [('opt',False),('debug_materialized',True),('place',True)]:
            with self.assertRaisesRegex(ValueError,'before place'):m.phase_coverage(phase,self.root,counts,1,restored)
        with self.assertRaisesRegex(ValueError,'unique actual blackbox'):m.phase_coverage('opt',self.root,counts,2,True)

    def test_foreign_clock_gap_never_reaches_debug(self):
        counts=self.pending(foreign=True)
        with self.assertRaisesRegex(ValueError,'unverified debug'):m.phase_coverage('opt',self.root,counts,1,True)

    def test_actual_hub_frequency_mismatch_is_preserved_and_missing_clock_is_unknown(self):
        path=self.root/'debug.tsv'
        rows=['PROPERTY\tdbg_hub\tC_CLK_INPUT_FREQ_HZ\t300000000','PROPERTY\tdbg_hub\tC_ENABLE_CLK_DIVIDER\tfalse',
              'DEBUG_PIN_CLOCKS\tdbg_hub/clk\tinput_clock']
        for d in (0,1):
            rows += [f'DEBUG_PIN_CLOCKS\tdbg_hub/sl_iport{d}_o[1]\toutput{d}',
                     f'DEBUG_ENDPOINT_CLOCKS\tdbg_hub/sl_iport{d}_o[1]\tddr{d}/r/C\toutput{d}']
        for clock,period in [('input_clock','20'),('output0','3.333'),('output1','3.333')]:
            for key,value in [('PERIOD',period),('MASTER_CLOCK',''),('SOURCE_PINS','source/'+clock),('IS_GENERATED','0'),('WAVEFORM','0 1')]:
                rows.append(f'DEBUG_ACTUAL_CLOCK\t{clock}\t{key}\t{value}')
        put(path,'\n'.join(rows)+'\n');value=m.debug_clock_facts(path)
        self.assertFalse(value['declared_matches_actual_input']);self.assertEqual(value['actual_input_hz'],50000000)
        self.assertFalse(value['relationship_qualified'])
        put(path,'\n'.join(row for row in rows if not row.startswith('DEBUG_PIN_CLOCKS\tdbg_hub/sl_iport1'))+'\n')
        with self.assertRaisesRegex(ValueError,'observations incomplete'):m.debug_clock_facts(path)

    def test_correct_output_ancestry_allows_metadata_frequency_mismatch(self):
        path=self.root/'debug.tsv';put(self.root/'debug_hub_effective_debug_materialized.xdc','actual scoped timing')
        rows=['PROPERTY\tdbg_hub\tC_CLK_INPUT_FREQ_HZ\t300000000','PROPERTY\tdbg_hub\tC_ENABLE_CLK_DIVIDER\tfalse',
              'DEBUG_PIN_CLOCKS\tdbg_hub/clk\tinput_clock']
        for d in (0,1):
            rows += [f'DEBUG_PIN_CLOCKS\tdbg_hub/sl_iport{d}_o[1]\toutput{d}',
                     f'DEBUG_ENDPOINT_CLOCKS\tdbg_hub/sl_iport{d}_o[1]\tddr{d}/r/C\toutput{d}',
                     f'DEBUG_OUTPUT_DRIVER\tdbg_hub/sl_iport{d}_o[1]\tdbg_hub/buf{d}/O\tBUFG\tO',
                     f'DEBUG_OUTPUT_STARTPOINTS\tdbg_hub/sl_iport{d}_o[1]\tdbg_hub/clk']
        for clock in ('input_clock','output0','output1'):
            generated=clock != 'input_clock'
            for key,value in [('PERIOD','20'),('MASTER_CLOCK','input_clock' if generated else ''),
                ('SOURCE_PINS','source/'+clock),('IS_GENERATED','1' if generated else '0'),('WAVEFORM','0 10')]:
                rows.append(f'DEBUG_ACTUAL_CLOCK\t{clock}\t{key}\t{value}')
        put(path,'\n'.join(rows)+'\n');value=m.debug_clock_facts(path)
        self.assertTrue(value['relationship_qualified'],value['relationship_issues']);self.assertFalse(value['declared_matches_actual_input'])
        text=path.read_text().replace('output0','debug/sl_iport0_o[1]')
        text=text.replace('\tdebug/sl_iport0_o[1]\n','\t{debug/sl_iport0_o[1]}\n')
        put(path,text);self.assertTrue(m.debug_clock_facts(path)['relationship_qualified'])
        put(path,path.read_text().replace('output1\tPERIOD\t20','output1\tPERIOD\t3.333'))
        self.assertFalse(m.debug_clock_facts(path)['relationship_qualified'])

    def test_independent_gate_failures_are_all_saved_before_verdict(self):
        from contextlib import ExitStack
        put(self.root/'debug_materialized_result.txt','blackboxes=0\n')
        constraint=put(self.root/'constraints_debug_materialized.json','{}')
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,HAP_PROJECT_DIR=str(self.root),HAP_SYNTH_REPORT_DIR=str(self.root),
                HAP_SYNTH_ATTEMPT_DIR=str(self.root),HAP_EXECUTION_MODE='checkpoint_restored_commands'))
            for name,value in [('synth_lineage',{}),('input_manifest',{}),('constraint_chain',{}),('check_timing_counts',{}),
                ('phase_coverage','COMPLETE_INTERNAL'),('reset_io_coverage',{}),('utilization_metrics',{}),
                ('reset_structure',{'qualified':False,'issues':['actual reset unknown']}),
                ('debug_clock_facts',{'relationship_qualified':False,'relationship_issues':['independent wrong 3.333ns']})]:
                stack.enter_context(patch.object(m,name,return_value=value))
            stack.enter_context(patch.object(m,'critical_coverage',side_effect=ValueError('unknown critical CDC')))
            with self.assertRaisesRegex(ValueError,'conditions not established'):m.hook_batch('debug_materialized',self.root)
        result=json.loads((self.root/'integrity_debug_materialized.json').read_text())
        self.assertEqual(len(result['gate_issues']),3)
        self.assertFalse(result['reset_structure']['qualified']);self.assertFalse(result['debug_clock_observation']['relationship_qualified'])
        self.assertFalse((self.root/'admission_debug_materialized.txt').exists())

    def test_native_debug_step_precedes_strict_pre_place_gate(self):
        text=(SCRIPTS/'m002_resume_physical.tcl').read_text()
        start=text.index('    m002_post opt\n')
        flow=text[start:]
        ordered=['get_debug_cores -quiet','m002_command debug_materialization implement_debug_core',
                 'm002_post debug_materialized','pre-place debug_materialized','m002_command place place_design']
        self.assertEqual([flow.index(x) for x in ordered],sorted(flow.index(x) for x in ordered))
        self.assertIn('post_opt_pre_debug',text)

    def test_recovered_opt_never_repeats_opt_or_places_before_admission(self):
        text=(SCRIPTS/'m002_resume_physical.tcl').read_text()
        flow=text[text.index('if {$stage eq "place"} {'):text.index('m002_put [file join $report_dir implementation_checkpoint.sha256]')]
        for deny in (0,1):
            prefix=f'''set stage place
set ::env(HAP_RECOVERY_PHASE) post_opt_pre_debug
set report_dir {{{self.root}}}
set script_dir /fixture
set sequence {{}}
set deny {deny}
proc m002_put {{args}} {{}}
proc m002_post {{point}} {{
 lappend ::sequence post_$point
 if {{$point eq "opt"}} {{set h [open [file join $::report_dir opt_result.txt] w];puts $h "completed=1\ndebug_materialization_eligible=1";close $h}}
}}
proc m002_command {{point args}} {{lappend ::sequence $point}}
proc get_debug_cores {{args}} {{return {{dbg_hub mig0 mig1}}}}
proc exec {{args}} {{lappend ::sequence pre_place;if {{$::deny}} {{error "strict admission failed"}}}}
'''
            result=subprocess.run(['tclsh'],input=prefix+'set rc [catch {\n'+flow+'\n} issue]\nputs $rc\nputs $sequence\n',text=True,capture_output=True)
            lines=result.stdout.splitlines();self.assertEqual(lines[0],str(deny),result.stdout+result.stderr)
            sequence=lines[1].split();self.assertNotIn('opt',sequence)
            if deny:self.assertNotIn('place',sequence)
            else:self.assertLess(sequence.index('pre_place'),sequence.index('place'))

    def preplace(self):
        timing(self.root/'check_timing_debug_materialized.rpt')
        put(self.root/'debug_materialized.dcp','actual post-debug fixture')
        put(self.root/'debug_materialization_condition.txt','debug_core_count=3\ncondition=actual_get_debug_cores_nonempty\n')
        put(self.root/'debug_materialization_command_result.txt','phase=debug_materialization\ncommand=implement_debug_core\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n')
        put(self.root/'debug_materialized_result.txt','phase=debug_materialized\ncompleted=1\ndiagnostic_eligible=1\nblackboxes=0\nclock_coverage=COMPLETE_INTERNAL\n')
        put(self.root/'admission_debug_materialized.txt','clock_coverage COMPLETE_INTERNAL\ndiagnostic_eligible 1\n')
        constraint=put(self.root/'constraints_debug_materialized.json',json.dumps({'hashes':{}}))
        graph=put(self.root/'reset_graph_debug_materialized.tsv','actual reset proof fixture')
        debug=put(self.root/'debug_debug_materialized.tsv','actual hub clock proof fixture')
        effective=put(self.root/'debug_hub_effective_debug_materialized.xdc','actual scoped timing fixture')
        put(self.root/'integrity_debug_materialized.json',json.dumps({'phase':'debug_materialized',
            'constraints':m.file_id(constraint),'cdc_classification':{'new_critical':0},'reset_structure':{'qualified':True,'source':m.file_id(graph)},'debug_clock_observation':{'source':m.file_id(debug),'relationship_qualified':True,'effective_hub_constraints':m.file_id(effective)}}))
        return m.pre_place_evidence(self.root,create=True)

    def test_pre_place_binds_actual_debug_command_and_dcp(self):
        self.preplace();m.pre_place_evidence(self.root)
        put(self.root/'debug_materialization_command_result.txt','phase=debug_materialization\ncommand=opt_design\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n')
        with self.assertRaisesRegex(ValueError,'command did not actually complete'):m.pre_place_evidence(self.root)

    def test_nonempty_but_wrong_output_clock_never_admits_place(self):
        self.preplace();p=self.root/'integrity_debug_materialized.json';value=json.loads(p.read_text())
        value['debug_clock_observation']['relationship_qualified']=False;put(p,json.dumps(value))
        with self.assertRaisesRegex(ValueError,'clock relationship unresolved'):m.pre_place_evidence(self.root)

    def test_post_debug_unknown_gap_or_reset_proof_blocks(self):
        self.preplace()
        timing(self.root/'check_timing_debug_materialized.rpt',['functional/C'])
        with self.assertRaisesRegex(ValueError,'internal timing coverage'):m.pre_place_evidence(self.root)
        timing(self.root/'check_timing_debug_materialized.rpt')
        p=self.root/'integrity_debug_materialized.json';v=json.loads(p.read_text());v['reset_structure']['qualified']=False;put(p,json.dumps(v))
        with self.assertRaisesRegex(ValueError,'reset structure'):m.pre_place_evidence(self.root)

    def test_no_pre_place_receipt_can_be_created_after_place(self):
        self.preplace();put(self.root/'place_command_result.txt')
        with self.assertRaisesRegex(ValueError,'after placement'):m.pre_place_evidence(self.root,create=True)

    def test_retained_debug_constraint_survives_tool_temporary_cleanup(self):
        source=put(self.root/'tool_temporary/debug.xdc','real constraint bytes')
        hashes={str(source):m.sha256(source)}
        retained=m.retain_debug_sources(self.root,hashes,{str(source):['full metadata']},{})
        source.unlink();value={'hashes':hashes,'source_archives':retained}
        copy=m.constraint_source(str(source),value);self.assertEqual(copy.read_text(),'real constraint bytes')
        put(copy,'tamper')
        with self.assertRaisesRegex(ValueError,'identity changed'):m.constraint_source(str(source),value)


class OptRecoveryParent(Temp):
    def setUp(self):
        fixture=RecoveryParent();fixture.setUp();self.addCleanup(fixture.doCleanups)
        for name in ('root','source','report','project','attempt','lineage'):setattr(self,name,getattr(fixture,name))
        original=m.recovery_parent(self.source,self.project,self.lineage,self.report)
        original_source=self.source
        self.source=self.root/'vivado/reports/post_opt';self.report=self.root/'vivado/reports/after_opt'
        self.report.mkdir(parents=True)
        self.opt_attempt=self.root/'opt_attempt'
        put(self.source/'recovery_parent.json',json.dumps(original))
        script=self.root/'script.tcl';archive=put(self.source/'stage_sources/script.tcl','old')
        manifest(self.source/'stage_inputs.sha256',[script,self.source/'recovery_parent.json'])
        manifest(self.source/'archived_sources.sha256',[archive])
        put(self.source/'command.json',json.dumps({'managed_attempt':str(self.opt_attempt),'synthesis':self.lineage,
             'stage':'place','execution_mode':'checkpoint_restored_commands'}))
        put(self.opt_attempt/'status.json',json.dumps({'project':str(self.project),'report':str(self.source),'stage':'place',
            'exit_code':1,'native_exit_code':1,'stop_reason':None,'owned_survivors':[]}))
        put(self.source/'launcher_status.txt',f'exit_code=1\nnative_exit_code=1\nproject={self.project}\n')
        import shutil
        shutil.copy2(original_source/'init.dcp',self.source/'opt.dcp')
        self.log=put(self.source/'implementation_run.log',f"Command: opt_design\nThe checkpoint '{self.source/'opt.dcp'}' has been generated\n")
        put(self.source/'opt_command_result.txt','phase=opt\ncommand=opt_design\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n')
        put(self.source/'opt_result.txt','completed=0\nphase=opt\nblackboxes=0\n')
        put(self.source/'constraints_opt.json',json.dumps({'phase':'opt','mode':'embedded_checkpoint_inherited',
            'hashes':original['hashes'],'candidate_metadata':original['source_metadata']}))
        put(self.source/'integrity_opt.json',json.dumps({'phase':'opt','synthesis':self.lineage,
            'constraints':m.file_id(self.source/'constraints_opt.json'),
            'gate_issues':['critical_CDC: ValueError: new/unclassified critical CDC path']}))
        timing(self.source/'check_timing_opt.rpt')
        phy_archive(self.opt_attempt);debug_archive(self.opt_attempt)
        for name in ('implementation_settings.txt','timing_opt.rpt','utilization_opt.rpt','drc_opt.rpt','clocks_opt.rpt',
            'cdc_opt.rpt','clock_interaction_opt.rpt','exceptions_opt.rpt','pulse_width_opt.rpt','bus_skew_opt.rpt',
            'reset_cdc_and_io_probe_opt.tsv','xpm_invalid_endpoint_probe_opt.tsv','head_wave_local_opt.tsv','reset_graph_opt.tsv'):put(self.source/name)

    def check(self):return m.recovery_opt_parent(self.source,self.project,self.lineage,self.report)

    def test_exact_opt_dcp_retains_failed_parent_and_original_init_lineage(self):
        value=self.check();self.assertEqual(value['phase'],'post_opt_pre_debug')
        self.assertEqual(value['original_execution_state'],'failed_opt_post_gate');self.assertEqual(len(value['source_metadata']),162)

    def continuation(self):
        import shutil
        upstream=self.check();original=self.source;self.source=self.report
        shutil.copytree(original,self.source,dirs_exist_ok=True)
        put(self.source/'recovery_parent.json',json.dumps(upstream))
        self.report=self.root/'vivado/reports/next_opt';self.report.mkdir(parents=True)
        self.opt_attempt=self.root/'continued_attempt'
        put(self.source/'command.json',json.dumps({'managed_attempt':str(self.opt_attempt),'synthesis':self.lineage,
            'stage':'place','execution_mode':'checkpoint_restored_commands','environment':{'HAP_OPT_REPORT_DIR':str(original)}}))
        put(self.opt_attempt/'status.json',json.dumps({'project':str(self.project),'report':str(self.source),'stage':'place',
            'exit_code':1,'native_exit_code':1,'stop_reason':None,'owned_survivors':[]}))
        put(self.source/'implementation_run.log',f"Command: open_checkpoint {upstream['checkpoint']['path']}\nThe checkpoint '{self.source/'opt.dcp'}' has been generated\n")
        put(self.source/'integrity_opt.json',json.dumps({'phase':'opt','synthesis':self.lineage,
            'constraints':m.file_id(self.source/'constraints_opt.json'),'gate_issues':['critical_CDC: ValueError: new/unclassified critical CDC path']}))
        manifest(self.source/'stage_inputs.sha256',[self.root/'script.tcl',self.source/'recovery_parent.json'])
        manifest(self.source/'archived_sources.sha256',[self.source/'stage_sources/script.tcl'])
        return upstream

    def test_continued_same_opt_reuses_only_completed_identity_bound_reports(self):
        self.continuation();value=self.check()
        self.assertTrue(value['opt_evidence_complete']);self.assertEqual(len(value['inherited_reports']),14)
        self.assertEqual(value['completed_report_integrity'],m.file_id(self.source/'integrity_opt.json'))
        self.assertEqual(value['generated_phy']['evidence']['path'],str(self.root/'opt_attempt/generated_phy_evidence.json'))

    def test_continuation_foreign_ancestor_or_changed_opt_receipt_is_rejected(self):
        self.continuation();p=self.source/'recovery_parent.json';original=p.read_text();value=json.loads(original)
        value['opt_command']['sha256']='0'*64;put(p,json.dumps(value))
        manifest(self.source/'stage_inputs.sha256',[self.root/'script.tcl',p])
        with self.assertRaisesRegex(ValueError,'upstream identity changed'):self.check()
        put(p,original);manifest(self.source/'stage_inputs.sha256',[self.root/'script.tcl',p])
        put(self.source/'opt_command_result.txt','phase=opt\ncommand=opt_design\nnative_tcl_code=0\nstarted_epoch=5\nended_epoch=6\n')
        with self.assertRaisesRegex(ValueError,'inherited OPT command receipt changed'):self.check()

    def test_continuation_missing_report_or_false_opt_rerun_never_reuses_reports(self):
        self.continuation();p=self.source/'cdc_opt.rpt';original=p.read_text();put(p,'')
        with self.assertRaisesRegex(ValueError,'completed report missing'):self.check()
        put(p,original);p=self.source/'implementation_run.log';put(p,'Command: opt_design\n'+p.read_text())
        with self.assertRaisesRegex(ValueError,'post_opt_pre_debug'):self.check()

    def test_opt_native_failure_or_later_debug_cannot_resume_as_opt(self):
        receipt=self.source/'opt_command_result.txt';old=receipt.read_text();put(receipt,old.replace('native_tcl_code=0','native_tcl_code=1'))
        with self.assertRaisesRegex(ValueError,'completed opt_design'):self.check()
        put(receipt,old);put(self.log,self.log.read_text()+'Command: implement_debug_core\n')
        with self.assertRaisesRegex(ValueError,'post_opt_pre_debug'):self.check()

    def controlled(self):
        status=json.loads((self.opt_attempt/'status.json').read_text())
        status.update(exit_code=125,native_exit_code=-15,stop_reason='supervisor_exception:KeyboardInterrupt:signal 15',
            supervisor_pid=123,leader_pid=124,owned_survivors=[124],ended_utc='2026-10-15T05:30:21+00:00')
        put(self.opt_attempt/'status.json',json.dumps(status));(self.source/'launcher_status.txt').unlink()
        constraints=json.loads((self.source/'constraints_opt.json').read_text());constraints['phase']='init'
        put(self.source/'constraints_init.json',json.dumps(constraints));(self.source/'constraints_opt.json').unlink()
        proof={name:m.file_id(self.source/name) for name in ('opt_command_result.txt','opt.dcp','opt_result.txt','check_timing_opt.rpt','clocks_opt.rpt')}
        put(self.opt_attempt/'controlled_stop_request.json',json.dumps({'reason':'missing_explicit_pre_place_debug_implementation',
            'supervisor_pid':123,'leader_pid':124,'leader_identity':{'start_ticks':20},'report':str(self.source),'opt_proof':proof}))
        put(self.opt_attempt/'resources.jsonl',json.dumps({'processes':{'124':{'start_ticks':20},'125':{'start_ticks':21}}})+'\n')
        put(self.source/'vivado.log',self.log.read_text())
        self.reap_path=put(self.opt_attempt/'post_termination_verification.json',json.dumps({
            'original_status':m.file_id(self.opt_attempt/'status.json'),'original_status_preserved':True,
            'original_reported_survivors':[124],'leader_pid':124,'supervisor_pid':123,'owned_survivors_after_reap':[],
            'observed_utc':'2026-10-15T05:31:32+00:00','tracked_pid_count':2,
            'checks':[{'pid':124,'expected_start_ticks':20,'state':'not_present'},
                      {'pid':125,'expected_start_ticks':21,'state':'not_present'}],
            'log_freeze':{**m.file_id(self.log),'source':str(self.source/'vivado.log')}}))

    def test_bounded_intentional_stop_preserves_real_125_and_recollects_opt_reports(self):
        self.controlled()
        value=self.check();self.assertEqual(value['original_execution_state'],'intentional_stop_after_opt_before_place')
        self.assertFalse(value['opt_evidence_complete']);self.assertEqual(value['inherited_reports'],{});self.assertIsNone(value['launcher'])
        self.assertEqual(value['post_termination'],m.file_id(self.reap_path))
        self.assertEqual(json.loads((self.opt_attempt/'status.json').read_text())['owned_survivors'],[124])
        put(self.source/'clocks_opt.rpt','tampered after bounded stop')
        with self.assertRaisesRegex(ValueError,'identity changed'):self.check()

    def test_controlled_stop_missing_or_status_tampered_reap_proof_is_rejected(self):
        self.controlled();original=self.reap_path.read_text();self.reap_path.unlink()
        with self.assertRaisesRegex(ValueError,'lacks post-reap'):self.check()
        value=json.loads(original);value['original_status']['sha256']='0'*64;put(self.reap_path,json.dumps(value))
        with self.assertRaisesRegex(ValueError,'post-reap status/survivor'):self.check()

    def test_controlled_stop_incomplete_pid_scope_or_frozen_log_is_rejected(self):
        self.controlled();original=self.reap_path.read_text();value=json.loads(original)
        value['checks']=value['checks'][:1];put(self.reap_path,json.dumps(value))
        with self.assertRaisesRegex(ValueError,'exact tracked PID'):self.check()
        put(self.reap_path,original);put(self.log,'modified after external freeze')
        with self.assertRaisesRegex(ValueError,'identity changed'):self.check()

    def test_forged_absence_receipt_cannot_hide_a_live_pid_identity(self):
        self.controlled();pid=os.getpid();raw=Path(f'/proc/{pid}/stat').read_text()
        ticks=int(raw[raw.rindex(')')+2:].split()[19])
        value=json.loads(self.reap_path.read_text());value['tracked_pid_count']+=1
        value['checks'].append({'pid':pid,'expected_start_ticks':ticks,'state':'not_present'})
        put(self.reap_path,json.dumps(value));p=self.opt_attempt/'resources.jsonl';sample=json.loads(p.read_text())
        sample['processes'][str(pid)]={'start_ticks':ticks};put(p,json.dumps(sample)+'\n')
        with self.assertRaisesRegex(ValueError,'owned PID identity still present'):self.check()

    def test_failed_opt_state_cannot_be_rewritten_success(self):
        put(self.source/'opt_result.txt','completed=1\nphase=opt\nblackboxes=0\n')
        with self.assertRaisesRegex(ValueError,'failure must remain'):self.check()


class PhyRuntimeEvidence(Temp):
    def test_generated_hub_owner_is_exact_and_retained(self):
        debug_archive(self.root);value=m.generated_debug_parent(self.root)
        self.assertEqual(value['ownership']['module'],'dbg_hub')
        p=self.root/'generated_debug_evidence.json';v=json.loads(p.read_text());v['module']='foreign_hub';put(p,json.dumps(v))
        with self.assertRaisesRegex(ValueError,'foreign generated debug'):m.generated_debug_parent(self.root)

    def test_current_phy_generation_and_two_worker_reads_are_bound(self):
        phy_archive(self.root);value=m.generated_phy_parent(self.root)
        self.assertEqual(len(value['worker_actual_xdc_reads']),2);self.assertEqual(len(value['outputs']),2)

    def test_archived_worker_constraint_or_log_tamper_is_rejected(self):
        archive=phy_archive(self.root);put(archive/'phy0.xdc','modified')
        with self.assertRaisesRegex(ValueError,'changed input'):m.generated_phy_parent(self.root)


class RecoveryDebugConstraints(Temp):
    def setUp(self):
        fixture=Constraints();fixture.setUp();self.addCleanup(fixture.doCleanups)
        for name in ('root','report','project','xdc','header','row'):setattr(self,name,getattr(fixture,name))
        old=json.loads((self.report/'constraints_init.json').read_text())
        put(self.report/'recovery_parent.json',json.dumps({'source_metadata':old['metadata'],'hashes':old['hashes']}))
        self.env=patch.dict(os.environ,HAP_EXECUTION_MODE='checkpoint_restored_commands');self.env.start();self.addCleanup(self.env.stop)
        self.registry('opt');m.constraint_chain('opt',self.report)
        self.debug=put(self.root/'generated_debug.xdc','real debug constraint')

    def registry(self,phase):put(self.report/f'xdc_registry_{phase}.tsv',self.header+self.row)

    def tool(self,phase):
        self.registry(phase)
        put(self.report/f'tool_debug_xdc_{phase}.txt',str(self.debug)+'\n')
        put(self.report/f'tool_debug_xdc_ownership_{phase}.tsv',f'dbg_hub\txilinx.com:ip:dbg_hub:3.0\t{self.debug}\n')
        put(self.report/f'tool_debug_registry_{phase}.tsv',self.header+self.row.replace(str(self.xdc),str(self.debug)))

    def command(self):
        put(self.report/'debug_materialization_condition.txt','debug_core_count=3\ncondition=actual_get_debug_cores_nonempty\n')
        put(self.report/'debug_materialization_command_result.txt','phase=debug_materialization\ncommand=implement_debug_core\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n')

    def test_new_debug_constraints_require_actual_materialization_not_opt(self):
        self.tool('opt')
        with self.assertRaisesRegex(ValueError,'outside actual debug materialization'):m.constraint_chain('opt',self.report)
        self.tool('debug_materialized');self.command()
        value=m.constraint_chain('debug_materialized',self.report)
        self.assertIn(str(self.debug),value['source_archives'])
        self.debug.unlink();self.tool('place')
        after=m.constraint_chain('place',self.report)
        self.assertEqual(after['source_archives'],value['source_archives'])

    def test_tool_owner_scope_and_native_command_are_required(self):
        self.tool('debug_materialized');self.command()
        put(self.report/'tool_debug_xdc_ownership_debug_materialized.tsv',f'foreign\txilinx.com:ip:other:1.0\t{self.debug}\n')
        with self.assertRaisesRegex(ValueError,'invalid actual debug XDC owner'):m.constraint_chain('debug_materialized',self.report)
        self.tool('debug_materialized');put(self.report/'debug_materialization_command_result.txt','phase=debug_materialization\ncommand=opt_design\nnative_tcl_code=0\nstarted_epoch=1\nended_epoch=2\n')
        with self.assertRaisesRegex(ValueError,'command did not actually complete'):m.constraint_chain('debug_materialized',self.report)


if __name__=='__main__': unittest.main()




class OptResetCdcAdmission(Temp):
    def setUp(self):
        super().setUp();self.rows=[];self.base='scalellm_vcu118_f05_bd_i/'
        self.user=self.base+'xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/Q'
        self.rows.append(f'SOURCE_Q\t{self.user[:-2]}/C\t{self.user}\tC_CLOCKS=xdma_0_axi_aclk')
        user=[]
        for d,psrs in ((0,('psr_aclk1',)),(1,('psr0','psr_aclk2'))):
            clock='mmcm_clkout0'+('_1' if d else '')
            user.extend((self.base+f'd{d}_gate/inst/u_base_reset_cdc/arststages_ff_reg[{i}]/CLR','FDCE',clock) for i in range(4))
            for psr in psrs:
                scope=self.base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/'
                user.append((scope+'ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D','FDRE',clock))
                q=scope+'ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[3]/Q'
                self.fanout('HOST_RESET_Q',q,[(scope+'lpf_asr_reg/D','FDRE',clock)])
            q=self.base+f'd{d}_gate/inst/u_base_reset_cdc/arststages_ff_reg[3]/Q'
            targets=[(self.base+f'd{d}_smc/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D','FDRE','clk_out1_scalellm_vcu118_f05_bd_clk_core_0') for psr in ('psr0','psr_aclk1')]
            self.fanout('BASE_RESET_Q',q,targets)
        self.fanout('SOURCE_Q',self.user,user);self.path=put(self.root/'fanout.tsv','\n'.join(self.rows)+'\n')

    def fanout(self,kind,q,entries):
        self.rows.append(f'{kind}_FANOUT_COUNT\t{q}\t{len(entries)}\tLIMIT=8192')
        self.rows.extend(f'{kind}_ENDPOINT\t{q}\t{name}\t{ref}\tCLOCKS={clock}' for name,ref,clock in entries)

    def test_exact_same_ui_members_and_three_local_consumers_qualify(self):
        value=m.reset_fanout(self.path);self.assertTrue(value['qualified'],value['issues'])
        self.assertEqual({k:len(v) for k,v in value['xdma_ui_branches'].items()},{'mmcm_clkout0':5,'mmcm_clkout0_1':6})

    def test_extra_async_direct_consumer_wrong_clock_or_missing_scope_blocks(self):
        original=self.path.read_text();put(self.path,original.replace('lpf_asr_reg/D','other_data_reg/D',1))
        self.assertFalse(m.reset_fanout(self.path)['qualified'])
        put(self.path,original.replace('CLOCKS=mmcm_clkout0\n','CLOCKS=unrelated_clock\n',1))
        self.assertFalse(m.reset_fanout(self.path)['qualified'])
        put(self.path,original.replace('d0_smc/inst/clk_map/psr0','foreign/inst/clk_map/psr0',1))
        self.assertFalse(m.reset_fanout(self.path)['qualified'])
        put(self.path,original.replace('SOURCE_Q_FANOUT_COUNT\t'+self.user+'\t11','SOURCE_Q_FANOUT_COUNT\t'+self.user+'\t12'))
        with self.assertRaisesRegex(ValueError,'incomplete actual reset fanout'):m.reset_fanout(self.path)

    def test_exact_eight_rows_need_all_bounded_proofs_and_keep_formal_open(self):
        import shutil
        reference=self.root/'vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/cdc_opt.rpt'
        reference.parent.mkdir(parents=True);shutil.copy2(SCRIPTS.parent/'reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/cdc_opt.rpt',reference)
        report=self.root/'actual_cdc.rpt';shutil.copy2(reference,report)
        original=SCRIPTS.parent/'reports/m002_E002_R001_AT002_fresh_synth/cdc_post_synth.rpt'
        structure={'qualified':True,'host_split_reset_chains':[{}]*3,'async_reset_chains':[{}]*7,'aux_chains':[{}]*4,
                   'explicit_primitive_exports':[{}]*14,'source':m.file_id(put(self.root/'actual_graph.tsv'))}
        fanout=m.reset_fanout(self.path)
        with self.assertRaisesRegex(ValueError,'actual chain/polarity'):m.critical_coverage(report,original)
        value=m.critical_coverage(report,original,structure,fanout)
        self.assertEqual(value['classification'],'classified_reset_cdc_diagnostic_only');self.assertEqual(value['formal_reset_cdc_safety'],'OPEN')
        self.assertEqual(value['changed_vs_synthesis'],4);self.assertEqual(value['remaining_original_identities'],4)
        m.verify_cdc_proof(value)
        structure['host_split_reset_chains']=[]
        with self.assertRaisesRegex(ValueError,'actual chain/polarity'):m.critical_coverage(report,original,structure,fanout)
        structure['host_split_reset_chains']=[{}]*3
        put(report,report.read_text().replace('calDone_gated_reg/C','foreign_source_reg/C',1))
        with self.assertRaisesRegex(ValueError,'new/unclassified'):m.critical_coverage(report,original,structure,fanout)
