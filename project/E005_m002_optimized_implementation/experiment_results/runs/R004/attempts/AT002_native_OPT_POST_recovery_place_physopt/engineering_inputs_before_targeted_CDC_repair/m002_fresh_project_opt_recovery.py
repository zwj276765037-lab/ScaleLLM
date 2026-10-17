"""Explicit log-derived E005 native-project OPT provenance.

This module never manufactures a command receipt or a successful native run.
Its caller supplies the existing diagnostic evidence functions as ``m``.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import re


GUARD = 'native project mode has no qualified explicit pre-place debug admission'
FROZEN_SHA = 'c34da1cfa5f8dec2a0bba93c282c5c07c71b8ed0bdcfc390330bc3261cce1e01'


def expected_physical_command(point, default, authorization):
    if authorization and authorization.get('profile') == 'm002_optimized_implementation':
        return dict(place='place_design -directive SSI_SpreadSLLs',
                    physopt='phys_opt_design -directive Default',
                    route='route_design -directive Default').get(point, default)
    return default


def verify_inherited_proof(m, identity, project, lineage, report):
    m.verify_identity(identity)
    proof = json.loads(Path(identity['path']).read_text())
    m.require(proof.get('schema') == 'E005_native_project_OPT_log_derived_v1' and
              proof.get('native_command_receipt_exists') is False,
              'inherited fresh OPT proof is not explicitly log-derived')
    source = Path(proof['original_command']['path']).parent
    qualified = qualify_native_project(m, source, project, lineage, report, write=False)
    m.require(qualified['inherited_opt_execution_proof'] == identity,
              'inherited fresh OPT proof differs from requalified native source')
    return qualified


def proof_source_paths(m, identity):
    """Bind the separate proof, retained inputs and fixed observations in-stage."""
    m.verify_identity(identity)
    proof = json.loads(Path(identity['path']).read_text())
    paths = {Path(identity['path'])}
    def visit(value):
        if isinstance(value, dict):
            if set(value) == {'path', 'bytes', 'sha256'}:
                m.verify_identity(value); paths.add(Path(value['path']))
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(proof)
    for path in m.input_manifest(Path(proof['archive']['path'])):
        paths.add(path)
    return sorted(paths)


def literal_assignment(m, text, variable):
    """Parse only a unique literal scalar/list assignment; never evaluate Tcl."""
    prefix = r'^[ \t]*set[ \t]+'+re.escape(variable)+r'[ \t]+'
    m.require(len(re.findall(prefix, text, re.M)) == 1,
              f'fresh PHY assignment missing or repeated: {variable}')
    matches = list(re.finditer(prefix+r'(?:\{([^{}]*)\}|([^\n{}]*))[ \t]*$', text, re.M))
    m.require(len(matches) == 1, f'fresh PHY assignment is not a bounded literal: {variable}')
    value = next(group for group in matches[0].groups() if group is not None).strip()
    m.require(not any(char in value for char in '$[];\\'),
              f'fresh PHY assignment contains executable substitution: {variable}')
    return value.split()


def qualify_disabled_phy_cache(m, attempt, value, records, original, project, *, create_observation=False):
    """Additional fresh-project proof; zero cached files alone is insufficient."""
    status = json.loads((attempt/'status.json').read_text())
    report = Path(status['report'])
    auth = m.full_impl.report_authorization(report)
    command = json.loads((report/'command.json').read_text())
    m.require(auth and auth['profile'] == m.full_impl.OPTIMIZED_PROFILE and
              auth['managed_attempt'] == str(attempt) and
              command.get('execution_mode') == 'project_runs' and command.get('stage') == 'place' and
              command.get('managed_attempt') == str(attempt) and status.get('project') == str(project) and
              status.get('exit_code') == 1 and status.get('native_exit_code') == 1 and
              status.get('stop_reason') is None and status.get('owned_survivors') == [],
              'disabled-cache PHY branch requires the genuine failed E005 fresh project')
    runtime = project/'scalellm_vcu118_f05.runs/impl_1/.Xil'
    relative = original.relative_to(runtime)
    match = re.fullmatch(r'Vivado-(\d+)-user/\1', str(relative))
    m.require(match and match.group(1) in status.get('tracked_identities', {}),
              'disabled-cache PHY worker is not owned by the actual native implementation')
    script_record = records[original/'get_cs_ip.tcl']
    script = Path(script_record['path']).read_text()
    log_record = records[original/'vivado.log']
    log = Path(log_record['path']).read_text()
    repo = project/'scalellm_vcu118_f05.cache/ip'
    modules = [f'scalellm_vcu118_f05_bd_ddr4_{d}_0_phy' for d in (1, 0)]
    expected = dict(part=['xcvu9p-flga2104-2L-e'], board_part=['xilinx.com:vcu118:part0:2.0'],
        ip_vlnv=['xilinx.com:ip:ddr4_phy:2.2']*2, ip_module_name=modules,
        ip_output_repo=[str(repo)], ip_cache_permissions=['disable'],
        output_dcp=[str(original/'out'/(name+'.0')/'result.dcp') for name in modules],
        output_xci=[str(original/'out'/(name+'.0')/'result.xci') for name in modules])
    traced_script = '\n'.join(line[2:] for line in log.splitlines() if line.startswith('# '))
    for variable, expected_value in expected.items():
        m.require(literal_assignment(m, script, variable) == expected_value and
                  literal_assignment(m, traced_script, variable) == expected_value,
                  f'actual fresh PHY script/log assignment differs: {variable}')
    m.require('synth_design completed successfully' in log and 'Exiting Vivado' in log and
              log.count('DBG: no cache hit, so run synth') == 2 and
              log.count('synth_design completed successfully') == 2,
              'disabled-cache PHY lacks two actual current syntheses and worker exit')
    for name in modules:
        m.require(not any(p.is_relative_to(original/'.cache/ip') and p.name == name+'.dcp' for p in records),
                  'disabled-cache fresh PHY unexpectedly has a worker-local third copy')
    declared_files = sorted(str(p) for p in repo.rglob('*') if p.is_file())
    m.require(repo.is_dir() and not any(Path(p).name in {name+'.dcp' for name in modules} for p in declared_files),
              'disabled-cache fresh PHY has unexpected declared-repo third DCP copies')
    main_log = report/'implementation_run.log'
    messages = [dict(line=n, text=line) for n,line in enumerate(main_log.read_text().splitlines(), 1)
                if 'Added synthesis output to IP cache for IP ' in line]
    m.require(len(messages) == 2 and all(sum(name in row['text'] for row in messages) == 1 for name in modules),
              'fresh PHY main-log cache dispositions are missing or ambiguous')
    observation_path = attempt/'generated_phy_terminal_repository_observation.json'
    if not observation_path.exists():
        m.require(create_observation, 'fresh PHY fixed terminal repository observation is missing')
        observation = dict(observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            status=m.file_id(attempt/'status.json'), project=str(project),
            declared_ip_output_repo=str(repo), declared_repo_files_observed=declared_files,
            matched_PHY_DCP_copies=0, scope='one fixed terminal observation; unrelated later repo entries do not rewrite historical provenance')
        observation_path.write_text(json.dumps(observation, indent=2)+'\n')
    observation = json.loads(observation_path.read_text())
    m.require(observation.get('status') == m.file_id(attempt/'status.json') and
              observation.get('project') == str(project) and observation.get('declared_ip_output_repo') == str(repo) and
              observation.get('matched_PHY_DCP_copies') == 0 and
              not any(Path(p).name in {name+'.dcp' for name in modules}
                      for p in observation['declared_repo_files_observed']),
              'fresh PHY fixed terminal repository observation changed')
    return dict(mode='E005_fresh_project_worker_cache_disabled',
        actual_worker_script={k:v for k,v in script_record.items() if k != 'source_path'},
        actual_worker_log={k:v for k,v in log_record.items() if k != 'source_path'},
        project=str(project), declared_ip_output_repo=str(repo), cache_permissions='disable',
        worker_local_cache_DCP_copies=0, terminal_repository_observation=m.file_id(observation_path),
        actual_script_and_log_assignments=expected,
        main_log=m.file_id(main_log), native_main_cache_messages=messages,
        scope='matching actual produced/result pairs; native cache messages retained; no measured third disk copy; no legacy cache exemption')


def no_active_owned_identity(m, status):
    tracked = status.get('tracked_identities', {})
    m.require(tracked and str(status['leader_pid']) in tracked,
              'fresh OPT terminal lacks tracked native process identities')
    observations = []
    for pid, ticks in sorted(tracked.items(), key=lambda row: int(row[0])):
        try:
            fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            observations.append(dict(pid=int(pid), expected_start_ticks=ticks, state='not_present'))
            continue
        m.require(int(fields[19]) != ticks,
                  f'fresh OPT still has a matching owned PID identity: {pid}')
        observations.append(dict(pid=int(pid), expected_start_ticks=ticks,
                                 state='different_identity'))
    return observations


def archive_frozen_inputs(m, source):
    frozen = m.ROOT.parent/'E005_m002_optimized_implementation/experiment_source/frozen_inputs_before_physical.json'
    m.require(m.sha256(frozen) == FROZEN_SHA, 'fresh OPT original 142-input freeze identity changed')
    rows = json.loads(frozen.read_text())['files']
    m.require(len(rows) == 142 and len({row['path'] for row in rows}) == 142,
              'fresh OPT original production freeze is incomplete')
    resolved = []
    for row in rows:
        original = Path(row['path'])
        archived = source/'stage_sources'/original.name
        current = archived if archived.is_file() else original
        m.require(current.is_file() and m.sha256(current) == row['sha256'],
                  f'fresh OPT original production input differs: {original}')
        resolved.append(dict(original_path=str(original), retained_identity=m.file_id(current)))
    return dict(manifest=m.file_id(frozen), inputs=resolved)


def qualify_native_project(m, source, project, lineage, report, *, write=True):
    """Read a naturally failed POST; return a distinct inherited-OPT parent."""
    m.require(source.is_relative_to(m.ROOT/'vivado/reports') and
              project.is_relative_to(m.ROOT/'vivado/project'), 'foreign fresh OPT source root')
    auth = m.full_impl.report_authorization(source)
    m.require(auth and auth['profile'] == m.full_impl.OPTIMIZED_PROFILE and auth['stage'] == 'place',
              'fresh OPT source is not the authorized E005 project run')
    command = json.loads((source/'command.json').read_text())
    attempt = Path(command['managed_attempt'])
    status_path = attempt/'status.json'
    status = json.loads(status_path.read_text())
    m.require(command.get('execution_mode') == 'project_runs' and command.get('stage') == 'place' and
              str(attempt) == auth['managed_attempt'] and
              command.get('synthesis') == lineage and lineage.get('source_rows') == 342 and
              lineage.get('checkpoint_paths') == 45 and status.get('project') == str(project) and
              status.get('report') == str(source) and status.get('stage') == 'place' and
              status.get('exit_code') == 1 and status.get('native_exit_code') == 1 and
              status.get('stop_reason') is None and status.get('owned_survivors') == [] and
              not (attempt/'controlled_stop_request.json').exists(),
              'fresh OPT source is not the native/supervisor failure without configured stop')
    launcher = m.key_values(source/'launcher_status.txt')
    m.require(launcher.get('stage') == 'place' and launcher.get('exit_code') == '1' and
              launcher.get('native_exit_code') == '1' and launcher.get('project') == str(project) and
              launcher.get('reports') == str(source), 'fresh OPT failed launcher identity mismatch')
    manager_command = json.loads((attempt/'command.json').read_text())
    started = json.loads((attempt/'started.json').read_text())
    m.require(all(started.get(key) == value for key,value in manager_command.items()) and
              set(started)-set(manager_command) == {'supervisor_pid','leader_pid','process_group'} and
              all(status.get(key) == value for key,value in started.items()),
              'fresh OPT manager command/started/status chain does not bind one attempt')
    identity_checks = no_active_owned_identity(m, status)
    identity_path = attempt/'native_project_opt_terminal_identity_observation.json'
    if not identity_path.exists():
        m.require(write, 'fresh OPT fixed terminal identity observation is missing')
        identity_path.write_text(json.dumps(dict(observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
            original_status=m.file_id(status_path), checks=identity_checks,
            scope='fixed observation of exact owned PID/start identities after native/supervisor terminal'), indent=2)+'\n')
    identities = json.loads(identity_path.read_text())
    m.require(identities.get('original_status') == m.file_id(status_path) and
              {str(row['pid']):row['expected_start_ticks'] for row in identities['checks']} == status['tracked_identities'] and
              all(row['state'] in {'not_present','different_identity'} for row in identities['checks']),
              'fresh OPT fixed terminal identity observation changed')
    m.validate_stage_archive(source, m.file_id(source/'stage_inputs.sha256'),
                             m.file_id(source/'archived_sources.sha256'))
    frozen = archive_frozen_inputs(m, source)
    result = m.key_values(source/'opt_result.txt')
    init = m.key_values(source/'init_result.txt')
    m.require(result.get('completed') == '0' and result.get('phase') == 'opt' and
              init.get('completed') == '1' and init.get('phase') == 'init',
              'fresh OPT original INIT/failed POST disposition was changed')
    m.require(not any((source/name).exists() for name in (
        'opt_command_result.txt', 'integrity_opt.json', 'debug_materialization_command_result.txt',
        'place_command_result.txt', 'physopt_command_result.txt', 'place.dcp', 'physopt.dcp',
        'diagnostic_evidence.json')), 'fresh OPT source has unexpected later/synthetic success artifacts')
    checkpoint = m.file_id(source/'opt.dcp')
    package = m.checkpoint_package(source/'opt.dcp')
    log_path = source/'implementation_run.log'
    text = log_path.read_text(errors='replace')
    markers = ['Command: opt_design', 'opt_design completed successfully',
               'source '+str(m.ROOT/'vivado/scripts/m002_diagnostic_opt_post.tcl'),
               "The checkpoint '"+checkpoint['path']+"' has been generated", GUARD]
    positions = [text.find(marker) for marker in markers]
    m.require(all(pos >= 0 for pos in positions) and positions == sorted(positions) and
              text.count('Command: opt_design') == 1 and
              not any('Command: '+name in text for name in ('implement_debug_core', 'place_design',
                                                           'phys_opt_design', 'route_design')) and
              'M002_DIAGNOSTIC_STEP_COMPLETED opt' not in text,
              'fresh OPT successful command/failed POST chronology is not genuine')
    native = source/'native_run_receipts'
    script_path = native/'scalellm_vcu118_f05_bd_wrapper.tcl'
    script = script_path.read_text()
    opt_command = re.search(r'^\s*opt_design\s*$', script, re.M)
    hook_command = re.search(r'^\s*source '+re.escape(str(m.ROOT/'vivado/scripts/m002_diagnostic_opt_post.tcl'))+r'\s*$', script, re.M)
    m.require(opt_command and hook_command and opt_command.start() < hook_command.start() and
              'step_failed opt_design' in script and 'return -code error' in script and
              (native/'.opt_design.error.rst').is_file() and
              not (native/'.opt_design.end.rst').exists(),
              'fresh OPT generated native Tcl/error receipt does not bind the failed POST')
    settings = m.key_values(source/'implementation_settings.txt')
    m.require(settings.get('STEPS.PLACE_DESIGN.ARGS.DIRECTIVE') == 'SSI_SpreadSLLs' and
              settings.get('STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE') == 'Default' and
              settings.get('STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE') == 'Default',
              'fresh OPT project settings no longer match E005 authorization')
    constraint_path = source/'constraints_opt.json'
    constraints = json.loads(constraint_path.read_text())
    m.require(constraints.get('phase') == 'opt' and constraints.get('parent') ==
              m.file_id(source/'constraints_init.json'), 'fresh OPT failed POST constraint ancestry mismatch')
    m.require(constraints.get('registry') == m.file_id(source/'xdc_registry_opt_hashed.tsv') and
              constraints.get('actual_reads') == m.file_id(source/'actual_xdc_reads_opt.json'),
              'fresh OPT actual constraint registry/read-file identity mismatch')
    metadata = constraints['metadata']
    registry_rows = (source/'xdc_registry_opt_hashed.tsv').read_text().splitlines()[1:]
    registry_metadata = {}
    for row in registry_rows:
        fields = row.split('\t')
        m.require(len(fields) == 9 and fields[0] not in registry_metadata and
                  constraints['hashes'].get(fields[0]) == fields[-1],
                  'fresh OPT constraint registry has duplicate/inconsistent rows')
        registry_metadata[fields[0]] = fields[1:-1]
    project_constraints = json.loads((source/'constraints_project.json').read_text())
    m.require(len(registry_metadata) == 162 and metadata == registry_metadata == project_constraints['metadata'],
              'fresh OPT original candidate XDC metadata is incomplete or changed')
    source_archives = {}
    generated = dict(generated_phy=m.generated_phy_parent(attempt, fresh_project=project, create_terminal_observation=write),
                     generated_debug=m.generated_debug_parent(attempt))
    hashes = dict(constraints['hashes'])
    candidates = {}
    for kind, value in generated.items():
        for name, identity in value['main_generated_xdc_candidates'].items():
            m.require(name not in hashes or hashes[name] == identity['sha256'],
                      'fresh OPT generated constraint candidate bytes differ from actual constraint hash')
            hashes[name] = identity['sha256']; source_archives[name] = identity
            candidates[name] = dict(kind=kind, produced_phase='actual_OPT_core_generation',
                effective_import_status='inherited_binary_checkpoint; candidate is not a fabricated read record')
    for name in hashes:
        m.constraint_source(name, dict(hashes=hashes, source_archives=source_archives))
    actual = json.loads((source/'actual_xdc_reads_opt.json').read_text())['records']
    recomputed = []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?", line)
        if match:
            recomputed.append(dict(line=number, path=match.group(1), scope=match.group(2),
                                   sha256=hashes[match.group(1)]))
    m.require(actual and actual == recomputed,
              'fresh OPT actual constraint records are incomplete or changed')
    required = ('timing_opt.rpt', 'utilization_opt.rpt', 'drc_opt.rpt', 'check_timing_opt.rpt',
                'clocks_opt.rpt', 'cdc_opt.rpt', 'clock_interaction_opt.rpt', 'exceptions_opt.rpt',
                'pulse_width_opt.rpt', 'bus_skew_opt.rpt', 'reset_cdc_and_io_probe_opt.tsv',
                'xpm_invalid_endpoint_probe_opt.tsv', 'head_wave_local_opt.tsv')
    reports = {name:m.file_id(source/name) for name in required}
    m.require(all(value['bytes'] > 0 for value in reports.values()), 'fresh OPT incomplete POST report set')
    proof = dict(schema='E005_native_project_OPT_log_derived_v1', origin='native_project_log_and_generated_Tcl',
        native_command_receipt_exists=False, original_execution_state='failed_incomplete_OPT_POST',
        original_native_exit_code=1, original_supervisor_exit_code=1,
        successful_native_command='opt_design', qualified_scope='completed OPT only; no POST/admission success',
        checkpoint=checkpoint, checkpoint_package=package, synthesis=lineage,
        markers=[dict(text=marker, character_offset=pos) for marker,pos in zip(markers, positions)],
        source_log=m.file_id(log_path), native_generated_tcl=m.file_id(script_path),
        native_OPT_error_receipt=m.artifact_id(native/'.opt_design.error.rst'),
        original_status=m.file_id(status_path), original_command=m.file_id(source/'command.json'),
        original_manager_command=m.file_id(attempt/'command.json'), original_started=m.file_id(attempt/'started.json'),
        terminal_identity_observation=m.file_id(identity_path),
        original_launcher=m.file_id(source/'launcher_status.txt'), frozen_production_inputs=frozen,
        stage_inputs=m.file_id(source/'stage_inputs.sha256'), archive=m.file_id(source/'archived_sources.sha256'),
        original_failed_POST=m.file_id(source/'opt_result.txt'), constraints=m.file_id(constraint_path),
        generated_phy=generated['generated_phy'], generated_debug=generated['generated_debug'])
    proof_path = attempt/'native_project_opt_execution_proof.json'
    if proof_path.exists():
        m.require(json.loads(proof_path.read_text()) == proof, 'fresh OPT log-derived proof changed')
    elif write:
        proof_path.write_text(json.dumps(proof, indent=2)+'\n')
    m.require(proof_path.is_file(), 'fresh OPT separate log-derived proof not yet materialized')
    value = dict(phase='post_opt_pre_debug', original_execution_state='failed_native_project_OPT_POST_guard',
        original_impl_run_remains='FAIL', original_POST_remains='incomplete',
        opt_evidence_complete=False, opt_reports_complete=True,
        opt_execution_proof_kind='native_project_log_derived',
        inherited_opt_execution_proof=m.file_id(proof_path),
        checkpoint=checkpoint, checkpoint_package=package, synthesis=lineage,
        status=m.file_id(status_path), launcher=m.file_id(source/'launcher_status.txt'),
        child_log=m.file_id(log_path), command=m.file_id(source/'command.json'),
        stage_inputs=m.file_id(source/'stage_inputs.sha256'), archive=m.file_id(source/'archived_sources.sha256'),
        implementation_settings=m.file_id(source/'implementation_settings.txt'),
        source_registry=m.file_id(source/'xdc_registry_opt_hashed.tsv'), source_metadata=metadata,
        hashes=hashes, actual_reads=actual, source_archives=source_archives,
        generated_source_candidates=candidates, **generated,
        parent_constraints=m.file_id(constraint_path), constraint_mode='embedded_checkpoint_inherited',
        inherited_reports=reports, parent_coverage='NOT_QUALIFIED_INCOMPLETE_NATIVE_OPT_POST',
        formal_reset_cdc_safety='OPEN', inherited_reset_evidence=None)
    if write:
        (report/'recovery_parent.json').write_text(json.dumps(value, indent=2)+'\n')
    return value


def qualify_restored_opt(m, source, project, lineage, report, *, write=True):
    """Resume a failed POST of the same new OPT; never replay a later command."""
    command = json.loads((source/'command.json').read_text())
    old = json.loads((source/'recovery_parent.json').read_text())
    m.require(old.get('phase') == 'post_opt_pre_debug' and
              old.get('opt_execution_proof_kind') == 'native_project_log_derived',
              'restored fresh OPT is outside its exact pre-debug proof scope')
    original = verify_inherited_proof(m, old['inherited_opt_execution_proof'], project, lineage, report)
    auth = m.full_impl.report_authorization(source)
    attempt = Path(command['managed_attempt'])
    status_path = attempt/'status.json'; status = json.loads(status_path.read_text())
    m.require(auth and auth['profile'] == m.full_impl.OPTIMIZED_PROFILE and auth['managed_attempt'] == str(attempt) and
              command.get('execution_mode') == 'checkpoint_restored_commands' and command.get('stage') == 'place' and
              command.get('synthesis') == lineage and status.get('stage') == 'place' and
              status.get('project') == str(project) and status.get('report') == str(source) and
              status.get('exit_code') == 1 and status.get('native_exit_code') == 1 and
              status.get('stop_reason') is None and status.get('owned_survivors') == [],
              'restored fresh OPT is not this terminal failed POST without configured stop')
    manager_command = json.loads((attempt/'command.json').read_text())
    started = json.loads((attempt/'started.json').read_text())
    m.require(all(started.get(key) == value for key,value in manager_command.items()) and
              set(started)-set(manager_command) == {'supervisor_pid','leader_pid','process_group'} and
              all(status.get(key) == value for key,value in started.items()),
              'restored fresh OPT manager command/started/status chain changed')
    no_active_owned_identity(m, status)
    launcher = m.key_values(source/'launcher_status.txt')
    m.require(launcher.get('exit_code') == '1' and launcher.get('native_exit_code') == '1' and
              launcher.get('project') == str(project), 'restored fresh OPT launcher identity mismatch')
    upstream = Path(command.get('environment', {}).get('HAP_OPT_REPORT_DIR', ''))
    m.require(upstream.is_absolute() and old['command']['path'] == str(upstream/'command.json') and
              old.get('synthesis') == lineage, 'restored fresh OPT upstream identity mismatch')
    m.validate_stage_archive(source, m.file_id(source/'stage_inputs.sha256'), m.file_id(source/'archived_sources.sha256'))
    for name in ('opt_command_result.txt','debug_materialization_command_result.txt','place_command_result.txt',
                 'physopt_command_result.txt','debug_materialized.dcp','place.dcp','physopt.dcp','diagnostic_evidence.json'):
        m.require(not (source/name).exists(), 'restored fresh OPT has later executed-command evidence; recover the later checkpoint')
    checkpoint = m.file_id(source/'opt.dcp')
    m.require(all(checkpoint[key] == original['checkpoint'][key] == old['checkpoint'][key] for key in ('bytes','sha256')),
              'restored fresh OPT checkpoint bytes transformed')
    m.checkpoint_package(source/'opt.dcp')
    result = m.key_values(source/'opt_result.txt')
    m.require(result.get('completed') == '0' and result.get('phase') == 'opt' and
              result.get('evidence_origin') == 'inherited_identical_opt_checkpoint',
              'restored fresh OPT failed POST disposition changed')
    text = (source/'implementation_run.log').read_text(errors='replace')
    m.require(f"Command: open_checkpoint {old['checkpoint']['path']}" in text and
              not any('Command: '+name in text for name in ('opt_design','implement_debug_core','place_design','phys_opt_design','route_design')),
              'restored fresh OPT executed a new transformation or later command')
    reports = {name:m.file_id(source/name) for name in original['inherited_reports']}
    m.require(all(all(value[key] == original['inherited_reports'][name][key] for key in ('bytes','sha256'))
                  for name,value in reports.items()), 'restored fresh OPT copied reports differ from original OPT')
    constraint_path = source/'constraints_opt.json'; constraints = json.loads(constraint_path.read_text())
    m.require(constraints.get('mode') == 'embedded_checkpoint_inherited' and
              constraints.get('candidate_metadata') == original['source_metadata'] and constraints['hashes'] == original['hashes'],
              'restored fresh OPT effective/candidate constraints changed')
    for name in constraints['hashes']:
        m.constraint_source(name, constraints)
    proof_sources = list(old.get('inherited_proof_sources', []))
    proof_sources += [m.file_id(path) for path in (status_path, attempt/'command.json', attempt/'started.json',
        source/'command.json', source/'launcher_status.txt', source/'implementation_run.log', source/'opt_result.txt',
        source/'stage_inputs.sha256', source/'archived_sources.sha256', source/'recovery_parent.json', constraint_path)]
    proof_sources += [m.file_id(path) for path in m.input_manifest(source/'archived_sources.sha256')]
    if (source/'integrity_opt.json').exists():
        proof_sources.append(m.file_id(source/'integrity_opt.json'))
    for identity in proof_sources:
        m.verify_identity(identity)
    value = dict(original)
    value.update(original_execution_state='failed_restored_identical_OPT_POST', checkpoint=checkpoint,
        status=m.file_id(status_path), launcher=m.file_id(source/'launcher_status.txt'),
        child_log=m.file_id(source/'implementation_run.log'), command=m.file_id(source/'command.json'),
        stage_inputs=m.file_id(source/'stage_inputs.sha256'), archive=m.file_id(source/'archived_sources.sha256'),
        implementation_settings=m.file_id(source/'implementation_settings.txt'),
        source_registry=m.file_id(source/'xdc_registry_opt_hashed.tsv'), inherited_reports=reports,
        upstream_recovery=m.file_id(source/'recovery_parent.json'), parent_constraints=m.file_id(constraint_path),
        inherited_proof_sources=proof_sources, source_archives=constraints.get('source_archives', {}))
    if write:
        (report/'recovery_parent.json').write_text(json.dumps(value, indent=2)+'\n')
    return value
