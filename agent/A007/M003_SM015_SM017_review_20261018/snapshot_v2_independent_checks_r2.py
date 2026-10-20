from pathlib import Path
import ast,copy,datetime,hashlib,io,json,os,subprocess,sys,types,unittest
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
HW=ROOT/'project/hardware'
OUT=ROOT/'agent/A007/M003_SM015_SM017_review_20261018'
CAND=ROOT/'project/E011_m003_joint_routability_implementation/experiment_source/R002_native_entry_fix/snapshot_collection_serialization_v1'
TEMP=OUT/'snapshot_v2_r2_cpu_tmp'
TEMP.mkdir(exist_ok=True)
os.environ['TMPDIR']=str(TEMP)
os.environ.pop('HAP_M003_SCRIPTS_DIR',None)
def ident(p):
    p=Path(p); b=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
assemblies={}
for version,suffix in [('before','.before'),('v2','.proposed.v2')]:
    base=OUT/('snapshot_v2_r2_'+version+'_fixture')/'vivado'
    (base/'scripts').mkdir(parents=True,exist_ok=True)
    (base/'constraints').mkdir(exist_ok=True)
    pairs=[(CAND/('m003_joint_checks.tcl'+suffix),base/'scripts/m003_joint_checks.tcl'),
           (HW/'vivado/scripts/m003_system_python.tcl',base/'scripts/m003_system_python.tcl'),
           (HW/'vivado/constraints/m003_joint_locality_data.tcl',base/'constraints/m003_joint_locality_data.tcl')]
    assemblies[version]=[]
    for source,dest in pairs:
        dest.write_bytes(source.read_bytes())
        a,b=ident(source),ident(dest); assert a['sha256']==b['sha256']
        assemblies[version].append(dict(source=a,copy=b))
SOURCE=OUT/'snapshot_v2_r2_v2_fixture/vivado/scripts/m003_joint_checks.tcl'
OLD_SOURCE=OUT/'snapshot_v2_r2_before_fixture/vivado/scripts/m003_joint_checks.tcl'
sys.path.insert(0,str(HW))
module=types.ModuleType('a007_snapshot_v2_r2_candidate')
module.__file__=str(HW/'tests/test_m003_native_entry_repair.py')
sys.modules[module.__name__]=module
testfile=CAND/'test_m003_native_entry_repair.py.proposed.v2'
exec(compile(testfile.read_text(),str(testfile),'exec'),module.__dict__)
module.SnapshotCollections.SOURCE=SOURCE
from tests import test_m003_joint_qualification as q

def tcl(body, source=SOURCE):
    code='source {'+str(source)+'}\n'+body
    wrapped='if {[catch {\n'+code+'\n} message options]} {puts stderr [dict get $options -errorinfo];exit 1}\n'
    result=subprocess.run(['tclsh'],input=wrapped,text=True,capture_output=True,cwd=HW)
    return result
class IndependentChecks(unittest.TestCase):
    def test_all_selected_roles_reject_empty_pblocks_but_original_core_allows(self):
        baseline=q.fixture()
        for row in baseline['cells']:
            if row['role']=='core_address': row['PBLOCKS']=''
        self.assertTrue(q.E.validate(baseline,q.SPEC,fixture=True)['passed'])
        messages={'buffer':'M2 region binding absent','payload':'M2 region binding absent',
                  'address':'address cone pblock absent','address_logic':'address cone pblock absent',
                  'memory':'URAM pool binding absent','c01':'C01 hard-SLR2 binding missing'}
        for role,message in messages.items():
            with self.subTest(role=role):
                changed=copy.deepcopy(baseline)
                next(row for row in changed['cells'] if row['role']==role)['PBLOCKS']=''
                result=q.E.validate(changed,q.SPEC,fixture=True)
                self.assertFalse(result['passed'])
                self.assertTrue(any(message in e for e in result['errors']),result['errors'])
    def test_wrapper_exclusive_trace_collision_retains_original_error_options(self):
        destination=TEMP/'collision'
        destination.mkdir(exist_ok=True)
        body='set destination {'+str(destination)+'}\n'+r'''
rename m003::snapshot_body m003::original_snapshot_body
proc m003::snapshot_body {phase out} {return -code error -errorcode {REVIEW NATIVE 55} {original sentinel}}
set path [file join $destination m003_snapshot_synth_[pid]_error_info.txt]
set h [open $path w];puts -nonewline $h immutable_prior_evidence;close $h
set code [catch {m003::snapshot synth $destination} message options]
set h [open $path];set kept [read $h];close $h
puts [list $code [expr {$message eq {original sentinel}}] [expr {[dict get $options -errorcode] eq {REVIEW NATIVE 55}}] [expr {$kept eq {immutable_prior_evidence}}] [string match {*snapshot_body*} [dict get $options -errorinfo]]]
'''
        result=tcl(body)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'1 1 1 1 1')
        self.assertIn('trace preservation failed',result.stderr)
    def test_nonempty_helper_preserves_native_errorcode_and_empty_is_canonical(self):
        result=tcl(r'''
proc get_property {property objects} {return -code error -errorcode {REVIEW PROPERTY BAD} native_failure}
set code [catch {m003::collection_property NAME {object}} message options]
puts [list $code [expr {[dict get $options -errorcode] eq {REVIEW PROPERTY BAD}}] [expr {$message eq {native_failure}}] [string length [m003::collection_property NAME " \t "]]]
''')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.strip(),'1 1 1 0')
    def test_exact_memory_expression_preserves_nonaddress_and_address_semantics(self):
        old=OLD_SOURCE.read_text()
        new=SOURCE.read_text()
        oldline=next(s.strip() for s in old.splitlines() if s.strip().startswith('lappend pins [dict create slice $index cell $cell pin $terminal drivers '))
        newline=next(s.strip() for s in new.splitlines() if s.strip().startswith('lappend pins [dict create slice $index cell $cell pin $terminal drivers '))
        setup=r'''
set index 0;set cell memory;set driver constant/O;set refs GND;set nets connected
proc get_property {property objects} {
 if {![llength $objects]} {error empty_property}
 return $objects
}
'''
        for terminal,points,expected in [('RDB_WR_A','',0),('CLK','',0),('ADDR_A[0]','',1),('ADDR_A[0]','state/Q',0)]:
            with self.subTest(terminal=terminal,points=points):
                body=setup+'\nset terminal {'+terminal+'};set startpoints {'+points+'};set pins {}\n'
                body+='set code [catch {'+newline+'} message]\nputs $code\n'
                actual=tcl('namespace eval ::m003 {\n'+body+'\n}')
                self.assertEqual(actual.returncode,0,actual.stderr)
                self.assertEqual(actual.stdout.strip(),str(expected))
        body=setup+'\nset terminal RDB_WR_A;set startpoints {};set pins {}\nset code [catch {'+oldline+'} message]\nputs [list $code $message]\n'
        actual=tcl('namespace eval ::m003 {\n'+body+'\n}',OLD_SOURCE)
        self.assertEqual(actual.returncode,0,actual.stderr)
        self.assertEqual(actual.stdout.strip(),'1 empty_property')


diagnostic=tcl('set code [catch {memory_startpoint_names RDB_WR_A {}} message]\nputs [list $code $message]\n')
assert diagnostic.returncode==0 and 'invalid command name "memory_startpoint_names"' in diagnostic.stdout
diagnosis_path=OUT/'snapshot_v2_r2_harness_namespace_correction.json'
diagnosis_path.write_text(json.dumps(dict(
  cause='The independent test extracted one line from m003::snapshot_body but evaluated it in the global namespace. Its unqualified helper call therefore could not resolve. Correct the test evaluation namespace to ::m003, matching the real proc.',
  direct_reproduction_stdout=diagnostic.stdout,direct_reproduction_stderr=diagnostic.stderr,
  initial_runner=ident(OUT/'snapshot_v2_independent_checks.py'),
  initial_receipt=ident(OUT/'snapshot_v2_independent_CPU14_receipt.json'),
  initial_log=ident(OUT/'snapshot_v2_independent_CPU14.log'),
  candidate_and_expectations_changed=False,
  correction='Only wrap exact memory expression/setup in namespace eval ::m003; retain old/new terminal expectations and exact source bytes.'
),indent=2)+'\n')

loader=unittest.TestLoader()
suite=unittest.TestSuite([loader.loadTestsFromTestCase(module.SnapshotCollections),loader.loadTestsFromTestCase(IndependentChecks)])
stream=io.StringIO()
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
log=OUT/'snapshot_v2_r2_independent_CPU14.log'
log.write_text(stream.getvalue())
test_ast=ast.parse(testfile.read_text())
old_ast=ast.parse((CAND/'test_m003_native_entry_repair.py.before').read_text())
old_main=old_ast.body[-1]
assert isinstance(old_main,ast.If)
assert ast.dump(test_ast.body[-1])==ast.dump(old_main)
assert [ast.dump(x) for x in old_ast.body[:-1]]==[ast.dump(x) for x in test_ast.body[:len(old_ast.body)-1]]
oldrow_body=next(n.value for n in ast.walk(test_ast) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'set row [dict create NAME {root/meta_read_addr_r_reg[0]}' in n.value)
oldrow=tcl(oldrow_body,OLD_SOURCE)
assert oldrow.returncode==1 and "'get_property' expects at least one object" in oldrow.stderr
replay=OUT/'snapshot_v2_r2_old_empty_pblock_replay.json'
replay.write_text(json.dumps(dict(source=ident(OLD_SOURCE),returncode=oldrow.returncode,stdout=oldrow.stdout,stderr=oldrow.stderr,scope='Synthetic original row only; not native AT017 exact call location'),indent=2)+'\n')
receipt=OUT/'snapshot_v2_r2_independent_CPU14_receipt.json'
record=dict(schema='A007_snapshot_v2_r2_independent_CPU_v1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful(),
            command='taskset -c 0-7 nice -n 5 python3 A007/snapshot_v2_r2_independent_checks.py',
            cwd=str(HW),cpu_affinity=sorted(os.sched_getaffinity(0)),nice=os.getpriority(os.PRIO_PROCESS,0),
            runner=ident(Path(__file__)),candidate=ident(CAND/'m003_joint_checks.tcl.proposed.v2'),
            test_source=ident(testfile),qualifier=ident(HW/'vivado/scripts/m003_joint_evidence.py'),
            assemblies=assemblies,old_test_AST_unchanged=True,main_guard_at_end_unchanged=True,
            proposed_tests=10,independent_tests=4,log=ident(log),old_mock_reproduction=ident(replay),
            scope='CPU mocked Tcl API and fixture validation only; no native EDA or full graph acceptance.')
receipt.write_text(json.dumps(record,indent=2)+'\n')
print(stream.getvalue())
print(json.dumps(ident(receipt),indent=2))
sys.exit(0 if result.wasSuccessful() else 1)
