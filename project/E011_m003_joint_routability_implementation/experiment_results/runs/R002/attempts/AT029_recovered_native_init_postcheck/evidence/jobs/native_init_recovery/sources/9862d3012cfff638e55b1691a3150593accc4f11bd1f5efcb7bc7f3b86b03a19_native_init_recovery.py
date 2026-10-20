"""Explicit same-checkpoint INIT recovery; original 48-source validators stay frozen."""
from pathlib import Path
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HW = ROOT / 'project/hardware'
sys.path.insert(0, str(HW / 'vivado/scripts'))
import m003_entry as entry
import m003_native_init as init
import m003_stage as stage
import m003_physical_evidence as base
import m002_physical_evidence as old

ORIGIN = ROOT / 'project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT028_native_init_opt_preplace'
REPORT = HW / 'vivado/reports/m003_E011_R002_AT028_native_init_opt_preplace'
PROJECT = HW / 'vivado/project/scalellm_m003_E011_R002_AT002'
SYNTH_AT = ORIGIN.parent / 'AT027_reset_semantics_postreport_recovery'
SYNTH_REPORT = HW / 'vivado/reports/m003_E011_R002_AT027_reset_semantics_postreport_recovery'
MANIFEST_SHA = '42dafce33f4727734dcf169b285a3decfcfa18d78d10f9a36463b4bea7c904d5'
OVERLAY = HW / 'vivado/constraints/m003_joint_locality.xdc'

def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')

def registry(path):
    lines = path.read_text().splitlines()
    expected = 'path USED_IN USED_IN_SYNTHESIS USED_IN_IMPLEMENTATION IS_ENABLED SCOPED_TO_REF SCOPED_TO_CELLS PROCESSING_ORDER SHA256'.split()
    old.require(lines[0].split('\t') == expected, 'full registry header required')
    result = {}
    for line in lines[1:]:
        row = line.split('\t')
        old.require(len(row) == 9 and row[0] not in result, 'malformed/duplicate registry')
        result[row[0]] = dict(zip(expected[1:-1], row[1:-1]))
    return result

def context_proof(candidate, actual, prefix, embedded):
    """Keep original policy strict; admit only the observed unmanaged representation."""
    row = candidate
    old.require(row.get('USED_IN_SYNTHESIS') == '0' and row.get('USED_IN_IMPLEMENTATION') == '1'
                and row.get('IS_ENABLED') == '1' and row.get('SCOPED_TO_REF') == ''
                and row.get('SCOPED_TO_CELLS') == '' and row.get('PROCESSING_ORDER') == 'LATE'
                and row.get('FILE_TYPE') == 'TCL', 'original global implementation-only LATE TCL policy lost')
    old.require(actual.get('USED_IN_SYNTHESIS') == '1' and actual.get('USED_IN_IMPLEMENTATION') == '1'
                and actual.get('IS_ENABLED') == '1' and actual.get('SCOPED_TO_REF') == ''
                and actual.get('SCOPED_TO_CELLS') == '' and actual.get('PROCESSING_ORDER') == 'LATE',
                'actual INIT registration differs beyond pinned unmanaged context')
    read = '  read_xdc -unmanaged ' + str(OVERLAY)
    order = '  set_property processing_order LATE [get_files ' + str(OVERLAY) + ']'
    old.require(prefix.splitlines().count(read) == 1 and prefix.splitlines().count(order) == 1,
                'native unmanaged overlay read/order missing or duplicated')
    old.require('  create_project -in_memory -part xcvu9p-flga2104-2L-e' in prefix
                and '  set_property design_mode GateLvl [current_fileset]' in prefix
                and prefix.index(read) < prefix.index(order) < prefix.index('  link_design '),
                'native in-memory GateLvl implementation context not proven')
    rows = [r for r in embedded if ('cfile:' + str(OVERLAY) + ' ') in r]
    old.require(len(rows) == 1 and ' order:LATE ' in rows[0] and ' unmanaged:yes ' in rows[0],
                'actual checkpoint overlay unmanaged/LATE source identity missing')
    old.require('scoped_inst:' not in rows[0] and 'scoped_ref:' not in rows[0],
                'embedded selected overlay is unexpectedly scoped')

def prepare(output):
    entry.check_sources(); old.require(old.sha256(entry.MANIFEST) == MANIFEST_SHA, 'frozen48 changed')
    status = ORIGIN / 'evidence/jobs/native_pre_place/status.json'
    terminal = json.loads(status.read_text())
    old.require(terminal['native_exit_code'] == 1 and terminal['stop_reason'] is None
                and not terminal['owned_survivors'] and terminal['core_RTL_unchanged_during_job'], 'origin terminal not natural failed/closed')
    text = (REPORT / 'vivado.log').read_text(errors='replace')
    old.require('link_design completed successfully' in text and 'M003 overlay must be global implementation-only LATE TCL' in text
                and not (REPORT / 'opt_command_result.txt').exists(), 'wrong recovery stage/origin')
    prefix_record = json.loads((REPORT / 'native_init_prefix.json').read_text())
    for key in ('preserved_driver', 'prefix'):
        old.verify_identity(prefix_record[key])
    prefix = Path(prefix_record['prefix']['path']).read_text()
    old.require(init.init_prefix(Path(prefix_record['preserved_driver']['path']).read_text()) == prefix,
                'saved INIT prefix is not exact complete native prefix')
    candidate = json.loads((REPORT / 'm003_candidate_registration.json').read_text())
    entry.check_registration([candidate]); old.require(candidate['source_manifest_sha256'] == MANIFEST_SHA
                and candidate['overlay_sha256'] == old.sha256(OVERLAY), 'original candidate binding changed')
    actual = registry(REPORT / 'xdc_registry_init.tsv')[str(OVERLAY)]
    embedded = []; embedded_ids = []
    with zipfile.ZipFile(REPORT / 'init.dcp') as archive:
        for name in archive.namelist():
            if name.endswith('.xdc'):
                data = archive.read(name)
                embedded_ids.append(dict(member=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
                embedded += [line for line in data.decode().splitlines() if line.startswith('set_property SRC_FILE_INFO ')]
    context_proof(candidate, actual, prefix, embedded)
    reads = []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"(Parsing XDC File|Sourcing Tcl File) \[([^]]+)\](?: for cell '([^']+)')?", line)
        if match:
            path = Path(match[2]); reads.append(dict(line=number, operation=match[1], scope=match[3], source=old.file_id(path)))
    selected = [r for r in reads if r['source']['path'] == str(OVERLAY)]
    old.require(len(selected) == 1 and selected[0]['operation'] == 'Sourcing Tcl File', 'actual native overlay source record missing')
    applied = entry.check_apply(REPORT)
    old.require(applied['actual_native_apply_count'] == 1, 'origin INIT actual apply inventory changed')
    for row in applied['receipts']: old.verify_identity(row)
    anchors = [status, ORIGIN / 'evidence/AT028_owner_terminal_and_input_closure.json', REPORT / 'launcher_status.json',
               REPORT / 'vivado.log', REPORT / 'native_init_prefix.json', REPORT / 'native_init_prefix.tcl',
               REPORT / 'native_init_prefix_full_generated_driver.tcl', REPORT / 'm003_candidate_registration.json',
               REPORT / 'xdc_registry_project.tsv', REPORT / 'xdc_registry_init.tsv', REPORT / 'effective_build_identity.txt',
               REPORT / 'stage_inputs.sha256', REPORT / 'source_archive.json']
    # Existing raw INIT reports stay attributed to the original native attempt.
    inherited = [REPORT / n for n in ('init.dcp','utilization_init.rpt','timing_init.rpt','drc_init.rpt',
                 'check_timing_init.rpt','clocks_init.rpt','cdc_init.rpt','clock_interaction_init.rpt','exceptions_init.rpt')]
    sources = [HERE / n for n in ('native_init_recovery.py','recover_init.tcl','launch.py')]
    sources.append(HERE.parent / 'AT028_offline_pblock_membership_check.py')
    value = dict(schema='M003_AT028_actual_INIT_checkpoint_recovery_v1', created_utc=stage.now(),
                 origin_attempt=str(ORIGIN), origin_report=str(REPORT), project=str(PROJECT),
                 synthesis_report=str(SYNTH_REPORT), synthesis_attempt=str(SYNTH_AT),
                 source_manifest=old.file_id(entry.MANIFEST), sources=[old.file_id(p) for p in sources],
                 anchors=[old.file_id(p) for p in anchors], inherited=[old.file_id(p) for p in inherited],
                 checkpoint=old.file_id(REPORT / 'init.dcp'), candidate=candidate, actual_native_INIT_registry=actual,
                 native_INIT_FILE_TYPE='NOT_EXPORTED_IN_ORIGIN; not inferred from file extension',
                 embedded_XDC_members=embedded_ids, embedded_source_info=embedded,
                 original_native_reads=reads, original_actual_apply=applied,
                 INIT_execution='inherited actual AT028 native INIT, not re-executed',
                 remaining='restored effective selected snapshot + remaining INIT POST, explicit OPT, actual conditional debug, strict preplace; no place')
    save(output, value); return value

def verify(package):
    value = json.loads(package.read_text())
    old.require(value['schema'] == 'M003_AT028_actual_INIT_checkpoint_recovery_v1'
                and value['origin_attempt'] == str(ORIGIN) and value['project'] == str(PROJECT), 'foreign recovery package')
    for row in [value['source_manifest'], value['checkpoint'], *value['sources'], *value['anchors'], *value['inherited']]: old.verify_identity(row)
    for row in value['original_native_reads']: old.verify_identity(row['source'])
    entry.check_sources(); old.require(old.sha256(entry.MANIFEST) == MANIFEST_SHA, 'runtime frozen48 changed')
    context_proof(value['candidate'], value['actual_native_INIT_registry'], (REPORT / 'native_init_prefix.tcl').read_text(), value['embedded_source_info'])
    stage.lineage(PROJECT, SYNTH_REPORT, SYNTH_AT)
    return value

def constraints(point, report):
    package = Path(os.environ['HAP_M003_INIT_RECOVERY_PACKAGE']); value = verify(package)
    if point == 'project': return base.current_native_constraints(point, report)
    old.require(point in {'init','opt','debug_materialized'}, 'unexpected recovery phase')
    metadata, hashes = old.hash_registry(point, report)
    parent = report / ('constraints_project.json' if point == 'init' else 'constraints_init.json' if point == 'opt' else 'constraints_opt.json')
    prior = json.loads(parent.read_text())
    for name, digest in prior['hashes'].items(): old.require(Path(name).is_file() and old.sha256(Path(name)) == digest, 'inherited constraint bytes changed:' + name)
    for name, props in prior['metadata'].items(): old.require(metadata.get(name) == props, 'source candidate scope/enable/order changed:' + name)
    additions = set(hashes) - set(prior['hashes'])
    allowed_path = report / f'tool_debug_xdc_{point}.txt'
    allowed = set(allowed_path.read_text().splitlines()) if allowed_path.exists() else set()
    old.require(not additions or (point == 'debug_materialized' and additions <= allowed), 'unclassified new restored constraint sources')
    inherited_hashes = {r['source']['path']:r['source']['sha256'] for r in value['original_native_reads']}
    hashes = {**prior['hashes'], **inherited_hashes, **hashes}
    embedded = report / f'embedded_xdc_registry_{point}.tsv'
    old.require(embedded.is_file(), 'actual embedded registry observations missing')
    live = report / 'restore_apply_attempts.json'; attempts = json.loads(live.read_text())
    old.require(attempts == dict(before=0, after=0, delta=0), 'restore attempted to apply overlay')
    actual = report / f'actual_xdc_reads_{point}.json'
    save(actual, dict(mode='actual_AT028_INIT_embedded_checkpoint_inherited', records=[],
        inherited_native_reads=value['original_native_reads'], original_actual_apply=value['original_actual_apply'],
        checkpoint=value['checkpoint'], recovery_package=old.file_id(package),
        actual_embedded_registry=old.file_id(embedded), no_new_overlay_source_or_apply=True))
    result = dict(phase=point, mode='M003_AT028_INIT_embedded_checkpoint_inherited', hashes=hashes, metadata=metadata,
                  registry=old.file_id(report / f'xdc_registry_{point}_hashed.tsv'), actual_reads=old.file_id(actual),
                  parent=old.file_id(parent), recovery_package=old.file_id(package), embedded_observation=old.file_id(embedded))
    save(report / f'constraints_{point}.json', result); return result

def hook(point, report):
    # Narrow explicit adapter: retain every original numeric/clock/CDC/reset/DRC guard.
    import importlib.util
    path = HERE.parent / 'AT028_offline_pblock_membership_check.py'
    spec = importlib.util.spec_from_file_location('membership', path); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result = module.check(report / f'm003_stream_{point}_cells.jsonl', HW / 'vivado/constraints/m003_joint_locality_spec.json')
    save(report / f'effective_pblock_membership_{point}.json', result)
    old.require(result['passed'], 'actual restored C01/M2 membership not preserved')
    base.constraint_chain = constraints
    base.hook_batch(point, report)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare','verify','constraints','hook-batch'])
    parser.add_argument('point', nargs='?'); parser.add_argument('report', nargs='?', type=Path)
    parser.add_argument('--package', type=Path, default=HERE / 'recovery_package.json'); args = parser.parse_args()
    if args.action == 'prepare': result = prepare(args.package); print(json.dumps(dict(prepared=True, sources=len(result['sources']), checkpoint=result['checkpoint'])))
    elif args.action == 'verify': verify(args.package); print('{"passed":true,"new_EDA":false}')
    elif args.action == 'constraints': constraints(args.point, args.report.resolve())
    else: hook(args.point, args.report.resolve())
