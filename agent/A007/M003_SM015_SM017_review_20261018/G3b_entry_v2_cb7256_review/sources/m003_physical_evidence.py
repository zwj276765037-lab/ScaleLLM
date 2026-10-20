#!/usr/bin/env python3
"""M003 native stage admission; reuse original clock/reset/CDC/resource predicates."""
from m002_physical_evidence import *
import m002_physical_evidence as original
import m003_stage as selected
import m003_entry as entry

def constraint_chain(point,report):
    import os
    if point=='project' and os.environ.get('HAP_EXECUTION_MODE')=='checkpoint_restored_commands':
        mode=os.environ.pop('HAP_EXECUTION_MODE')
        try:return original.constraint_chain(point,report)
        finally:os.environ['HAP_EXECUTION_MODE']=mode
    if os.environ.get('HAP_EXECUTION_MODE')!='checkpoint_restored_commands':
        return original.constraint_chain(point,report)
    metadata,hashes=hash_registry(point,report)
    parent=Path(os.environ['HAP_PRE_PLACE_REPORT_DIR'])/'constraints_debug_materialized.json' if point=='place' else report/('constraints_place.json' if point=='physopt' else 'constraints_physopt.json')
    old=json.loads(parent.read_text())
    for name,digest in old['hashes'].items():
        require(Path(name).is_file() and sha256(Path(name))==digest,'inherited effective constraint source changed: '+name)
    for name,values in metadata.items():
        require(name in old['metadata'] and old['metadata'][name]==values,'candidate XDC scope/enable/order changed on restore: '+name)
    for name in ('attention_mlp_vcu118_board_v5.xdc','vcu118_ddr4_explicit_pins.xdc','board_clock_domains.xdc','ddr_timing_recovery.xdc','m003_joint_locality.xdc'):
        paths=[n for n in metadata if Path(n).name==name]
        require(len(paths)==1,'restored candidate required XDC missing: '+name)
    mode=report/f'embedded_xdc_registry_{point}.tsv'
    require(mode.is_file(),'missing actual checkpoint embedded registry observations')
    result=dict(phase=point,mode='M003_embedded_checkpoint_inherited',hashes=old['hashes'],metadata=old['metadata'],registry=file_id(report/f'xdc_registry_{point}_hashed.tsv'),actual_reads=old['actual_reads'],parent=file_id(parent),embedded_observation=file_id(mode))
    (report/f'constraints_{point}.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def hook_batch(point: str, report: Path) -> None:
    """One small process validates every frozen row; avoids 339 large forks."""
    import os
    lineage = selected.lineage(*(Path(os.environ[k]).resolve() for k in
        ("HAP_PROJECT_DIR", "HAP_SYNTH_REPORT_DIR", "HAP_SYNTH_ATTEMPT_DIR")))
    input_manifest(report / "stage_inputs.sha256")
    constraints = constraint_chain(point, report)
    if point == 'opt':
        receipt=key_values(report/'opt_command_result.txt')
        require(receipt.get('command')=='opt_design' and receipt.get('native_tcl_code')=='0','M003 explicit opt command not natively successful')
    gate_issues=[]
    def collect(name, action):
        try:return action()
        except Exception as exc:
            gate_issues.append(f'{name}: {type(exc).__name__}: {exc}')
            return None
    counts = collect('clock_counts',lambda:check_timing_counts(report / f"check_timing_{point}.rpt")) or {}
    bb = int(key_values(report / f"{point}_result.txt")["blackboxes"])
    coverage = collect('clock_coverage',lambda:phase_coverage(point, report, counts, bb, point=="opt" or os.environ.get("HAP_EXECUTION_MODE") == "checkpoint_restored_commands"))
    io = collect('reset_IO',lambda:reset_io_coverage(report / f"check_timing_{point}.rpt"))
    inherited_reset = (json.loads((report/'recovery_parent.json').read_text()).get('inherited_reset_evidence')
                       if point=='opt' and (report/'recovery_parent.json').is_file() else None)
    graph_path=report/f'reset_graph_{point}.tsv';fanout_path=report/f'cdc_changed_reset_{point}.tsv'
    if inherited_reset:
        for key in ('graph','fanout'):verify_identity(inherited_reset[key])
        for identity in [*inherited_reset['exports'],*inherited_reset.get('auxiliary_cdc_reports',[])]:verify_identity(identity)
        if inherited_reset.get('bram_port_clocks'):verify_identity(inherited_reset['bram_port_clocks'])
        graph_path=Path(inherited_reset['graph']['path']);fanout_path=Path(inherited_reset['fanout']['path'])
    if point == "init" or (point == 'opt' and not graph_path.is_file()):
        structure = {"qualified": False, "status": "DEFERRED_TO_DEBUG_MATERIALIZED_PRE_PLACE", "issues": []}
    else:
        structure = collect('reset_structure',lambda:reset_structure(graph_path)) or {'qualified':False,'issues':['structural parsing failed; see gate_issues']}
        (report / f"reset_structure_{point}.json").write_text(json.dumps(structure, indent=2) + "\n")
    if point not in {'init','opt'} and not structure['qualified']:
        gate_issues.append('known reset CDC/IO structural conditions not established: '+str(structure.get('issues')))
    bram_path=Path(inherited_reset['bram_port_clocks']['path']) if inherited_reset and inherited_reset.get('bram_port_clocks') else report/f'bram_port_clocks_{point}.tsv'
    fanout = collect('reset_fanout',lambda:reset_fanout(fanout_path,bram_path)) if fanout_path.is_file() else None
    cdc = collect('critical_CDC',lambda:critical_coverage(report / f"cdc_{point}.rpt", Path(os.environ["HAP_SYNTH_REPORT_DIR"]) / "cdc_post_synth.rpt",structure,fanout))
    debug_clocks=collect('debug_clocks',lambda:debug_clock_facts(report/'debug_debug_materialized.tsv')) if point == 'debug_materialized' else None
    if debug_clocks and not debug_clocks['relationship_qualified']:
        gate_issues.append('actual hub output clock relationship is unresolved: '+str(debug_clocks['relationship_issues']))
    resources=collect('resources',lambda:utilization_metrics(report / f"utilization_{point}.rpt"))
    (report / f"integrity_{point}.json").write_text(json.dumps({
        "observed_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "phase": point,
        "synthesis": lineage, "resources": resources,
        "constraints": file_id(report / f"constraints_{point}.json"), "cdc_classification": cdc,
        "reset_io_classification": io, "reset_structure": structure, "debug_clock_observation":debug_clocks,
        "reset_fanout_observation":fanout,
        "gate_issues":gate_issues}, indent=2) + "\n")
    require(not gate_issues,'diagnostic pre-place/stage conditions not established: '+str(gate_issues))
    # OPT can only authorize debug implementation, regardless of BB count.
    eligible = int(point != "opt")
    (report / f"admission_{point}.txt").write_text(
        f"clock_coverage {coverage}\ndiagnostic_eligible {eligible}\ndebug_materialization_eligible {int(point == 'opt')}\n")

if __name__=='__main__':
    import sys
    require(len(sys.argv)==4 and sys.argv[1] in {'hook-batch','constraints'},'expected hook-batch/constraints PHASE REPORT')
    if sys.argv[1]=='constraints':constraint_chain(sys.argv[2],Path(sys.argv[3]).resolve())
    else:hook_batch(sys.argv[2],Path(sys.argv[3]).resolve())
