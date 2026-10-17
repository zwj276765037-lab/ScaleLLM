#!/usr/bin/env python3
"""Identity and diagnostic evidence for M002. Never qualifies physical signoff."""
from __future__ import annotations

import m002_execution_profile as full_impl
import m002_synthesis_recovery as synth_recovery
import m002_fresh_project_opt_recovery as fresh_opt
import sys

import datetime as dt
from functools import cache
import json
import math
from pathlib import Path
import re

from emit_current_board_evidence import file_id, input_manifest, key_values, require, sha256, status_id

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "m002_physical_diagnostic_v1"
PRIMITIVE_MODEL_ROOT=Path('/home/user/EDA-202/vivado/vivado_2025.2/2025.2/Vivado/data/verilog/src/unisims')
PRIMITIVE_MODEL_HASHES={'FDCE':'74d30d7c788e7db47f12b92d5b4b57b707974a0962708b309e4cc081d5f98b04',
                      'FDRE':'e2965e4b5174bd8de84b82e89a7b4ea5df36d8715c4f585580c16b8e6d9aa80d'}
BRAM_MODEL_HASHES={'RAMB18E2':'5b5824a9a33980c7019ca4ea18d272134da4e1e3b8a0ba6b576e485eedb27dc5',
                   'RAMB36E2':'de300b57debd3f31771fa1d7a343f12200658cea6317e4da2a8c3d2f8e61519d'}


@cache
def bram_write_clock(ref: str, terminal: str) -> tuple[str, dict]:
    require(ref in BRAM_MODEL_HASHES,'unknown BRAM primitive for write-port clock')
    path=PRIMITIVE_MODEL_ROOT/(ref+'.v')
    require(sha256(path)==BRAM_MODEL_HASHES[ref],'BRAM same-version functional model identity changed')
    match=re.fullmatch(r'WEBWE\[(\d+)\]',terminal)
    require(match is not None and int(match.group(1)) < (8 if ref=='RAMB36E2' else 4),
            'unknown BRAM write terminal or out-of-range bit')
    return 'CLKBWRCLK',file_id(path)


SYNTH_ANCHORS = {
    "inputs.sha256": "1dc14fef9dbe62ba0a55a7eebef3a5c0a277574c674e2d3310d5d69e10f711d3",
    "build_identity.txt": "4647130ebdfe11b9b853698a30d1cc6455e06e551307867421978411c71baa10",
    "fresh_synth_complete.txt": "346cceddd7180ad519b5862da92994c7067284568b3d1b765d50c28a886444b6",
    "synth_checkpoint_bindings.sha256": "9f2fffaca87d3afe0bb512cb381c72902239a3c57418b95579bafc73cb365f46",
    "synth_checkpoint_bindings.json": "68ab2cf88b4462a574cfff3b4abb6b088ab672402f7533fad622afcbc38eb39d",
    "status.json": "877b0eecf2736cb954aa72b2f37465ca4dd957f08f0587c27f98858e8b508937",
}


def synth_lineage(project: Path, report: Path, attempt: Path) -> dict:
    recovered = not (attempt/'status.json').exists() and (attempt/synth_recovery.RECEIPT).exists()
    closure = synth_recovery.validate_recovery(project,report,attempt) if recovered else None
    status = json.loads((attempt / ('started.json' if recovered else 'status.json')).read_text())
    optimized = status.get('execution_profile') == full_impl.OPTIMIZED_PROFILE
    anchors = SYNTH_ANCHORS
    if optimized:
        expected = full_impl.authorization(ROOT.parent.parent,'synth',attempt,report,full_impl.OPTIMIZED_PROFILE)
        require(json.loads((attempt/'execution_authorization.json').read_text()) == expected and
                status.get('authorization') == full_impl.identity(attempt/'execution_authorization.json'),
                'new E005 synthesis authorization mismatch')
        optimized_anchor = json.loads((attempt/'frozen_synthesis_anchor.json').read_text())
        require(optimized_anchor.get('execution_authorization') == expected and optimized_anchor.get('project') == str(project) and
                optimized_anchor.get('report') == str(report), 'new E005 synthesis anchor binding mismatch')
        anchors = optimized_anchor['anchors']
        expected_names = (set(SYNTH_ANCHORS)-{'status.json'})|{synth_recovery.RECEIPT} if recovered else set(SYNTH_ANCHORS)
        require(set(anchors) == expected_names, 'new E005 anchor file set incomplete')
    for name, digest in anchors.items():
        anchor = (report if name in {"inputs.sha256", "build_identity.txt", "fresh_synth_complete.txt"} else attempt) / name
        require(sha256(anchor) == digest, f"frozen synthesis identity record changed: {anchor}")
    status_id(report / "launcher_status.txt", "synth", project)
    if not recovered:
        require(status["exit_code"] == 0 and status["native_exit_code"] == 0,
                "original synthesis launcher/supervisor did not succeed")
        require(not status["stop_reason"] and not status["owned_survivors"],
                "original synthesis was stopped or retains owned processes")
    rows = input_manifest(report / "inputs.sha256")
    dcps = input_manifest(attempt / "synth_checkpoint_bindings.sha256")
    binding = json.loads((attempt / "synth_checkpoint_bindings.json").read_text())
    require(status.get("stage") == "synth" and status.get("project") == str(project) and
            status.get("report") == str(report) and binding.get("project") == str(project),
            "original synthesis project/report identity mismatch")
    require((len(rows) == optimized_anchor['source_rows'] if optimized else len(rows) == 339) and len(dcps) == 45,
            "incomplete frozen source/checkpoint manifests")
    require(len(binding["run_records"]) == 23 and len(binding["consumed_ip_records"]) == 22,
            "incomplete actual top/OOC checkpoint lineage")
    produced, consumed, names = set(), set(), set()
    for run in binding["run_records"]:
        name = run["run"]
        require(name not in names and (name == "synth_1" or
                (name.startswith("scalellm_vcu118_f05_bd_") and name.endswith("_synth_1"))),
                "duplicate/foreign synthesis run")
        names.add(name)
        directory = project / "scalellm_vcu118_f05.runs" / name
        expected_name = "scalellm_vcu118_f05_bd_wrapper.dcp" if name == "synth_1" else name.removesuffix("_synth_1") + ".dcp"
        require(Path(run["checkpoint"]) == directory / expected_name and
                Path(run["end_receipt"]) == directory / ".vivado.end.rst", "run artifact outside its actual run")
        produced.add(Path(run["checkpoint"]))
        receipt = Path(run["end_receipt"])
        require(receipt.is_file() and not receipt.with_name(".vivado.error.rst").exists(),
                f"missing/failed original synthesis receipt: {receipt}")
        require(Path(run["checkpoint"]) in dcps, "unbound synthesis checkpoint")
    for record in binding["consumed_ip_records"]:
        path = Path(record["path"])
        require(path.is_relative_to(project / "scalellm_vcu118_f05.gen") and path not in consumed and
                record["cell"].startswith("scalellm_vcu118_f05_bd_i/"), "duplicate/foreign consumed checkpoint")
        consumed.add(path)
        matches = [p for p in produced if p.name == path.name]
        require(len(matches) == 1 and dcps.get(path) == dcps[matches[0]], "actual IP read is not its frozen synthesized copy")
    require("synth_1" in names and len(produced) == 23 and len(consumed) == 22 and
            produced.isdisjoint(consumed) and set(dcps) == produced | consumed and
            set(binding["checkpoints"]) == {str(p) for p in dcps}, "DCP manifest is not the complete actual 45-path set")
    for path, digest in dcps.items():
        require(binding["checkpoints"][str(path)]["sha256"] == digest, "DCP binding hash mismatch")
    lineage = {
        "project": str(project), "source_rows": len(rows), "checkpoint_paths": len(dcps),
        "manifest": file_id(report / "inputs.sha256"),
        "identity": file_id(report / "build_identity.txt"),
        "completion": file_id(report / "fresh_synth_complete.txt"),
        "checkpoint_manifest": file_id(attempt / "synth_checkpoint_bindings.sha256"),
        "checkpoint_bindings": file_id(attempt / "synth_checkpoint_bindings.json"),
    }
    if recovered:
        require(optimized, 'only E005 supports independent synthesis supervision recovery')
        lineage['execution_closure'] = file_id(attempt/synth_recovery.RECEIPT)
        lineage['supervision'] = {k:closure[k] for k in ['supervision_continuous','original_supervisor_exit_code',
            'original_leader_wait_exit_code','wrapper_native_exit_code','wrapper_aggregate_exit_code',
            'original_last_resource_utc','adoption_started_utc','resource_statistics_scope']}
    else:
        lineage['managed_status'] = file_id(attempt/'status.json')
    if optimized:
        lineage['execution_authorization'] = expected
        lineage['frozen_synthesis_anchor'] = file_id(attempt/'frozen_synthesis_anchor.json')
    return lineage


def timing_metrics(path: Path) -> dict:
    lines = path.read_text().splitlines()
    for i, line in enumerate(lines):
        if "WNS(ns)" in line and "TNS Failing Endpoints" in line:
            for row in lines[i + 1:i + 6]:
                words = row.split()
                if len(words) != 12:
                    continue
                try:
                    values = [float(x) for x in words]
                except ValueError:
                    continue
                names = ("wns", "tns", "setup_failing_endpoints", "setup_total_endpoints",
                         "whs", "ths", "hold_failing_endpoints", "hold_total_endpoints",
                         "wpws", "tpws", "pw_skew_failing_endpoints", "pw_skew_total_endpoints")
                return dict(zip(names, values))
    raise ValueError(f"missing complete timing summary: {path}")


def timing_verdict(metrics: dict) -> str:
    keys = ("wns", "whs", "wpws", "tns", "ths", "tpws",
            "setup_failing_endpoints", "hold_failing_endpoints", "pw_skew_failing_endpoints")
    if not all(math.isfinite(metrics[x]) for x in keys):
        return "NOT_EVALUABLE"
    return "PASS" if (all(metrics[x] >= 0 for x in keys[:6]) and
                      all(metrics[x] == 0 for x in keys[6:])) else "FAIL"


def cdc_critical_records(path: Path) -> set[tuple[str, str, str, str, str]]:
    from collections import Counter
    lines = path.read_text().splitlines()
    require("CDC Report" in lines, "missing actual CDC report header")
    declared, observed = {}, Counter()
    clocks, result, critical_count = {}, set(), 0
    for line in lines:
        summary = re.match(r"^(CDC-\d+)\s+(Info|Warning|Critical)\s+(\d+)\s", line)
        if summary:
            key = summary.group(1, 2)
            require(key not in declared, "duplicate CDC summary category")
            declared[key] = int(summary.group(3))
        for key in ("Source Clock", "Destination Clock"):
            if line.startswith(key + ":"):
                clocks[key] = line.split(":", 1)[1].strip()
        match = re.match(r"^\s*\d+\s+(CDC-\d+)\s+(Info|Warning|Critical)\s+", line)
        if match:
            require("Source Clock" in clocks and "Destination Clock" in clocks, "CDC detail lacks actual clock group")
            observed[match.group(1, 2)] += 1
            if match.group(2) != "Critical":
                continue
            critical_count += 1
            fields = re.split(r"\s{2,}", line.strip())
            require(len(fields) >= 5, "unparsed critical CDC row")
            result.add((match.group(1), clocks["Source Clock"], clocks["Destination Clock"], fields[-2], fields[-1]))
    require(bool(declared) and bool(observed) and dict(observed) == {k:v for k,v in declared.items() if v} and
            len(result) == critical_count, "CDC report has unparsed/missing/duplicate rows or incomplete summary")
    return result


def opt_reset_cdc_rows() -> set[tuple[str, str, str, str, str]]:
    base='scalellm_vcu118_f05_bd_i/'
    core='clk_out1_scalellm_vcu118_f05_bd_clk_core_0'
    rows=set()
    for d in (0,1):
        clock='mmcm_clkout0'+('_1' if d else '')
        rows.add(('CDC-10',clock,core,base+f'ddr4_{d}/inst/u_ddr4_mem_intfc/u_ddr_cal_top/calDone_gated_reg/C',
                  base+f'core_gate/inst/u_ready{d}_cdc/arststages_ff_reg[0]/CLR'))
        for psr in ('psr0','psr_aclk1'):
            rows.add(('CDC-10',clock,core,base+f'd{d}_gate/inst/u_ready_cdc/arststages_ff_reg[3]/C',
                      base+f'd{d}_smc/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D'))
        rows.add(('CDC-11','xdma_0_axi_aclk',clock,base+'xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/C',
                  base+f'd{d}_gate/inst/u_base_reset_cdc/arststages_ff_reg[0]/CLR'))
    return rows


TARGETED_OPT_REPORT_HASHES = (
    'dd84ac0ca83c91630474d858d153bcbe95f46534829a37cf1721a7a397c0280f',
    'd7a16c3c859a5d5c344eb4d0fbe95731610d01f89206a61d91d3801e139f5930',
    'ed4dd29ec38557bec16e07d8dcdc43ea828ada4a0e55acf24fc4d6dca5834db5',
    '751f9dfc750d24270ed1884bd590bc4d8756aac0bc837317154ea8ddcd0dd4b2')


def auxiliary_cdc_limits(path: Path) -> dict:
    """Classify only four measured OPT auxiliary enumeration caps, retaining raw UNKNOWN."""
    lines=path.read_text().splitlines()
    sentinels=[(i,line) for i,line in enumerate(lines) if line.startswith('TARGETED_CDC_VIOLATIONS_UNKNOWN')]
    if not sentinels:return {'coverage':'not_limited','raw_sentinels':[],'reports':[]}
    pairs=sorted({row[1:3] for row in opt_reset_cdc_rows()})
    require(len(sentinels)==4,'unexpected targeted CDC auxiliary cap set')
    reports=[];union=set()
    for index,((position,line),(source,target),count,digest) in enumerate(zip(sentinels,pairs,(668,668,768,769),TARGETED_OPT_REPORT_HASHES)):
        name=f'm002_changed_reset_opt_{index}'
        report=path.parent/f'cdc_changed_opt_{index}.rpt'
        command=f'report_cdc -from {source} -to {target} -severity Critical -all_checks_per_endpoint -details -name {name} -file {report}'
        require(position>=2 and line==f'TARGETED_CDC_VIOLATIONS_UNKNOWN\t{name}' and
                lines[position-2]==f'TARGETED_CDC_COMMAND\t{source}\t{target}\t{command}' and
                lines[position-1]==f'TARGETED_CDC_VIOLATION_COUNT\t{source}\t{target}\t{count}\tLIMIT=64' and count>64,
                'targeted CDC auxiliary cap command/name/clock/count mismatch')
        require(sha256(report)==digest,'targeted CDC complete report identity changed')
        actual=cdc_critical_records(report)
        expected={row for row in opt_reset_cdc_rows() if row[1:3]==(source,target)}
        require(actual==expected and len(actual)==(3 if index<2 else 1),'targeted CDC complete critical tuples changed')
        union.update(actual);reports.append(file_id(report))
    full=path.parent/'cdc_opt.rpt'
    require(union==opt_reset_cdc_rows() and cdc_critical_records(full)==union,
            'targeted/full CDC complete critical tuple union mismatch')
    return {'coverage':'coverage_limited','scope':'auxiliary get_cdc_violations object properties only; complete Critical reports parsed',
            'raw_sentinels':[line for _,line in sentinels],'reports':reports,'full_report':file_id(full),
            'critical_rows':len(union),'object_counts':[668,668,768,769],'object_limit':64}


def reset_fanout(path: Path, bram_clock_path: Path | None = None) -> dict:
    """Exact UI reset consumers; no vendor-scope or ASYNC_REG-only waiver."""
    counts, endpoints, sources = {}, {}, {}
    issues=[]
    try:auxiliary=auxiliary_cdc_limits(path)
    except Exception as exc:
        auxiliary={'coverage':'unqualified','raw_sentinels':[],'reports':[]}
        issues.append(f'auxiliary CDC cap proof: {type(exc).__name__}: {exc}')
    for line in path.read_text().splitlines():
        f=line.split('\t')
        if ((f[0].endswith('_UNKNOWN') or f[0]=='OBSERVED_SOURCE_SET_UNAVAILABLE') and
                line not in auxiliary['raw_sentinels']):issues.append(line)
        if f[0]=='SOURCE_Q':
            require(len(f)==4 and f[2] not in sources,'malformed/duplicate reset source Q')
            sources[f[2]]=f[1]
        elif f[0] in {'SOURCE_Q_FANOUT_COUNT','HOST_RESET_Q_FANOUT_COUNT','BASE_RESET_Q_FANOUT_COUNT'}:
            key=(f[0].removesuffix('_FANOUT_COUNT'),f[1])
            require(len(f)==4 and key not in counts and f[3]=='LIMIT=8192','malformed/duplicate bounded reset fanout count')
            counts[key]=int(f[2])
        elif f[0] in {'SOURCE_Q_ENDPOINT','HOST_RESET_Q_ENDPOINT','BASE_RESET_Q_ENDPOINT'}:
            require(len(f)==5 and f[4].startswith('CLOCKS='),'malformed actual reset consumer')
            key=(f[0].removesuffix('_ENDPOINT'),f[1])
            entries=endpoints.setdefault(key,{})
            require(f[2] not in entries,'duplicate actual reset consumer')
            entries[f[2]]={'ref':f[3],'clocks':[x.strip('{}') for x in f[4][7:].split()]}
    require(counts and set(counts)==set(endpoints) and all(0 < n <= 8192 and n==len(endpoints[k]) for k,n in counts.items()),
            'incomplete actual reset fanout consumer scope')
    base='scalellm_vcu118_f05_bd_i/'
    bram_clocks={}
    if bram_clock_path and bram_clock_path.is_file():
        for line in bram_clock_path.read_text().splitlines():
            f=line.split('\t')
            require(len(f)==7 and f[0]=='BRAM_PORT_CLOCK' and f[1] not in bram_clocks,'malformed/duplicate actual BRAM port clock')
            clocks=[x.strip('{}') for x in f[5].split()]
            bram_clocks[f[1]]={'ref':f[2],'cell':f[3],'clock_pin':f[4],'clocks':clocks,'is_clock':f[6]}
    bram_endpoints={name:row for (kind,q),rows in endpoints.items() if kind=='BASE_RESET_Q' for name,row in rows.items() if row['ref'] in {'RAMB36E2','RAMB18E2'}}
    if set(bram_clocks)!=set(bram_endpoints):issues.append('missing/foreign actual per-port BRAM clock evidence')
    for name,row in bram_endpoints.items():
        actual=bram_clocks.get(name)
        terminal=name.rsplit('/',1)[-1]
        port,_=bram_write_clock(row['ref'],terminal)
        if (not actual or not port or actual['ref']!=row['ref'] or actual['cell']!=name.rsplit('/',1)[0] or
                actual['clock_pin']!=actual['cell']+'/'+port or actual['is_clock'].lower() not in {'1','true'} or
                len(actual['clocks'])!=1 or not set(actual['clocks'])<=set(row['clocks'])):
            issues.append(f'unknown/conflicting BRAM endpoint clock pin mapping: {name}')
        else:
            row['observed_cell_clocks']=row['clocks'];row['clocks']=actual['clocks']
    user_q=base+'xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/Q'
    require(sources.get(user_q)==user_q.removesuffix('/Q')+'/C','actual XDMA reset launch identity missing')
    entries=endpoints.get(('SOURCE_Q',user_q),{})
    groups={}
    for d,psrs in ((0,('psr_aclk1',)),(1,('psr0','psr_aclk2'))):
        clock='mmcm_clkout0'+('_1' if d else '')
        actual={name:row for name,row in entries.items() if clock in row['clocks']}
        expected={base+f'd{d}_gate/inst/u_base_reset_cdc/arststages_ff_reg[{i}]/CLR':'FDCE' for i in range(4)}
        expected.update({base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D':'FDRE' for psr in psrs})
        if set(actual)!=set(expected) or any(row['ref']!=expected.get(name) or row['clocks']!=[clock] for name,row in actual.items()):
            issues.append(f'XDMA reset exact same-UI branch membership/clock mismatch: {clock}')
        groups[clock]=sorted(actual)
        base_q=base+f'd{d}_gate/inst/u_base_reset_cdc/arststages_ff_reg[3]/Q'
        base_consumers=endpoints.get(('BASE_RESET_Q',base_q),{})
        if not base_consumers:issues.append(f'missing actual base reset output consumers {base_q}')
        cross_domain={base+f'd{d}_smc/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[0]/D'
                      for psr in ('psr0','psr_aclk1')}
        core='clk_out1_scalellm_vcu118_f05_bd_clk_core_0'
        for name,row in base_consumers.items():
            if row['ref'] not in {'FDRE','FDCE','FDPE','RAMB18E2','RAMB36E2'}:
                issues.append(f'base reset output has unclassified primitive consumer: {name}')
                continue
            if row['clocks']==[clock]:continue
            if name not in cross_domain or row != {'ref':'FDRE','clocks':[core]}:
                issues.append(f'base reset output has unclassified asynchronous consumer: {name}')
        for psr in psrs:
            q=base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX/syncstages_ff_reg[3]/Q'
            consumer=base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/lpf_asr_reg/D'
            if endpoints.get(('HOST_RESET_Q',q))!={consumer:{'ref':'FDRE','clocks':[clock]}}:
                issues.append(f'HostSplit exact same-clock local LPF consumer mismatch: {psr}')
    return {'qualified':not issues,'issues':issues,'source':file_id(path),'xdma_ui_branches':groups,
            'bram_port_clock_source':file_id(bram_clock_path) if bram_clock_path and bram_clock_path.is_file() else None,
            'bram_port_clock_endpoints':len(bram_clocks),'auxiliary_cdc_observation':auxiliary,
            'bram_models':list({ref:bram_write_clock(ref,'WEBWE[0]')[1] for ref in {row['ref'] for row in bram_endpoints.values()}}.values()),
            'consumer_counts':{kind+':'+q:counts[kind,q] for kind,q in counts},
            'formal_reset_cdc_safety':'OPEN','scope':'diagnostic only; downstream release/transaction safety remains OPEN'}


def qualified_aux_representatives(actual: set, structure: dict | None, report: Path) -> tuple[set, list]:
    """Only the two proven inputs of each of four exact AUX cones may represent it.

    Actual primitive polarity, complete four-stage chains and bounded Boolean
    cones remain qualified by reset_structure; no source/type/clock/target
    outside those exact graphs is admitted here.
    """
    require(structure and structure.get('qualified') is True, 'new/unclassified critical CDC path: missing actual structural proof')
    verify_reset_proof(structure)
    require(Path(structure['source']['path']).parent==report.parent and
            Path(structure['source']['path']).name=='reset_graph_'+report.stem.removeprefix('cdc_')+'.tsv',
            'new/unclassified critical CDC path: foreign physical graph')
    base='scalellm_vcu118_f05_bd_i/';core='clk_out1_scalellm_vcu118_f05_bd_clk_core_0'
    chains={row['root']:row for row in structure.get('aux_chains',[])}
    require(len(chains)==4, 'new/unclassified critical CDC path: incomplete AUX chains')
    alternatives={}
    for d in (0,1):
        clock='mmcm_clkout0'+('_1' if d else '')
        terms={base+f'd{d}_gate/inst/{kind}/arststages_ff_reg[3]/Q' for kind in ('u_base_reset_cdc','u_ready_cdc')}
        for psr in ('psr0','psr_aclk1'):
            root=base+f'd{d}_smc/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX'
            row=chains.get(root,{})
            require(row.get('stages')==[root+f'/syncstages_ff_reg[{i}]' for i in range(4)] and
                    set(row.get('source_synchronized_terms',[]))==terms and row.get('destination_clock')==core,
                    'new/unclassified critical CDC path: AUX actual chain/dual-source proof changed')
            target=root+'/syncstages_ff_reg[0]/D'
            ready=('CDC-10',clock,core,base+f'd{d}_gate/inst/u_ready_cdc/arststages_ff_reg[3]/C',target)
            other=('CDC-10',clock,core,base+f'd{d}_gate/inst/u_base_reset_cdc/arststages_ff_reg[3]/C',target)
            alternatives[other]=(ready,sorted(terms))
    normalized=set();changes=[]
    canonical=opt_reset_cdc_rows()
    for row in sorted(actual):
        if row in canonical:normalized.add(row)
        elif row in alternatives:
            ready,terms=alternatives[row];normalized.add(ready)
            changes.append({'actual_tuple':list(row),'canonical_tuple':list(ready),'actual_same_cone_data_terms':terms,
                            'scope':'report representative selection only; diagnostic reset/CDC safety remains OPEN'})
        else:raise ValueError('new/unclassified critical CDC path')
    require(len(normalized)==len(actual), 'new/unclassified critical CDC path: duplicate AUX representatives')
    return normalized,changes


def critical_coverage(report: Path, original: Path, structure: dict | None = None, fanout: dict | None = None) -> dict:
    expected = cdc_critical_records(original)
    actual = cdc_critical_records(report)
    require(len(expected) == 6, 'original critical CDC reference changed')
    if actual <= expected:
        return {"known_original": len(expected), "remaining_known": len(actual), "new_critical": 0}
    canonical=opt_reset_cdc_rows()
    representative_changes=[]
    if actual!=canonical:
        require(report.name in {"cdc_place.rpt","cdc_physopt.rpt","cdc_route.rpt"}, "new/unclassified critical CDC path")
        normalized,representative_changes=qualified_aux_representatives(actual,structure,report)
        require(normalized==canonical and len(actual)==8, "new/unclassified critical CDC path")
    require(structure and structure.get('qualified') is True and len(structure.get('host_split_reset_chains',[]))==3 and
            len(structure.get('async_reset_chains',[]))==7 and len(structure.get('aux_chains',[]))==4 and
            len(structure.get('explicit_primitive_exports',[]))==14 and fanout and fanout.get('qualified') is True,
            'exact OPT reset CDC requires actual chain/polarity/HostSplit/fanout diagnostic proof')
    reference=ROOT/'vivado/reports/m002_E002_R003_AT005_opt_recovery_debug_materialized_place_physopt/cdc_opt.rpt'
    require(sha256(reference)=='7451c566ed781bcc67e2bbc5484378980045df170acb9b2ad884a7d20b94ff67' and
            cdc_critical_records(reference)==canonical,'actual OPT critical CDC reference identity changed')
    sources=[file_id(report),file_id(reference),structure['source'],fanout['source']]
    if fanout.get('bram_port_clock_source'):sources.append(fanout['bram_port_clock_source'])
    auxiliary_sources=fanout.get('auxiliary_cdc_observation',{}).get('reports',[])
    sources.extend(auxiliary_sources)
    result={'known_original':6,'remaining_original_identities':len(actual & expected),'classified_opt_reset':8,
            'changed_vs_synthesis':len(actual-expected),'new_critical':0,'classification':'classified_reset_cdc_diagnostic_only',
            'formal_reset_cdc_safety':'OPEN','proof_sources':sources,'auxiliary_cdc_report_sources':auxiliary_sources}
    if representative_changes:result['actual_aux_representative_sources']=representative_changes
    return result


def check_timing_counts(path: Path) -> dict:
    rows = re.findall(r"^\d+\. checking ([a-z_]+) \((\d+)\)", path.read_text(), re.M)
    require(bool(rows), f"missing check_timing categories: {path}")
    return {name: int(count) for name, count in rows}


def timing_objects(path: Path, category: str) -> set[str]:
    lines = path.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if re.match(rf"^\d+\. checking {re.escape(category)} \(", line)]
    require(bool(starts), f"missing check_timing section {category}")
    start = starts[-1]
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^\d+\. checking ", lines[i])), len(lines))
    objects = set()
    for line in lines[start + 1:end]:
        if not line or line[0].isspace() or line.startswith("-"):
            continue
        if category in {"no_input_delay", "no_output_delay"}:
            require(re.fullmatch(r"[A-Za-z_][\w\[\].]*", line) is not None, "unparsed IO timing object")
        else:
            require("/" in line, f"unparsed timing endpoint: {line}")
        require(line not in objects, "duplicate timing endpoint")
        objects.add(line)
    expected = check_timing_counts(path)[category]
    require(len(objects) == expected, f"{category} endpoint count mismatch: {len(objects)} != {expected}")
    return objects


def debug_gap_coverage(path: Path, fanout: set[str], verified: bool) -> bool:
    no_clock = timing_objects(path, "no_clock")
    unconstrained = timing_objects(path, "unconstrained_internal_endpoints")
    pattern = re.compile(r"^scalellm_vcu118_f05_bd_i/ddr4_[01]/inst/u_ddr4_mem_intfc/u_ddr_cal_top/u_ddr_cal/(U_XSDB_SLAVE|u_xsdb_arbiter)/")
    return bool(verified and no_clock and unconstrained and no_clock <= fanout and
                {x.rsplit("/", 1)[0] for x in unconstrained} <= {x.rsplit("/", 1)[0] for x in fanout} and
                all(pattern.match(x) for x in no_clock | unconstrained))


def reset_io_coverage(path: Path) -> dict:
    inputs, outputs = timing_objects(path, "no_input_delay"), timing_objects(path, "no_output_delay")
    require(inputs <= {"pcie_perstn"} and outputs <= {"ddr4_sdram_c1_reset_n", "ddr4_sdram_c2_reset_n"},
            "new/unclassified untimed IO port")
    return {"known_async_reset_inputs": sorted(inputs), "known_ddr_reset_outputs": sorted(outputs)}


def hash_registry(point: str, report: Path) -> tuple[dict, dict]:
    registry = report / f"xdc_registry_{point}.tsv"
    lines = registry.read_text().splitlines()
    require(len(lines) > 1 and lines[0].split("\t") == ["path", "USED_IN", "USED_IN_SYNTHESIS",
        "USED_IN_IMPLEMENTATION", "IS_ENABLED", "SCOPED_TO_REF", "SCOPED_TO_CELLS", "PROCESSING_ORDER", "SHA256"],
        "missing/full XDC metadata header")
    hashed, metadata, hashes = [lines[0]], {}, {}
    for row in lines[1:]:
        cells = row.split("\t")
        require(len(cells) == 9 and cells[0] not in hashes, "malformed/duplicate XDC registry row")
        path = Path(cells[0])
        require(path.is_absolute() and path.is_file(), f"registered XDC missing: {path}")
        cells[-1] = sha256(path)
        hashes[str(path)], metadata[str(path)] = cells[-1], cells[1:-1]
        hashed.append("\t".join(cells))
    (report / f"xdc_registry_{point}_hashed.tsv").write_text("\n".join(hashed) + "\n")
    (report / f"xdc_sources_{point}.sha256").write_text("".join(
        f"{digest}  {name}\n" for name, digest in sorted(hashes.items())))
    return metadata, hashes


def constraint_chain(point: str, report: Path) -> dict:
    import os
    if os.environ.get("HAP_EXECUTION_MODE") == "checkpoint_restored_commands":
        return recovery_constraints(point, report)
    metadata, hashes = hash_registry(point, report)
    registry = report / f"xdc_registry_{point}_hashed.tsv"
    actual = report / f"actual_xdc_reads_{point}.json"
    run_log = Path(os.environ["HAP_PROJECT_DIR"]) / "scalellm_vcu118_f05.runs/impl_1/runme.log"
    records = []
    if point != "project" and run_log.exists():
        for number, line in enumerate(run_log.read_text(errors="replace").splitlines(), 1):
            match = re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?", line)
            if match:
                path = Path(match.group(1))
                hashes[str(path)] = sha256(path)
                records.append({"line": number, "path": str(path), "scope": match.group(2), "sha256": hashes[str(path)]})
    if point == "init":
        require(bool(records), "INIT has no actual constraint read records")
    actual.write_text(json.dumps({"records": records}, indent=2) + "\n")
    previous = {"init": "project", "opt": "init", "debug_materialized": "opt",
                "place": "debug_materialized", "physopt": "place"}.get(point)
    parent = report / f"constraints_{previous}.json" if previous else None
    if point == "route" or (point == "project" and os.environ.get("HAP_STAGE") == "route"):
        parent = Path(os.environ["HAP_PLACE_REPORT_DIR"]) / "constraints_physopt.json"
    if parent:
        old = json.loads(parent.read_text())
        for name, digest in old["hashes"].items():
            require(Path(name).is_file() and sha256(Path(name)) == digest, f"effective/candidate constraint changed: {name}")
        for name, properties in old["metadata"].items():
            require(name in metadata and metadata[name] == properties, f"XDC missing/scope/order/USED_IN changed: {name}")
        additions = set(hashes) - set(old["hashes"])
        if point != "init":
            allowed_path = report / f"tool_debug_xdc_{point}.txt"
            allowed = set(allowed_path.read_text().splitlines()) if allowed_path.exists() else set()
            require(not additions or (point == "debug_materialized" and additions <= allowed), f"unclassified new constraints: {sorted(additions)}")
        hashes = {**old["hashes"], **hashes}
    result = {"phase": point, "hashes": hashes, "metadata": metadata,
              "registry": file_id(registry), "actual_reads": file_id(actual),
              "parent": file_id(parent) if parent else None}
    (report / f"constraints_{point}.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def placement_coverage(counts: dict, blackboxes: int) -> bool:
    return blackboxes == 0 and all(counts.get(x, -1) == 0 for x in (
        "no_clock", "unconstrained_internal_endpoints", "multiple_clock", "generated_clocks", "loops", "pulse_width_clock"))


def utilization_metrics(path: Path) -> dict:
    result = {}
    for line in path.read_text().splitlines():
        cells = [x.strip() for x in line.split("|")[1:-1]]
        if len(cells) == 6 and cells[0].rstrip("*") in {"CLB LUTs", "CLB Registers", "DSPs", "Block RAM Tile", "URAM"}:
            result[cells[0].rstrip("*")] = {"used": float(cells[1]), "available": float(cells[4]), "percent": float(cells[5])}
    require(len(result) == 5, "incomplete actual resource capacity report")
    require(all(x["used"] <= x["available"] for x in result.values()), "aggregate device capacity exceeded")
    return result


@cache
def primitive_defaults(ref: str) -> dict:
    path=PRIMITIVE_MODEL_ROOT/(ref+'.v')
    require(ref in PRIMITIVE_MODEL_HASHES and sha256(path)==PRIMITIVE_MODEL_HASHES[ref], 'same-version primitive model identity changed')
    text=path.read_text()
    match=re.search(r'\bmodule\s+'+ref+r'\s*#\s*\((.*?)\)\s*\(',text,re.S)
    require(match is not None,'primitive model parameter declaration missing')
    values=dict(re.findall(r'parameter\s+\[0:0\]\s+(\w+)\s*=\s*(1\x27b[01])',match.group(1)))
    expected={'INIT','IS_C_INVERTED','IS_D_INVERTED','IS_CLR_INVERTED' if ref=='FDCE' else 'IS_R_INVERTED'}
    require(set(values)==expected and all(v=="1'b0" for v in values.values()), 'unknown primitive model defaults')
    return {'parameters':values,'identity':file_id(path),'tool_scope':'Vivado2025.2 build6299465 UNISIM declaration'}


def primitive_overrides(path: Path, scope: str) -> dict:
    text = path.read_text()
    require(not re.search(r'\bdefparam\b',text),'unknown defparam in actual reset primitive export')
    cells = {}
    for match in re.finditer(r'\b(FDCE|FDRE)\s*#\s*\((.*?)\)\s+(\\\S+|[A-Za-z_]\w*(?:\[\d+\])?)\s*\(', text, re.S):
        ref, body, instance = match.groups()
        name = scope + '/' + instance.removeprefix('\\')
        require(name not in cells, 'duplicate exported reset primitive')
        records=re.findall(r'\.(\w+)\s*\(\s*([^()]*)\s*\)',body)
        residue=re.sub(r'\.(\w+)\s*\(\s*([^()]*)\s*\)','',body).strip(' \t\r\n,')
        parameters={k:v.strip() for k,v in records}
        model=primitive_defaults(ref)
        require(not residue and len(records)==len(parameters) and set(parameters)<=set(model['parameters']),
                'unknown/duplicate actual reset primitive parameter override')
        require(all(v in {"1'b0","1'b1","1'h0","1'h1",'0','1'} for v in parameters.values()),
                'unknown actual reset primitive parameter expression')
        effective={**model['parameters'],**parameters}
        cells[name] = {'ref':ref, **effective,
            'parameter_sources':{k:'explicit_override' if k in parameters else 'model_default' for k in effective},
            'default_model':model['identity']}
    require(len(cells) == 4, 'bounded reset block export must contain exactly four actual primitives')
    return cells


def reset_structure(path: Path) -> dict:
    """Bounded primitive/connectivity proof. Unknown structures remain a gate failure."""
    import itertools
    cells, pins, receivers, outputs, gate_inputs, targets = {}, {}, [], {}, {}, set()
    cell_properties, pin_properties, netlist_scopes = {}, {}, []
    for row in path.read_text().splitlines():
        f = row.split("\t")
        if f[0] == "CELL":
            require(len(f) >= 5 and f[1] not in cells, "duplicate/malformed structural cell")
            cells[f[1]] = {"ref": f[2], "init": f[3], "async": f[4], **dict(x.split("=",1) for x in f[5:])}
        elif f[0] == "PIN":
            require(len(f) == 7 and f[1] not in pins, "duplicate/malformed structural pin")
            pins[f[1]] = {"refpin": f[2], "direction": f[3], "nets": f[4].split(),
                          "clocks": f[5].split(), "drivers": [x.strip("{}") for x in f[6].split()]}
        elif f[0] == "TARGET":
            targets.add(f[1])
        elif f[0] == "IO_RECEIVER":
            receivers.append(f[1:])
        elif f[0] == "IO_OUTPUT":
            outputs[f[1]] = [x.strip("{}") for x in f[2].split()]
        elif f[0] == "GATE_INPUT":
            gate_inputs[f[1]] = [x.strip("{}") for x in f[2].split()]
        elif f[0] == 'CELL_PROPERTY':
            cell_properties.setdefault(f[1], {})[f[2]] = f[3]
        elif f[0] == 'PIN_PROPERTY':
            pin_properties.setdefault(f[1], {})[f[2]] = f[3]
        elif f[0] == 'NETLIST_SCOPE':
            netlist_scopes.append((f[1], Path(f[2])))
    raw_gate_inputs={key:list(value) for key,value in gate_inputs.items()}
    source_normalization=[]
    for key,starts in gate_inputs.items():
        normalized=[]
        for pin in starts:
            cell,terminal=pin.rsplit('/',1)
            q=cell+'/Q'
            if terminal=='C' and cells.get(cell,{}).get('ref') in {'FDCE','FDRE','FDPE'} and q in pins and pins[q]['direction']=='OUT' and pins.get(pin,{}).get('clocks'):
                normalized.append(q);source_normalization.append({'gate_input':key,'reported_launch_clock_pin':pin,'actual_data_q':q})
            else:normalized.append(pin)
        gate_inputs[key]=normalized
    issues, chains, aux, host = [], [], [], []
    exported, exports = {}, []
    for scope, netlist in netlist_scopes:
        require(netlist.parent == path.parent, 'reset primitive export outside current stage reports')
        values = primitive_overrides(netlist, scope)
        require(not set(values) & set(exported), 'overlapping reset primitive export scopes')
        exported.update(values)
        exports.append({'scope':scope, 'netlist':file_id(netlist), 'effective_parameters':values,
                        'primitive_models':list({value['default_model']['path']:value['default_model'] for value in values.values()}.values())})
    def check(ok, message):
        if not ok:
            issues.append(message)
    def same(a, b):
        return bool(set(pins.get(a, {}).get("nets", [])) & set(pins.get(b, {}).get("nets", [])))
    def init_one(text):
        return text.lower() in {"1", "1'b1", "1'h1"}
    def inversion(cell, terminal):
        property = f'IS_{terminal}_INVERTED'
        parameters = {**cells.get(cell, {}), **cell_properties.get(cell, {})}
        values = [parameters.get(property), parameters.get('CONFIG.'+property),
                  pin_properties.get(cell+'/'+terminal, {}).get('IS_INVERTED'), exported.get(cell,{}).get(property)]
        if cell in exported:
            check(exported[cell]['ref'] == cells[cell]['ref'] and exported[cell].get('INIT') == cells[cell]['init'],
                  f'actual primitive export REF/INIT mismatch {cell}')
        bits = []
        for value in values:
            if value in (None, ''):
                continue
            value = value.lower()
            if value in {'0','false',"1'b0","1'h0"}: bits.append(False)
            elif value in {'1','true',"1'b1","1'h1"}: bits.append(True)
            else: issues.append(f'unparsed actual inversion {cell}/{terminal}={value}')
        check(bool(bits) and len(set(bits)) == 1, f'missing/conflicting actual inversion {cell}/{terminal}')
        return bits[0] if bits else None
    def evaluate(pin, symbols, seen=frozenset()):
        if pin in symbols:
            return symbols[pin]
        for symbolic_pin, value in symbols.items():
            if same(pin, symbolic_pin):
                return value
        require(pin not in seen and pin in pins, f"unresolved/cyclic logic pin {pin}")
        seen = seen | {pin}
        cell, refpin = pin.rsplit("/", 1)
        obj = cells.get(cell, {})
        ref = obj.get("ref", "")
        if pins[pin]["direction"] == "IN":
            drivers = pins[pin]["drivers"]
            require(len(drivers) == 1, f"nonunique/missing driver for {pin}: {drivers}")
            return evaluate(drivers[0], symbols, seen)
        if ref in {"VCC", "GND"}:
            return ref == "VCC"
        if re.fullmatch(r"LUT[1-6]", ref) and refpin == "O":
            n = int(ref[-1])
            value = obj["init"].lower()
            match = re.fullmatch(r"(?:\d+)'h([0-9a-f]+)", value)
            require(match is not None, f"unparsed LUT INIT {value}")
            address = sum(int(evaluate(f"{cell}/I{i}", symbols, seen)) << i for i in range(n))
            return bool((int(match.group(1), 16) >> address) & 1)
        if ref in {"IBUF", "OBUF", "BUF", "BUFG", "BUFGCE"} and refpin == "O":
            return evaluate(cell + "/I", symbols, seen)
        raise ValueError(f"unclassified logic primitive {cell} {ref}/{refpin}")
    def constant(pin, expected):
        try:
            return evaluate(pin, {}) == expected
        except ValueError:
            return False
    def function(pin, symbols, expected):
        try:
            for values in itertools.product((False, True), repeat=len(symbols)):
                if evaluate(pin, dict(zip(symbols, values))) != expected(values):
                    return False
            return True
        except ValueError as exc:
            issues.append(str(exc))
            return False
    base = "scalellm_vcu118_f05_bd_i/"
    core_clock = "clk_out1_scalellm_vcu118_f05_bd_clk_core_0"
    groups = [("core_gate", "u_base_reset_cdc", core_clock),
              ("core_gate", "u_ready0_cdc", core_clock), ("core_gate", "u_ready1_cdc", core_clock)]
    for d in (0, 1):
        groups.extend((f"d{d}_gate", x, "mmcm_clkout0" + ("_1" if d else ""))
                      for x in ("u_base_reset_cdc", "u_ready_cdc"))
    for gate, module, clock in groups:
        root = f"{base}{gate}/inst/{module}"
        stages = [f"{root}/arststages_ff_reg[{i}]" for i in range(4)]
        for i, cell in enumerate(stages):
            obj = cells.get(cell, {})
            check(obj.get("ref") == "FDCE" and init_one(obj.get("init", "")) and
                  obj.get("async", "").lower() in {"1", "true"}, f"async reset stage primitive/INIT/ASYNC_REG {cell}")
            check(pins.get(cell + "/C", {}).get("clocks") == [clock] and inversion(cell, 'C') is False, f"async reset destination clock/edge {cell}")
            check(inversion(cell, 'D') is False, f"async reset data polarity {cell}")
            check(constant(cell + "/CE", True), f"async reset CE {cell}")
            check(constant(cell + "/D", True) if i == 0 else same(cell + "/D", stages[i-1] + "/Q"), f"async reset shift connectivity {cell}")
            check(same(cell + "/CLR", stages[0] + "/CLR"), f"async reset common clear {cell}")
            check(inversion(cell, 'CLR') == inversion(stages[0], 'CLR'),
                  f"async reset per-stage clear polarity {cell}")
        input_name = "base_aresetn" if module == "u_base_reset_cdc" else (
            "async_ready" + module.removeprefix("u_ready").removesuffix("_cdc"))
        symbolic_pin = base + f"{gate}/inst/{input_name}"
                # Native primitive input inversion is part of the actual polarity.
        inverted = inversion(stages[0], 'CLR')
        user_q=base+'xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/Q'
        from_user_reset=gate in {'d0_gate','d1_gate'} and module=='u_base_reset_cdc' and gate_inputs.get(symbolic_pin)==[user_q]
        if from_user_reset:
            # OPT may fold the XDMA output inversion and reset_pol inversion
            # across stale hierarchy pins. Actual launch Q is active high.
            check(function(stages[0]+'/CLR',[user_q],lambda v:not v[0] if inverted else v[0]),f'actual XDMA active-high assertion cone {root}')
        else:
            check(function(stages[0] + "/CLR", [symbolic_pin], lambda v: v[0] if inverted else not v[0]), f"async assertion polarity/cone {root}")
        chains.append({"root": root, "stages": stages, "clock": clock, "source": symbolic_pin,
                       'physical_assertion_source':user_q if from_user_reset else symbolic_pin,
                       'physical_asserted_level':1 if from_user_reset else 0})
    # All known critical CDC receivers are exactly these two ready clears and four AUX inputs.
    expected_targets = {base + f"core_gate/inst/u_ready{d}_cdc/arststages_ff_reg[0]/CLR" for d in (0, 1)}
    for d in (0, 1):
        gate_symbols = [base + f"d{d}_gate/inst/{module}/arststages_ff_reg[3]/Q" for module in ("u_base_reset_cdc", "u_ready_cdc")]
        for psr in ("psr0", "psr_aclk1"):
            root = base + f"d{d}_smc/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX"
            stages = [f"{root}/syncstages_ff_reg[{i}]" for i in range(4)]
            expected_targets.add(stages[0] + "/D")
            for i, cell in enumerate(stages):
                obj = cells.get(cell, {})
                check(obj.get("ref") == "FDRE" and obj.get('init','').lower() in {'0',"1'b0","1'h0"} and
                      obj.get("async", "").lower() in {"true", "1"}, f"AUX stage primitive/INIT0/ASYNC_REG {cell}")
                check(pins.get(cell + "/C", {}).get("clocks") == [core_clock], f"AUX destination clock {cell}")
                check(all(inversion(cell, pin) is False for pin in ('C','D','R')), f"AUX clock/data/reset polarity {cell}")
                check(constant(cell + "/CE", True) and constant(cell + "/R", False), f"AUX CE/reset {cell}")
                if i:
                    check(same(cell + "/D", stages[i-1] + "/Q"), f"AUX shift connectivity {cell}")
            check(function(stages[0] + "/D", gate_symbols, lambda v: not all(v)), f"AUX active-low synchronized gate polarity/cone {root}")
            aux.append({"root": root, "stages": stages, "source_synchronized_terms": gate_symbols, "destination_clock": core_clock})
    check(targets == expected_targets and len(targets) == 6, "exact six known CDC targets missing/foreign")
    # The source qualifier's actual fan-in is retained, not inferred from a name.
    for d in (0, 1):
        key = base + f"core_gate/inst/async_ready{d}"
        starts = gate_inputs.get(key, [])
        check(bool(starts) and all(x.startswith(base + f"ddr4_{d}/") for x in starts) and
              any("div_clk_rst_r1_reg/" in x for x in starts) and
              any(x.endswith('/calDone_gated_reg/Q') for x in starts), f"MIG calibration/reset source qualifiers {key}")
        if len(starts) == 2:
            reset = next((i for i, x in enumerate(starts) if "div_clk_rst_r1_reg/" in x), None)
            check(reset is not None and function(key, starts, lambda v: v[1-reset] and not v[reset]), f"MIG calib && !ui_reset logic {key}")
        else:
            check(False, f"MIG source qualifier terminal count {key}")
        check(same(key, base + f"d{d}_gate/inst/async_ready"), f"core/DDR ready qualifier source identity d{d}")
    user_q = base+'xdma_0/inst/pcie4_ip_i/inst/user_reset_reg/Q'
    for psr,clock in (('psr_aclk1','mmcm_clkout0'),('psr0','mmcm_clkout0_1'),('psr_aclk2','mmcm_clkout0_1')):
        root = base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/ACTIVE_LOW_AUX.ACT_LO_AUX'
        stages = [f'{root}/syncstages_ff_reg[{i}]' for i in range(4)]
        if not any(name in cells for name in stages):continue
        for i,cell in enumerate(stages):
            obj=cells.get(cell,{})
            check(obj.get('ref')=='FDRE' and obj.get('init','').lower() in {'0',"1'b0","1'h0"} and
                  obj.get('async','').lower() in {'true','1'},f'HostSplit actual FDRE/INIT0/ASYNC_REG {cell}')
            check(pins.get(cell+'/C',{}).get('clocks') == [clock] and
                  all(inversion(cell,pin) is False for pin in ('C','D','R')),f'HostSplit clock/effective polarity {cell}')
            check(constant(cell+'/CE',True) and constant(cell+'/R',False),f'HostSplit CE/reset {cell}')
            check(function(cell+'/D',[user_q],lambda v:v[0]) if not i else same(cell+'/D',stages[i-1]+'/Q'),
                  f'HostSplit source double inversion/shift connectivity {cell}')
        consumer=base+f'host_split/inst/clk_map/{psr}/U0/EXT_LPF/lpf_asr_reg'
        check(cells.get(consumer,{}).get('ref')=='FDRE' and pins.get(consumer+'/C',{}).get('clocks')==[clock] and
              same(consumer+'/D',stages[-1]+'/Q'),f'HostSplit exact local LPF consumer {consumer}')
        host.append({'root':root,'stages':stages,'clock':clock,'effective_init':0,'input_source':user_q,'consumer':consumer+'/D'})
    check(bool(receivers), "no external PCIe reset receiver evidence")
    for port, pin, ref in receivers:
        cell, terminal = pin.rsplit("/", 1)
        known_sync = (terminal == "D" and "syncstages_ff_reg[0]" in cell and
                      any(cell.startswith(base + x + "/") for x in ("rst_core", "rst_ddr0", "rst_ddr1")))
        known_vendor = cell.startswith(base + "xdma_0/") and (terminal in {"CLR", "PRE", "R", "RST", "SYSRST", "SYSRSTN", "RSTN", "GTRXRESET", "GTTXRESET"} or
                      (terminal == "D" and ("sync" in cell.lower() or "reset" in cell.lower() or "rst" in cell.lower())))
        check(port == "pcie_perstn" and (known_sync or known_vendor), f"unclassified PCIe reset receiver {pin} {ref}")
    for d in (0, 1):
        port = f"ddr4_sdram_c{d+1}_reset_n"
        starts = outputs.get(port, [])
        check(bool(starts) and all(x.startswith(base + f"ddr4_{d}/") for x in starts), f"external DDR reset actual MIG driver {port}")
    return {"qualified": not issues, "issues": issues, "async_reset_chains": chains, "aux_chains": aux,
            "critical_targets": sorted(targets), "gate_source_startpoints": gate_inputs,
            "reported_gate_startpoints":raw_gate_inputs,"launch_clock_to_data_q":source_normalization,
            "pcie_reset_receivers": receivers, "ddr_reset_output_startpoints": outputs,
            "explicit_primitive_exports": exports,
            "host_split_reset_chains":host,
            "assumptions": ["MIG calibration and UI reset are reset-level qualifiers; no data protocol waiver",
                            "external reset IO classification is diagnostic; board reset electrical/timing signoff remains OPEN"],
            "source": file_id(path)}


def checkpoint_package(path: Path) -> dict:
    import hashlib
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as archive:
        raw=archive.read('dcp.xml')
    root=ET.fromstring(raw)
    values={node.tag:node.get('Name') for node in root}
    expected={'Part':'xcvu9p-flga2104-2L-e','Top':'scalellm_vcu118_f05_bd_wrapper',
              'BoardPart':'xilinx.com:vcu118:part0:2.0','BUILD_NUMBER':'6299465','PRODUCT':'Vivado v2025.2 (64-bit)'}
    require(root.tag=='Checkpoint' and all(values.get(k)==v for k,v in expected.items()), 'checkpoint package part/top/board/tool identity mismatch')
    return {**expected,'xml_sha256':hashlib.sha256(raw).hexdigest()}


def recovery_parent(source: Path, project: Path, lineage: dict, report: Path) -> dict:
    """Bind a failed POST's genuine project-init checkpoint, never its success."""
    require(source.is_relative_to(ROOT / 'vivado/reports') and project.is_relative_to(ROOT / 'vivado/project'), 'foreign checkpoint recovery root')
    command = json.loads((source / 'command.json').read_text())
    attempt = Path(command['managed_attempt'])
    status = json.loads((attempt / 'status.json').read_text())
    require(status['project'] == str(project) and status['report'] == str(source) and status['stage'] == 'place' and
            status['exit_code'] == 1 and status['native_exit_code'] == 1 and not status['stop_reason'] and
            not status['owned_survivors'], 'recovery parent is not this completed failed project-init attempt')
    launcher = key_values(source / 'launcher_status.txt')
    require(launcher['exit_code'] == '1' and launcher['native_exit_code'] == '1' and launcher['project'] == str(project),
            'recovery original launcher mismatch')
    require(command['synthesis'] == lineage, 'recovery synthesis lineage changed')
    validate_stage_archive(source, file_id(source / 'stage_inputs.sha256'), file_id(source / 'archived_sources.sha256'))
    result = key_values(source / 'init_result.txt')
    require(result['completed'] == '0' and result['phase'] == 'init', 'recovery must not reinterpret failed INIT as PASS')
    log = source / 'implementation_run.log'
    text = log.read_text(errors='replace')
    checkpoint = file_id(source / 'init.dcp')
    package = checkpoint_package(source / 'init.dcp')
    require('link_design completed successfully' in text and f"The checkpoint '{checkpoint['path']}' has been generated" in text and
            'source ' in text and 'm002_diagnostic_init_post.tcl' in text and
            'M002_DIAGNOSTIC_STEP_COMPLETED init' not in text and '\nCommand: opt_design' not in text,
            'checkpoint is not the actually generated project-init-before-opt state')
    records = []
    registry = source / 'xdc_registry_project_hashed.tsv'
    rows = registry.read_text().splitlines()
    require(len(rows) == 163, 'recovery candidate project XDC registry must contain all 162 files')
    metadata, hashes = {}, {}
    for row in rows[1:]:
        f = row.split('\t')
        require(len(f) == 9 and f[0] not in metadata and sha256(Path(f[0])) == f[-1], 'recovery registered XDC changed/duplicated')
        metadata[f[0]], hashes[f[0]] = f[1:-1], f[-1]
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?", line)
        if match:
            path = Path(match.group(1)); digest = sha256(path)
            require(str(path) not in hashes or hashes[str(path)] == digest, 'recovery loaded XDC changed')
            hashes[str(path)] = digest
            records.append(dict(line=number, path=str(path), scope=match.group(2), sha256=digest))
    require(bool(records), 'recovery has no original actual XDC parse order/scope')
    original = {
        'phase': 'project_init_after_link_before_opt', 'original_execution_state': 'failed_post_probe',
        'original_impl_run_remains': 'FAIL', 'checkpoint': checkpoint, 'checkpoint_package':package,
        'status': file_id(attempt / 'status.json'), 'launcher': file_id(source / 'launcher_status.txt'),
        'child_log': file_id(log), 'command': file_id(source / 'command.json'),
        'stage_inputs': file_id(source / 'stage_inputs.sha256'), 'archive': file_id(source / 'archived_sources.sha256'),
        'implementation_settings': file_id(source / 'implementation_settings.txt'),
        'effective_build_identity': file_id(source / 'effective_build_identity.txt'),
        'source_registry': file_id(registry), 'source_metadata': metadata,
        'hashes': hashes, 'actual_reads': records, 'synthesis': lineage,
        'inherited_reports': {n: file_id(source / n) for n in ('timing_init.rpt','utilization_init.rpt','drc_init.rpt','reset_register_probe_init.tsv')},
        'constraint_mode': 'embedded_checkpoint_inherited',
        'hash_observation': '162 source hashes verified against pre-link registry; actual read sources captured before this continuation',
    }
    (report / 'recovery_parent.json').write_text(json.dumps(original, indent=2) + '\n')
    return original


def generated_phy_parent(attempt: Path, *, fresh_project: Path | None = None, create_terminal_observation: bool = False) -> dict:
    evidence = attempt/'generated_phy_evidence.json'
    value = json.loads(evidence.read_text())
    archive = attempt/'generated_phy_snapshot'
    require(Path(value['archive_root']) == archive and value.get('cache_miss_count') == 2 and
            value.get('actual_synth_success_count') == 2, 'missing bounded actual MIG PHY generation evidence')
    records = {Path(row['source_path']):row for row in value['files']}
    require(len(records) == len(value['files']) and set(input_manifest(attempt/'generated_phy_snapshot.sha256')) ==
            {Path(row['path']) for row in records.values()}, 'incomplete actual MIG PHY source archive')
    for row in records.values():
        require(Path(row['path']).is_relative_to(archive), 'foreign actual MIG PHY archive source')
        verify_identity({k:row[k] for k in ('path','bytes','sha256')})
    original = Path(value['source_root'])
    log = Path(records[original/'vivado.log']['path']).read_text()
    require(log.count('DBG: no cache hit, so run synth') == 2 and log.count('synth_design completed successfully') == 2 and
            'Exiting Vivado' in log, 'MIG PHY no-cache-hit/current synthesis proof incomplete')
    worker_reads = []
    for number,line in enumerate(log.splitlines(),1):
        match = re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?",line)
        if match:
            name = Path(match.group(1))
            require(name in records, 'actual PHY worker XDC read missing retained bytes')
            row = records[name]
            worker_reads.append({'line':number,'path':str(name),'scope':match.group(2),
                                 'retained_source':{k:v for k,v in row.items() if k != 'source_path'}})
    require(len(worker_reads) == 2, 'incomplete bounded actual PHY worker constraint reads')
    disabled_cache = (fresh_opt.qualify_disabled_phy_cache(sys.modules[__name__], attempt, value, records, original, fresh_project, create_observation=create_terminal_observation)
                      if fresh_project is not None else None)
    outputs = {}
    for d in (0,1):
        module = f'scalellm_vcu118_f05_bd_ddr4_{d}_0_phy'
        produced = records[original/(module+'.dcp')]
        output = records[original/'out'/(module+'.0')/'result.dcp']
        cached = [row for p,row in records.items() if p.is_relative_to(original/'.cache/ip') and p.name == module+'.dcp']
        if disabled_cache:
            require(not cached and produced['sha256'] == output['sha256'], 'fresh disabled-cache produced/result PHY mismatch')
            pairs = (('produced',produced),('output',output))
        else:
            require(len(cached) == 1 and produced['sha256'] == output['sha256'] == cached[0]['sha256'],
                    'MIG PHY generated/actual output/post-synthesis cache bytes differ')
            pairs = (('produced',produced),('output',output),('cache_written_after_synthesis',cached[0]))
        outputs[module] = {k:{a:b for a,b in row.items() if a != 'source_path'} for k,row in pairs}
    return {'evidence':file_id(evidence),'manifest':file_id(attempt/'generated_phy_snapshot.sha256'),
            'cache_miss_count':2,'outputs':outputs,'worker_actual_xdc_reads':worker_reads,
            **({'fresh_disabled_cache_qualification':disabled_cache} if disabled_cache else {}),
            'main_generated_xdc_candidates':{str(p):{k:v for k,v in row.items() if k != 'source_path'} for p,row in records.items()
                if p.is_relative_to(original/'out') and p.suffix == '.xdc' and row['bytes'] > 0},
            'scope':'actual OPT-generated PHY; separate worker OOC constraints and original 45 synthesis DCP paths; not a claim about main-design imported constraint coverage'}


def generated_debug_parent(attempt: Path) -> dict:
    evidence = attempt/'generated_debug_evidence.json'
    value = json.loads(evidence.read_text())
    archive = attempt/'generated_debug_snapshot';original=Path(value['source_root'])
    require(Path(value['archive_root']) == archive and value.get('module') == 'dbg_hub' and
            value.get('ipdef') == 'xilinx.com:ip:xsdbm:3.0' and value.get('main_core_cell') == 'dbg_hub_CV' and
            value.get('generation_phase') == 'opt_design_phase_1.1.2', 'foreign generated debug source ownership')
    records={Path(row['source_path']):row for row in value['files']}
    require(len(records) == len(value['files']) and set(input_manifest(attempt/'generated_debug_snapshot.sha256')) ==
            {Path(row['path']) for row in records.values()}, 'incomplete actual debug generation archive')
    for row in records.values():
        require(Path(row['path']).is_relative_to(archive), 'foreign generated debug archive source')
        verify_identity({k:row[k] for k in ('path','bytes','sha256')})
    script=records[original/'dbg_hub_CV.0/out/get_cs_ip.tcl']
    text=Path(script['path']).read_text()
    require('set ip_vlnv xilinx.com:ip:xsdbm:3.0' in text and 'set ip_module_name dbg_hub' in text and
            f'set output_dcp {original}/dbg_hub_CV.0/out/result.dcp' in text, 'generated debug script/core/output association mismatch')
    worker=records[original/'dc_drv.0/vivado.log']
    log=Path(worker['path']).read_text()
    require('synth_design completed successfully' in log and 'Exiting Vivado' in log, 'actual debug worker synthesis incomplete')
    return {'evidence':file_id(evidence),'manifest':file_id(attempt/'generated_debug_snapshot.sha256'),
            'ownership':{'module':'dbg_hub','ipdef':'xilinx.com:ip:xsdbm:3.0','main_core_cell':'dbg_hub_CV','phase':'actual_opt_core_generation'},
            'generated_dcp':{k:v for k,v in records[original/'dbg_hub_CV.0/out/result.dcp'].items() if k != 'source_path'},
            'main_generated_xdc_candidates':{str(p):{k:v for k,v in row.items() if k != 'source_path'} for p,row in records.items()
                if p.is_relative_to(original/'dbg_hub_CV.0/out') and p.suffix == '.xdc'},
            'worker_actual_xdc_reads':value['worker_actual_xdc_reads'],'worker_read_bytes_limit':value['worker_read_bytes_limit'],
            'scope':'actual OPT-generated hub; generated main-source candidates retained; worker path/scope records do not imply missing original bytes were measured'}


def controlled_stop_reap(source: Path, status_path: Path, status: dict, stop: dict) -> dict:
    """Qualify only this intentional stop, preserving its pre-reap status."""
    attempt = status_path.parent
    receipt_path = attempt/'post_termination_verification.json'
    require(receipt_path.is_file(), 'controlled OPT stop lacks post-reap verification')
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get('original_status') == file_id(status_path) and
            receipt.get('original_status_preserved') is True and
            receipt.get('original_reported_survivors') == status['owned_survivors'] and
            status['owned_survivors'] in ([], [status['leader_pid']]) and
            receipt.get('leader_pid') == status['leader_pid'] and
            receipt.get('supervisor_pid') == status['supervisor_pid'] and
            receipt.get('owned_survivors_after_reap') == [],
            'controlled OPT post-reap status/survivor identity mismatch')
    require(dt.datetime.fromisoformat(receipt['observed_utc']) >= dt.datetime.fromisoformat(status['ended_utc']),
            'controlled OPT reap observation predates termination')
    tracked = {}
    resources = attempt/'resources.jsonl'
    for line in resources.read_text().splitlines():
        for pid, row in json.loads(line)['processes'].items():
            pid = int(pid)
            ticks = row['start_ticks']
            require(pid not in tracked or tracked[pid] == ticks, 'ambiguous controlled OPT PID identity')
            tracked[pid] = ticks
    checks = receipt.get('checks', [])
    require(tracked and receipt.get('tracked_pid_count') == len(tracked) == len(checks) and
            len({row['pid'] for row in checks}) == len(checks) and
            {row['pid']:row['expected_start_ticks'] for row in checks} == tracked and
            all(row.get('state') == 'not_present' for row in checks) and
            tracked.get(status['leader_pid']) == stop.get('leader_identity', {}).get('start_ticks'),
            'controlled OPT reap receipt does not cover exact tracked PID identities')
    for pid, ticks in tracked.items():
        try:
            raw = Path(f'/proc/{pid}/stat').read_text()
        except (FileNotFoundError, ProcessLookupError):
            continue
        fields = raw[raw.rindex(')') + 2:].split()
        require(int(fields[19]) != ticks, f'controlled OPT owned PID identity still present: {pid}')
    frozen = receipt.get('log_freeze', {})
    require(frozen.get('path') == str(source/'implementation_run.log') and
            frozen.get('source') == str(source/'vivado.log'), 'controlled OPT frozen log path mismatch')
    identity = {k:frozen[k] for k in ('path','bytes','sha256')}
    verify_identity(identity)
    require(sha256(source/'vivado.log') == identity['sha256'], 'controlled OPT frozen log differs from final child log')
    return {'post_termination':file_id(receipt_path), 'resource_samples':file_id(resources), 'frozen_child_log':identity}


def recovery_opt_parent(source: Path, project: Path, lineage: dict, report: Path, *, _seen: tuple = (), _write: bool = True) -> dict:
    """Resume exactly the generated post-OPT/pre-debug state of a failed POST."""
    require(source.is_relative_to(ROOT / 'vivado/reports') and project.is_relative_to(ROOT / 'vivado/project'), 'foreign OPT recovery root')
    require(source not in _seen and len(_seen) < 8, 'cyclic/unbounded OPT recovery ancestry')
    command = json.loads((source / 'command.json').read_text())
    if command.get('execution_mode') == 'project_runs':
        return fresh_opt.qualify_native_project(sys.modules[__name__], source, project, lineage, report, write=_write)
    status_path = Path(command['managed_attempt']) / 'status.json'
    status = json.loads(status_path.read_text())
    stop_path = Path(command['managed_attempt'])/'controlled_stop_request.json'
    controlled = stop_path.is_file()
    reap = {}
    if controlled:
        stop = json.loads(stop_path.read_text())
        require(stop.get('reason') == 'missing_explicit_pre_place_debug_implementation' and
                stop.get('supervisor_pid') == status.get('supervisor_pid') and stop.get('leader_pid') == status.get('leader_pid') and
                stop.get('report') == str(source) and status['exit_code'] == 125 and
                str(status['stop_reason']).startswith('supervisor_exception:KeyboardInterrupt:signal 15') and
                status['native_exit_code'] != 0, 'invalid bounded intentional OPT stop parent')
        require(set(stop.get('opt_proof',{})) == {'opt_command_result.txt','opt.dcp','opt_result.txt','check_timing_opt.rpt','clocks_opt.rpt'},
                'intentional OPT stop lacks its exact command/DCP/clock proof')
        for name,identity in stop['opt_proof'].items():
            require(Path(identity['path']) == source/name, 'foreign intentional-stop OPT proof')
            verify_identity(identity)
        require(key_values(source/'opt_result.txt').get('blackboxes') == '0', 'intentional OPT stop is not the BB-resolved bounded disposition')
        reap = controlled_stop_reap(source, status_path, status, stop)
    failed = status['exit_code'] == 1 and status['native_exit_code'] == 1 and not status['stop_reason']
    require(command.get('execution_mode') == 'checkpoint_restored_commands' and command.get('stage') == 'place' and
            command.get('synthesis') == lineage and status['project'] == str(project) and status['report'] == str(source) and
            status['stage'] == 'place' and (controlled or (failed and not status['owned_survivors'])),
            'OPT recovery parent is not the completed failed restored attempt')
    if not controlled:
        launcher = key_values(source / 'launcher_status.txt')
        require(launcher.get('exit_code') == '1' and launcher.get('native_exit_code') == '1' and
                launcher.get('project') == str(project), 'OPT recovery launcher mismatch')
    validate_stage_archive(source, file_id(source / 'stage_inputs.sha256'), file_id(source / 'archived_sources.sha256'))
    upstream = json.loads((source / 'recovery_parent.json').read_text())
    require(upstream['phase'] in {'project_init_after_link_before_opt', 'post_opt_pre_debug'} and upstream['synthesis'] == lineage,
            'OPT recovery must retain the genuine original project-init/OPT lineage')
    for key in ('checkpoint', 'status', 'launcher', 'child_log', 'command', 'stage_inputs', 'archive', 'source_registry'):
        if upstream.get(key):verify_identity(upstream[key])
    inherited_opt = upstream['phase'] == 'post_opt_pre_debug'
    if inherited_opt:
        original_source = Path(command.get('environment', {}).get('HAP_OPT_REPORT_DIR', ''))
        require(original_source.is_absolute() and original_source != source and
                upstream['command']['path'] == str(original_source/'command.json'), 'OPT continuation original source mismatch')
        original = recovery_opt_parent(original_source, project, lineage, report, _seen=(*_seen, source), _write=False)
        for key in ('checkpoint','status','child_log','command','stage_inputs','archive','source_registry','opt_command',
                    'upstream_recovery','parent_constraints','controlled_stop','post_termination','resource_samples','frozen_child_log'):
            require(upstream.get(key) == original.get(key), f'OPT continuation upstream identity changed: {key}')
        require(upstream['source_metadata'] == original['source_metadata'] and upstream['hashes'] == original['hashes'],
                'OPT continuation upstream constraint identity changed')
    receipt = key_values(source / 'opt_command_result.txt')
    require(receipt.get('phase') == 'opt' and receipt.get('command') == 'opt_design' and
            receipt.get('native_tcl_code') == '0' and int(receipt['ended_epoch']) >= int(receipt['started_epoch']),
            'OPT recovery requires the actual completed opt_design command receipt')
    if inherited_opt:
        require(sha256(source/'opt_command_result.txt') == upstream['opt_command']['sha256'],
                'inherited OPT command receipt changed')
    checkpoint = file_id(source / 'opt.dcp')
    package = checkpoint_package(source / 'opt.dcp')
    result = key_values(source / 'opt_result.txt')
    copied_checkpoint = (inherited_opt and result.get('evidence_origin')=='inherited_identical_opt_checkpoint' and
                         all(checkpoint[k]==upstream['checkpoint'][k] for k in ('sha256','bytes')))
    text = (source / 'implementation_run.log').read_text(errors='replace')
    require((('Command: opt_design' in text and not inherited_opt) or
             (inherited_opt and 'Command: opt_design' not in text and
              f"Command: open_checkpoint {upstream['checkpoint']['path']}" in text)) and
            (f"The checkpoint '{checkpoint['path']}' has been generated" in text or copied_checkpoint) and
            'Command: implement_debug_core' not in text and 'Command: place_design' not in text and
            not (source / 'place_command_result.txt').exists() and not (source / 'debug_materialization_command_result.txt').exists(),
            'OPT checkpoint is not the actually generated post_opt_pre_debug state')
    require(result.get('completed') == '0' and result.get('phase') == 'opt', 'OPT failure must remain unmodified')
    constraint_path = source/('constraints_init.json' if controlled else 'constraints_opt.json')
    constraints = json.loads(constraint_path.read_text())
    require(constraints.get('phase') == ('init' if controlled else 'opt') and constraints.get('mode') == 'embedded_checkpoint_inherited' and
            constraints['candidate_metadata'] == upstream['source_metadata'], 'OPT parent constraint phase/metadata mismatch')
    for name, digest in constraints['hashes'].items():
        constraint_source(name, constraints)
    if controlled:
        coverage = 'NOT_EVALUATED_POST_OPT_INTENTIONALLY_STOPPED_BEFORE_PLACE'
    else:
        counts = check_timing_counts(source / 'check_timing_opt.rpt')
        coverage = phase_coverage('opt', source, counts, int(result['blackboxes']), True)
    reports = ('timing_opt.rpt', 'utilization_opt.rpt', 'drc_opt.rpt', 'check_timing_opt.rpt', 'clocks_opt.rpt',
               'cdc_opt.rpt', 'clock_interaction_opt.rpt', 'exceptions_opt.rpt', 'pulse_width_opt.rpt', 'bus_skew_opt.rpt',
               'reset_cdc_and_io_probe_opt.tsv', 'xpm_invalid_endpoint_probe_opt.tsv', 'head_wave_local_opt.tsv',
               'opt_command_result.txt')
    if not controlled:
        integrity = json.loads((source/'integrity_opt.json').read_text())
        require(integrity.get('phase') == 'opt' and integrity.get('synthesis') == lineage and
                integrity.get('constraints') == file_id(constraint_path), 'OPT completed-report integrity source mismatch')
        require(integrity.get('gate_issues') and all(x.startswith('critical_CDC: ') for x in integrity['gate_issues']),
                'OPT completed-report reuse requires the exact unresolved CDC disposition')
        for name in reports:
            require((source/name).is_file() and (source/name).stat().st_size > 0, f'OPT completed report missing: {name}')
    value = dict(phase='post_opt_pre_debug', original_execution_state='intentional_stop_after_opt_before_place' if controlled else 'failed_opt_post_gate',
        phase_detail='after actual OPT including automatic debug implementation; before separate explicit native debug command/checkpoint',
        opt_evidence_complete=not controlled,
        original_impl_run_remains='FAIL', checkpoint=checkpoint, checkpoint_package=package,
        status=file_id(status_path), launcher=file_id(source/'launcher_status.txt') if not controlled else None, child_log=file_id(source/'implementation_run.log'),
        command=file_id(source/'command.json'), stage_inputs=file_id(source/'stage_inputs.sha256'),
        archive=file_id(source/'archived_sources.sha256'), implementation_settings=file_id(source/'implementation_settings.txt'),
        source_registry=upstream['source_registry'], source_metadata=constraints['candidate_metadata'],
        hashes=constraints['hashes'], actual_reads=upstream['actual_reads'], synthesis=lineage,
        upstream_recovery=file_id(source/'recovery_parent.json'), opt_command=file_id(source/'opt_command_result.txt'),
        parent_constraints=file_id(constraint_path), parent_coverage=coverage,
        constraint_mode='embedded_checkpoint_inherited', inherited_reports={n:file_id(source/n) for n in reports} if not controlled else {})
    value['controlled_stop'] = file_id(stop_path) if controlled else None
    value.update(reap)
    value['completed_report_integrity'] = file_id(source/'integrity_opt.json') if not controlled else None
    value['inherited_reset_evidence'] = None
    if copied_checkpoint:
        previous=upstream.get('inherited_reset_evidence')
        local=(source/'reset_graph_opt.tsv').is_file() and (source/'cdc_changed_reset_opt.tsv').is_file()
        if local or previous:
            structure=integrity['reset_structure'];fanout=integrity['reset_fanout_observation']
            graph=file_id(source/'reset_graph_opt.tsv') if local else previous['graph']
            raw_fanout=file_id(source/'cdc_changed_reset_opt.tsv') if local else previous['fanout']
            require(structure['source']==graph and fanout['source']==raw_fanout and
                    len(structure.get('explicit_primitive_exports',[]))==14,'same-OPT reset evidence producer mismatch')
            exports=[row['netlist'] for row in structure['explicit_primitive_exports']]
            if not local:
                require(all(previous['checkpoint'][k]==checkpoint[k] for k in ('sha256','bytes')) and exports==previous['exports'],
                        'same-OPT inherited reset evidence identity changed')
            for identity in [graph,raw_fanout,*exports]:verify_identity(identity)
            auxiliary=auxiliary_cdc_limits(Path(raw_fanout['path']))
            bram=fanout.get('bram_port_clock_source')
            if bram:
                require(bram==file_id(source/'bram_port_clocks_opt.tsv'),'same-OPT BRAM port clock producer mismatch')
                observed=reset_fanout(Path(raw_fanout['path']),Path(bram['path']))
                require(observed['qualified'] and observed['bram_port_clock_endpoints']==688,
                        'same-OPT actual BRAM/fanout proof is not qualified')
            value['inherited_reset_evidence']={'checkpoint':checkpoint,'graph':graph,'exports':exports,'fanout':raw_fanout,
                'auxiliary_cdc_reports':auxiliary['reports'],'bram_port_clocks':bram,
                'applicability':'exact unchanged OPT bytes/constraints/tool; raw evidence inherited; current parser requalifies; original failed qualification retained'}
    generated_attempt = Path(upstream['generated_phy']['evidence']['path']).parent if inherited_opt else Path(command['managed_attempt'])
    value['generated_phy'] = generated_phy_parent(generated_attempt)
    value['generated_debug'] = generated_debug_parent(generated_attempt)
    value['source_archives'] = {}
    value['generated_source_candidates'] = {}
    for kind in ('generated_phy','generated_debug'):
        for name,identity in value[kind]['main_generated_xdc_candidates'].items():
            value['hashes'][name] = identity['sha256']
            value['source_archives'][name] = identity
            value['generated_source_candidates'][name] = {'kind':kind,'produced_phase':'actual_OPT_core_generation',
                'effective_import_status':'inherited_binary_checkpoint; candidate source is not a fabricated Parsing XDC record'}
    if _write:(report/'recovery_parent.json').write_text(json.dumps(value, indent=2)+'\n')
    return value


PRE_PLACE_POST_REQUIRED = (
    'debug_materialized_result.txt','admission_debug_materialized.txt','integrity_debug_materialized.json',
    'constraints_debug_materialized.json','timing_debug_materialized.rpt','utilization_debug_materialized.rpt',
    'drc_debug_materialized.rpt','check_timing_debug_materialized.rpt','clocks_debug_materialized.rpt',
    'cdc_debug_materialized.rpt','clock_interaction_debug_materialized.rpt','exceptions_debug_materialized.rpt',
    'pulse_width_debug_materialized.rpt','bus_skew_debug_materialized.rpt','debug_debug_materialized.tsv',
    'debug_hub_effective_debug_materialized.xdc','reset_graph_debug_materialized.tsv',
    'cdc_changed_reset_debug_materialized.tsv','bram_port_clocks_debug_materialized.tsv',
    'reset_cdc_and_io_probe_debug_materialized.tsv','xpm_invalid_endpoint_probe_debug_materialized.tsv',
    'head_wave_local_debug_materialized.tsv')


def recovery_pre_place_parent(source: Path, project: Path, lineage: dict, report: Path, *, _write: bool = True) -> dict:
    """One bounded restart from a completed pre-place state, never partial placement."""
    require(source.is_relative_to(ROOT/'vivado/reports') and project.is_relative_to(ROOT/'vivado/project'),
            'foreign completed pre-place recovery root')
    command=json.loads((source/'command.json').read_text());attempt=Path(command['managed_attempt'])
    status_path=attempt/'status.json';status=json.loads(status_path.read_text())
    require(command.get('stage')=='place' and command.get('execution_mode')=='checkpoint_restored_commands' and
            command.get('synthesis')==lineage and status.get('stage')=='place' and status.get('project')==str(project) and
            status.get('report')==str(source) and status.get('exit_code')==124 and status.get('native_exit_code')==-15 and
            status.get('stop_reason')=='stage_wall_timeout' and not status.get('owned_survivors'),
            'pre-place recovery requires the genuine bounded timeout with no survivors')
    require(not command.get('environment',{}).get('HAP_PRE_PLACE_REPORT_DIR'),
            'a completed pre-place restart cannot be repeated without a new physical checkpoint')
    require(not any((source/name).exists() for name in ('place.dcp','physopt.dcp','place_command_result.txt','physopt_command_result.txt')),
            'physical command/checkpoint evidence exists; recover its missing stage rather than repeat place')
    validate_stage_archive(source,file_id(source/'stage_inputs.sha256'),file_id(source/'archived_sources.sha256'))
    old=json.loads((source/'recovery_parent.json').read_text())
    require(old.get('phase')=='post_opt_pre_debug' and old.get('synthesis')==lineage,
            'completed pre-place recovery must retain its original post-OPT lineage')
    upstream_path=Path(command.get('environment',{}).get('HAP_OPT_REPORT_DIR',''))
    require(upstream_path.is_absolute() and old['command']['path']==str(upstream_path/'command.json'),
            'completed pre-place upstream command identity mismatch')
    upstream=recovery_opt_parent(upstream_path,project,lineage,report,_write=False)
    for key in ('checkpoint','status','child_log','command','stage_inputs','archive','source_registry','opt_command',
                'upstream_recovery','parent_constraints','completed_report_integrity'):
        require(old.get(key)==upstream.get(key),f'completed pre-place upstream identity changed: {key}')
    pre=pre_place_evidence(source)
    checkpoint=file_id(source/'debug_materialized.dcp')
    require(pre['checkpoint']==checkpoint,'completed pre-place DCP identity changed')
    package=checkpoint_package(Path(checkpoint['path']))
    text=(source/'vivado.log').read_text(errors='replace')
    require(f"Command: open_checkpoint {old['checkpoint']['path']}" in text and
            f"The checkpoint '{checkpoint['path']}' has been generated" in text and
            'M002_DIAGNOSTIC_STEP_COMPLETED debug_materialized' in text and 'Command: place_design' in text and
            'Command: phys_opt_design' not in text,'completed pre-place DCP/command chronology is not genuine')
    integrity=json.loads((source/'integrity_debug_materialized.json').read_text())
    require(not integrity.get('gate_issues') and integrity['reset_structure'].get('qualified') is True and
            integrity['reset_fanout_observation'].get('qualified') is True and
            integrity['reset_fanout_observation'].get('bram_port_clock_endpoints')==688 and
            integrity['cdc_classification'].get('classified_opt_reset')==8,
            'completed pre-place reset/CDC/fanout qualification incomplete')
    constraints=json.loads((source/'constraints_debug_materialized.json').read_text())
    require(constraints.get('mode')=='embedded_checkpoint_inherited' and
            constraints['candidate_metadata']==old['source_metadata'],'completed pre-place constraint identity changed')
    for name in constraints['hashes']:constraint_source(name,constraints)
    for name in PRE_PLACE_POST_REQUIRED:
        require((source/name).is_file() and (source/name).stat().st_size>0,f'completed pre-place POST source missing: {name}')
    proof=[integrity['reset_structure']['source'],integrity['reset_fanout_observation']['source'],
           integrity['reset_fanout_observation']['bram_port_clock_source']]
    proof += [row['netlist'] for row in integrity['reset_structure']['explicit_primitive_exports']]
    for identity in proof:verify_identity(identity)
    historical={'opt':file_id(source/'opt_command_result.txt'),
                'debug_materialization':file_id(source/'debug_materialization_command_result.txt')}
    require(historical['opt']['sha256']==old['opt_command']['sha256'],'historical OPT command receipt changed')
    debug_command_receipt(source)
    for phase,expected in (('opt','opt_design'),('debug_materialization','implement_debug_core')):
        receipt=key_values(Path(historical[phase]['path']))
        require(receipt.get('phase')==phase and receipt.get('command')==expected and receipt.get('native_tcl_code')=='0',
                'historical pre-place command receipt is not successful')
    runtime=key_values(source/'restored_runtime_settings.txt')
    require(runtime.get('ip_cache_after')=='disable','completed pre-place actual cache policy is not disabled')
    terminal=json.loads((attempt/'terminal_facts.json').read_text())
    require(terminal['original_status']==file_id(status_path) and terminal['available_debug_checkpoint']==checkpoint and
            terminal.get('owned_survivors')==[] and terminal.get('placed_checkpoint_exists') is False,
            'completed pre-place timeout/cost evidence mismatch')
    post_manifest=attempt/'completed_pre_place_post.sha256'
    post_completion=json.loads((attempt/'completed_pre_place_post_completion.json').read_text())
    require(post_completion.get('original_status')==file_id(status_path) and
            post_completion.get('terminal_facts')==file_id(attempt/'terminal_facts.json') and
            post_completion.get('checkpoint')==checkpoint and post_completion.get('pre_place')==file_id(source/'pre_place_evidence.json') and
            post_completion.get('manifest')==file_id(post_manifest) and post_completion.get('processes_gone') is True,
            'completed pre-place post-termination source closure changed')
    bound_post=input_manifest(post_manifest)
    require({source/name for name in PRE_PLACE_POST_REQUIRED} <= set(bound_post) and
            all(path.parent==source for path in bound_post),'completed pre-place POST manifest missing/foreign sources')
    inherited={name:file_id(source/name) for name in PRE_PLACE_POST_REQUIRED}
    for path in source.iterdir():
        if path.is_file() and 'debug_materialized' in path.name and path.name!='debug_materialized.dcp':
            inherited.setdefault(path.name,artifact_id(path))
    value=dict(phase='post_debug_pre_place',source_report=str(source),
        original_execution_state='stage_wall_timeout_after_completed_pre_place',original_execution_preserved=True,
        restart_scope='restart place from saved completed pre-place state; partial placement progress is not inherited',
        single_bounded_restart=True,checkpoint=checkpoint,checkpoint_package=package,synthesis=lineage,
        status=file_id(status_path),command=file_id(source/'command.json'),child_log=file_id(source/'vivado.log'),
        stage_inputs=file_id(source/'stage_inputs.sha256'),archive=file_id(source/'archived_sources.sha256'),
        implementation_settings=file_id(source/'implementation_settings.txt'),source_registry=old['source_registry'],
        upstream_recovery=file_id(source/'recovery_parent.json'),parent_constraints=file_id(source/'constraints_debug_materialized.json'),
        inherited_pre_place=file_id(source/'pre_place_evidence.json'),inherited_integrity=file_id(source/'integrity_debug_materialized.json'),
        historical_command_receipts=historical,inherited_reports=inherited,inherited_proof_sources=proof,
        terminal_cost=file_id(attempt/'terminal_facts.json'),inherited_post_manifest=file_id(post_manifest),
        post_termination_post_completion=file_id(attempt/'completed_pre_place_post_completion.json'),source_metadata=constraints['candidate_metadata'],
        hashes=constraints['hashes'],source_archives=constraints.get('source_archives',{}),
        tool_debug_metadata=constraints.get('tool_debug_metadata',{}),
        generated_source_candidates=constraints.get('generated_source_candidates',{}),actual_reads=old['actual_reads'],
        constraint_mode='embedded_checkpoint_inherited',generated_phy=old['generated_phy'],generated_debug=old['generated_debug'],
        inherited_POST_scope='original completed measurements, not this restart measurements',formal_reset_cdc_safety='OPEN')
    auth=full_impl.report_authorization(report)
    if auth:
        value.update(execution_authorization=auth,single_bounded_restart=False,
            restart_scope="E003 new full implementation authorization; saved pre-place restore; partial placement is not inherited")
    if _write:(report/'recovery_parent.json').write_text(json.dumps(value,indent=2)+'\n')
    return value


def restored_pre_place_evidence(report: Path, *, create: bool = False, frozen_source: bool = False) -> dict:
    """Fresh bounded live guard plus the original, separately identified full POST."""
    parent=json.loads((report/'recovery_parent.json').read_text())
    require(parent.get('phase')=='post_debug_pre_place','not a completed pre-place restore mode')
    command=json.loads((report/'command.json').read_text())
    require(command.get('execution_mode')=='checkpoint_restored_commands' and command.get('stage')=='place' and
            command.get('synthesis')==parent['synthesis'] and
            command.get('environment',{}).get('HAP_PRE_PLACE_REPORT_DIR')==parent['source_report'] and
            command.get('environment',{}).get('HAP_RECOVERY_CHECKPOINT')==parent['checkpoint']['path'],
            'completed pre-place restore command identity mismatch')
    expected=recovery_pre_place_parent(Path(parent['source_report']),Path(parent['synthesis']['project']),parent['synthesis'],report,_write=False)
    require(parent==expected,'completed pre-place recovery record changed')
    if frozen_source:validate_stage_archive(report,file_id(report/'stage_inputs.sha256'),file_id(report/'archived_sources.sha256'))
    else:input_manifest(report/'stage_inputs.sha256')
    mode=key_values(report/'restored_checkpoint_mode.txt')
    require(mode.get('checkpoint')==parent['checkpoint']['path'] and mode.get('execution_mode')=='checkpoint_restored_commands',
            'actual restored pre-place checkpoint mismatch')
    preflight=(report/'restored_preflight.tsv').read_text().splitlines()
    require(preflight and preflight[-1]=='PREFLIGHT_ISSUES\t' and
            sum(row.startswith('PREFLIGHT_ISSUES\t') for row in preflight)==1 and
            any(row.startswith('BLACKBOX_COUNT\t0\t') for row in preflight),
            'actual restored pre-place live sanity incomplete')
    original_full=json.loads(Path(parent['inherited_integrity']['path']).read_text())
    for label,key in (('ASYNC_SEQUENTIAL_COUNT','async_reset_chains'),('AUX_SEQUENTIAL_COUNT','aux_chains')):
        actual={}
        for row in preflight:
            f=row.split('\t')
            if f[0]==label:
                require(len(f)==3 and f[1] not in actual,'duplicate/malformed live reset count')
                actual[f[1]]=int(f[2])
        require(actual=={row['root']:4 for row in original_full['reset_structure'][key]},
                'actual restored pre-place reset sanity differs from completed proof')
    counts=check_timing_counts(report/'check_timing_pre_place_restore.rpt')
    require(placement_coverage(counts,0),'actual restored pre-place clock coverage incomplete')
    reset_io_coverage(report/'check_timing_pre_place_restore.rpt')
    guard=key_values(report/'pre_place_restore_command_result.txt')
    require(guard.get('phase')=='pre_place_restore' and guard.get('command')=='m002_live_pre_place_restore' and
            guard.get('native_tcl_code')=='0' and int(guard['ended_epoch'])>=int(guard['started_epoch']),
            'actual restored pre-place native sanity/DRC did not complete')
    native=key_values(report/'pre_place_restore_guard.txt')
    require(native.get('completed')=='1' and native.get('blackboxes')=='0' and native.get('drc_blockers')=='0' and
            native.get('clock_groups_verified')=='1','actual restored pre-place native DRC/clock guard incomplete')
    constraints=json.loads((report/'constraints_pre_place_restore.json').read_text())
    require(constraints.get('mode')=='embedded_checkpoint_inherited' and constraints['hashes']==parent['hashes'] and
            constraints['candidate_metadata']==parent['source_metadata'],'restored effective pre-place constraints changed')
    for name in constraints['hashes']:constraint_source(name,constraints)
    original=original_full['debug_clock_observation']
    current=debug_clock_facts(report/'debug_restore.tsv',effective_path=Path(original['effective_hub_constraints']['path']))
    require(current['relationship_qualified'] and all(current[key]==original[key] for key in (
        'input_clocks','outputs','clocks','actual_output_drivers','actual_output_startpoints','fanout_endpoint_count',
        'fanout_by_output','fanout_clock_names','actual_input_hz','divider')),'actual restored hub clock relation differs from completed pre-place')
    def endpoints(path):return {row for row in path.read_text().splitlines() if row.startswith('DEBUG_ENDPOINT_CLOCKS\t')}
    require(endpoints(report/'debug_restore.tsv') and endpoints(report/'debug_restore.tsv')==endpoints(Path(original['source']['path'])),
            'actual restored hub endpoint set differs from completed pre-place')
    log=report/'vivado.log';snapshot=report/'pre_place_restore_log_snapshot.txt'
    if create:
        require(not (report/'place_command_result.txt').exists() and 'Command: place_design' not in log.read_text(errors='replace'),
                'restored pre-place admission created after actual place started')
        require(not snapshot.exists(),'restored pre-place log snapshot already exists')
        snapshot.write_bytes(log.read_bytes())
    prefix=snapshot.read_bytes()
    require(log.read_bytes().startswith(prefix) and
            f"Command: open_checkpoint {parent['checkpoint']['path']}" in prefix.decode(errors='replace') and
            'Command: place_design' not in prefix.decode(errors='replace'),'actual pre-place restore log/chronology mismatch')
    value=dict(phase='restored_completed_pre_place',checkpoint=parent['checkpoint'],
        inherited_pre_place=parent['inherited_pre_place'],inherited_integrity=parent['inherited_integrity'],
        historical_command_receipts=parent['historical_command_receipts'],
        inherited_measurements='original complete POST; not newly measured in this restart',
        recovery_parent=file_id(report/'recovery_parent.json'),live_clock_coverage=counts,live_debug_clock_observation=current,
        **{key:file_id(report/name) for key,name in (
            ('live_preflight','restored_preflight.tsv'),('live_runtime','restored_runtime_settings.txt'),
            ('live_constraints','constraints_pre_place_restore.json'),('live_DRC','drc_pre_place_restore.rpt'),
            ('live_guard','pre_place_restore_guard.txt'),('live_guard_command','pre_place_restore_command_result.txt'),
            ('live_check_timing','check_timing_pre_place_restore.rpt'),('live_log_prefix','pre_place_restore_log_snapshot.txt'))},
        diagnostic_eligible=True,formal_reset_cdc_safety='OPEN',physical_signoff=False)
    if create:(report/'pre_place_evidence.json').write_text(json.dumps(value,indent=2)+'\n')
    else:require(json.loads((report/'pre_place_evidence.json').read_text())==value,'restored pre-place admission changed')
    return value



def recovery_placed_parent(source: Path, project: Path, lineage: dict, report: Path, *, _write: bool = True) -> dict:
    """Current real E003 failure: closed place command, only CDC POST classification failed."""
    require(source.is_relative_to(ROOT/'vivado/reports') and project.is_relative_to(ROOT/'vivado/project'), 'foreign placed recovery root')
    command=json.loads((source/'command.json').read_text());attempt=Path(command['managed_attempt'])
    status=json.loads((attempt/'status.json').read_text());terminal=json.loads((attempt/'terminal_facts.json').read_text())
    require(command.get('stage')=='place' and command.get('execution_mode')=='checkpoint_restored_commands' and
            command.get('synthesis')==lineage and status.get('stage')=='place' and status.get('project')==str(project) and
            status.get('report')==str(source) and status.get('exit_code')==1 and status.get('native_exit_code')==1 and
            status.get('stop_reason') is None and not status.get('owned_survivors') and
            status.get('supervision_profile')=='m002_no_wall_continuation' and status.get('wall_clock_stop_disabled') is True,
            'placed recovery requires actual ended natural POST failure under continuation authorization')
    require(terminal['attempt_status']==file_id(attempt/'status.json') and terminal['owned_original_identities_present']==[] and
            terminal['stage_scope']['place_native']=='PASS' and terminal['stage_scope']['physopt']=='NOT_RUN', 'placed source terminal identity/scope changed')
    validate_stage_archive(source,file_id(source/'stage_inputs.sha256'),file_id(source/'archived_sources.sha256'))
    old=json.loads((source/'recovery_parent.json').read_text())
    require(old.get('phase')=='post_debug_pre_place' and old.get('synthesis')==lineage, 'unsupported placed recovery ancestor')
    admission=restored_pre_place_evidence(source,frozen_source=True)
    manifest=attempt/'closed_placed_source.sha256';completion_path=attempt/'closed_placed_source_completion.json';completion=json.loads(completion_path.read_text())
    require(completion.get('status')==file_id(attempt/'status.json') and completion.get('terminal')==file_id(attempt/'terminal_facts.json') and
            completion.get('manifest')==file_id(manifest) and completion.get('processes_gone') is True, 'placed source closure changed')
    bound=input_manifest(manifest)
    require(bound and all(path.is_relative_to(source) for path in bound), 'foreign placed closure source')
    receipt=key_values(source/'place_command_result.txt');checkpoint=file_id(source/'place.dcp');package=checkpoint_package(source/'place.dcp')
    log=(source/'vivado.log').read_text(errors='replace')
    require(receipt.get('phase')=='place' and receipt.get('command')=='place_design' and receipt.get('native_tcl_code')=='0' and
            int(receipt['ended_epoch'])>=int(receipt['started_epoch'])>=int(key_values(Path(admission['live_guard_command']['path']))['ended_epoch']) and
            'place_design completed successfully' in log and f"The checkpoint '{checkpoint['path']}' has been generated" in log and
            not any((source/name).exists() for name in ('physopt.dcp','physopt_command_result.txt','diagnostic_evidence.json')) and
            'Command: phys_opt_design' not in log and completion.get('checkpoint')==checkpoint and completion.get('package')==package and
            completion.get('place_command')==file_id(source/'place_command_result.txt'), 'source is not closed native place before independent physopt')
    integrity=json.loads((source/'integrity_place.json').read_text())
    require(integrity.get('phase')=='place' and integrity.get('gate_issues')==['critical_CDC: ValueError: new/unclassified critical CDC path'] and
            key_values(source/'place_result.txt').get('completed')=='0', 'placed source failure scope changed')
    structure=reset_structure(source/'reset_graph_place.tsv');fanout=reset_fanout(source/'cdc_changed_reset_place.tsv',source/'bram_port_clocks_place.tsv')
    require(structure==integrity['reset_structure'] and
            {k:v for k,v in fanout.items() if k!='bram_models'}=={k:v for k,v in integrity['reset_fanout_observation'].items() if k!='bram_models'} and
            sorted(fanout['bram_models'],key=lambda x:x['path'])==sorted(integrity['reset_fanout_observation']['bram_models'],key=lambda x:x['path']) and
            structure['qualified'] and fanout['qualified'], 'placed actual graph/primitive/fanout proof changed')
    cdc=critical_coverage(source/'cdc_place.rpt',ROOT/'vivado/reports/m002_E002_R001_AT002_fresh_synth/cdc_post_synth.rpt',structure,fanout)
    require(len(cdc.get('actual_aux_representative_sources',[]))==2 and
            all('/d1_gate/inst/u_base_reset_cdc/' in row['actual_tuple'][3] for row in cdc['actual_aux_representative_sources']), 'placed source is outside current two DDR1 representative changes')
    counts=check_timing_counts(source/'check_timing_place.rpt');require(placement_coverage(counts,0), 'placed source coverage incomplete');reset_io_coverage(source/'check_timing_place.rpt')
    utilization_metrics(source/'utilization_place.rpt')
    required={f'{name}_place.rpt' for name in ('timing','utilization','utilization_slr','congestion','slr_crossing','drc','check_timing','clocks','cdc','clock_interaction','exceptions','pulse_width','bus_skew')}
    required|={'place.dcp','place_command_result.txt','integrity_place.json','reset_structure_place.json','reset_graph_place.tsv','cdc_changed_reset_place.tsv','bram_port_clocks_place.tsv','constraints_place.json','place_result.txt'}
    require({source/name for name in required}<=set(bound), 'placed closure lacks actual required POST/checkpoint sources')
    prior_constraints=source/'constraints_place.json';constraints=json.loads(prior_constraints.read_text())
    require(constraints.get('mode')=='embedded_checkpoint_inherited' and constraints['hashes']==old['hashes'] and constraints['candidate_metadata']==old['source_metadata'], 'placed effective constraint identity changed')
    for name in constraints['hashes']:constraint_source(name,constraints)
    history={**old['historical_command_receipts'],'place':file_id(source/'place_command_result.txt')}
    require(set(history)=={'opt','debug_materialization','place'}, 'placed inherited command history changed')
    value={key:old[key] for key in ('source_metadata','hashes','source_archives','tool_debug_metadata','generated_source_candidates','actual_reads','generated_phy','generated_debug') if key in old}
    value.update(phase='post_place_pre_physopt',physical_point='place',source_report=str(source),synthesis=lineage,
        checkpoint=checkpoint,checkpoint_package=package,status=file_id(attempt/'status.json'),command=file_id(source/'command.json'),child_log=file_id(source/'vivado.log'),
        stage_inputs=file_id(source/'stage_inputs.sha256'),archive=file_id(source/'archived_sources.sha256'),implementation_settings=file_id(source/'implementation_settings.txt'),
        source_registry=old['source_registry'],upstream_recovery=file_id(source/'recovery_parent.json'),parent_constraints=file_id(prior_constraints),
        inherited_pre_place=file_id(source/'pre_place_evidence.json'),inherited_integrity=old['inherited_integrity'],historical_command_receipts=history,inherited_reports={},
        source_completion=file_id(completion_path),source_post_manifest=file_id(manifest),source_original_POST_failure=file_id(source/'integrity_place.json'),
        actual_CDC_revalidation=cdc,physical_post_complete=False,constraint_mode='embedded_checkpoint_inherited',
        restart_scope='fresh live guard; complete missing place POST then new independent physopt; never place_design',formal_reset_cdc_safety='OPEN')
    if _write:(report/'recovery_parent.json').write_text(json.dumps(value,indent=2)+'\n')
    return value


def completed_placed_post(report: Path) -> None:
    parent=json.loads((report/'recovery_parent.json').read_text())
    require(parent['phase']=='post_place_pre_physopt', 'wrong completed placed POST parent')
    result=key_values(report/'place_result.txt');integrity=json.loads((report/'integrity_place.json').read_text())
    require(result.get('completed')=='1' and result.get('diagnostic_eligible')=='1' and
            integrity.get('phase')=='place' and not integrity.get('gate_issues'), 'new place POST incomplete')
    verify_reset_proof(integrity['reset_structure']);verify_cdc_proof(integrity['cdc_classification'])
    require(integrity['reset_structure']['source']['path']==str(report/'reset_graph_place.tsv'), 'place POST uses foreign graph')
    require(not (report/'place_command_result.txt').exists() and (report/'place.dcp').is_file(), 'place command repeated or POST checkpoint missing')
    guard=key_values(report/'pre_place_restore_command_result.txt');physopt=key_values(report/'physopt_command_result.txt')
    log=(report/'vivado.log').read_text(errors='replace')
    marker="M002_DIAGNOSTIC_STEP_COMPLETED place"
    require(marker in log and 'Command: phys_opt_design' in log and log.index(marker)<log.index('Command: phys_opt_design') and
            'Command: place_design' not in log and 'Command: opt_design' not in log and 'Command: implement_debug_core' not in log and
            int(physopt['started_epoch'])>=int(guard['ended_epoch']), 'fresh place POST/independent physopt chronology mismatch')


def physical_resume_evidence(report: Path, *, create: bool = False, _seen: tuple = (), frozen_source: bool = False) -> dict:
    parent=json.loads((report/'recovery_parent.json').read_text())
    require(parent.get('phase')=='post_place_pre_physopt', 'not a physical checkpoint continuation')
    command=json.loads((report/'command.json').read_text())
    require(command.get('execution_mode')=='checkpoint_restored_commands' and command.get('stage')=='place' and
            command.get('synthesis')==parent['synthesis'] and
            command.get('environment',{}).get('HAP_PHYSICAL_REPORT_DIR')==parent['source_report'] and
            command.get('environment',{}).get('HAP_RECOVERY_CHECKPOINT')==parent['checkpoint']['path'],
            'physical continuation actual command/checkpoint mismatch')
    require(parent==recovery_placed_parent(Path(parent['source_report']),Path(parent['synthesis']['project']),parent['synthesis'],report,_write=False), 'physical continuation parent changed')
    if frozen_source:
        validate_stage_archive(report,file_id(report/'stage_inputs.sha256'),file_id(report/'archived_sources.sha256'))
    else:input_manifest(report/'stage_inputs.sha256')
    mode=key_values(report/'restored_checkpoint_mode.txt');runtime=key_values(report/'restored_runtime_settings.txt')
    require(mode.get('checkpoint')==parent['checkpoint']['path'] and mode.get('execution_mode')=='checkpoint_restored_commands' and
            runtime.get('ip_cache_after')=='disable', 'physical continuation actual restore policy mismatch')
    preflight=(report/'restored_preflight.tsv').read_text().splitlines()
    require(preflight and preflight[-1]=='PREFLIGHT_ISSUES\t' and
            sum(x.startswith('PREFLIGHT_ISSUES\t') for x in preflight)==1 and
            any(x.startswith('BLACKBOX_COUNT\t0\t') for x in preflight), 'physical continuation live preflight incomplete')
    baseline=json.loads(Path(parent['inherited_integrity']['path']).read_text())
    for label,key in (('ASYNC_SEQUENTIAL_COUNT','async_reset_chains'),('AUX_SEQUENTIAL_COUNT','aux_chains')):
        rows=[x.split('\t') for x in preflight if x.startswith(label+'\t')]
        require(len(rows)==len({x[1] for x in rows}) and {x[1]:int(x[2]) for x in rows}==
                {x['root']:4 for x in baseline['reset_structure'][key]}, 'physical continuation live reset count mismatch')
    counts=check_timing_counts(report/'check_timing_pre_place_restore.rpt')
    require(placement_coverage(counts,0), 'physical continuation live clock coverage incomplete')
    reset_io_coverage(report/'check_timing_pre_place_restore.rpt')
    guard=key_values(report/'pre_place_restore_command_result.txt');native=key_values(report/'pre_place_restore_guard.txt')
    require(guard.get('phase')=='pre_place_restore' and guard.get('command')=='m002_live_pre_place_restore' and
            guard.get('native_tcl_code')=='0' and int(guard['ended_epoch'])>=int(guard['started_epoch']) and
            native==dict(completed='1',blackboxes='0',drc_blockers='0',clock_groups_verified='1'),
            'physical continuation fresh native DRC/clock guard incomplete')
    constraints=json.loads((report/'constraints_pre_place_restore.json').read_text())
    require(constraints.get('mode')=='embedded_checkpoint_inherited' and constraints['hashes']==parent['hashes'] and
            constraints['candidate_metadata']==parent['source_metadata'], 'physical continuation live constraints changed')
    for name in constraints['hashes']:constraint_source(name,constraints)
    original=baseline['debug_clock_observation']
    clocks=debug_clock_facts(report/'debug_restore.tsv',effective_path=Path(original['effective_hub_constraints']['path']))
    require(clocks['relationship_qualified'] and all(clocks[k]==original[k] for k in ('input_clocks','outputs','clocks',
        'actual_output_drivers','actual_output_startpoints','fanout_endpoint_count','fanout_by_output','fanout_clock_names',
        'actual_input_hz','divider')),
        'physical continuation live hub relationship changed')
    endpoints=lambda path:{row for row in path.read_text().splitlines() if row.startswith('DEBUG_ENDPOINT_CLOCKS\t')}
    require(endpoints(report/'debug_restore.tsv') and endpoints(report/'debug_restore.tsv')==endpoints(Path(original['source']['path'])),
            'physical continuation live hub endpoint set changed')
    snapshot=report/'physical_resume_log_snapshot.txt';log=report/'vivado.log'
    if create:
        require(not snapshot.exists(), 'physical restore admission already exists');snapshot.write_bytes(log.read_bytes())
    prefix=snapshot.read_bytes();text=prefix.decode(errors='replace')
    require(log.read_bytes().startswith(prefix) and f"Command: open_checkpoint {parent['checkpoint']['path']}" in text and
            not any(f'Command: {x}' in text for x in ('place_design','phys_opt_design','route_design')),
            'physical continuation admission chronology mismatch')
    value=dict(phase='restored_physical_checkpoint_live_admission',checkpoint=parent['checkpoint'],
        physical_point=parent['physical_point'],inherited_pre_place=parent['inherited_pre_place'],
        historical_command_receipts=parent['historical_command_receipts'],
        recovery_parent=file_id(report/'recovery_parent.json'),live_clock_coverage=counts,live_debug_clock_observation=clocks,
        **{k:file_id(report/n) for k,n in (('live_preflight','restored_preflight.tsv'),('live_runtime','restored_runtime_settings.txt'),
            ('live_constraints','constraints_pre_place_restore.json'),('live_guard','pre_place_restore_guard.txt'),
            ('live_guard_command','pre_place_restore_command_result.txt'),('live_DRC','drc_pre_place_restore.rpt'),
            ('live_check_timing','check_timing_pre_place_restore.rpt'),('live_log_prefix','physical_resume_log_snapshot.txt'))},
        diagnostic_eligible=True,formal_reset_cdc_safety='OPEN',physical_signoff=False)
    if create:(report/'physical_resume_evidence.json').write_text(json.dumps(value,indent=2)+'\n')
    else:require(json.loads((report/'physical_resume_evidence.json').read_text())==value, 'physical restore live admission changed')
    return value


def constraint_source(name: str, value: dict) -> Path:
    """Use real retained bytes when Vivado has removed a temporary debug source."""
    source = Path(name)
    if source.is_file():
        require(sha256(source) == value['hashes'][name], f'effective constraint changed: {name}')
        return source
    identity = value.get('source_archives', {}).get(name)
    require(identity is not None, f'effective constraint missing without retained bytes: {name}')
    verify_identity(identity)
    require(identity['sha256'] == value['hashes'][name], f'retained constraint differs: {name}')
    return Path(identity['path'])


def retain_debug_sources(report: Path, hashes: dict, debug_metadata: dict, previous: dict) -> dict:
    import shutil
    retained = dict(previous.get('source_archives', {}))
    for name in debug_metadata:
        value = {'hashes':hashes, 'source_archives':retained}
        source = constraint_source(name, value)
        if name not in retained:
            target = report/'constraint_sources'/(hashes[name]+'_'+Path(name).name)
            target.parent.mkdir(exist_ok=True)
            if not target.exists():
                shutil.copy2(source,target)
            retained[name] = file_id(target)
        verify_identity(retained[name])
        require(retained[name]['sha256'] == hashes[name], 'retained debug source hash mismatch')
    return retained


def recovery_constraints(point: str, report: Path) -> dict:
    import os
    metadata, hashes = hash_registry(point, report)
    parent = report / 'recovery_parent.json'
    if os.environ.get('HAP_STAGE') == 'route':
        parent = Path(os.environ['HAP_PLACE_REPORT_DIR']) / 'constraints_physopt.json'
    old = json.loads(parent.read_text())
    original_metadata = old.get('candidate_metadata', old.get('source_metadata', old.get('metadata')))
    require(metadata == original_metadata, 'current candidate project XDC metadata changed from checkpoint parent')
    for name, digest in old['hashes'].items():
        constraint_source(name, old)
    hashes = {**old['hashes'], **hashes}
    # Each phase inherits every prior effective constraint, then classifies
    # only actual new tool-debug sources. No fabricated read_xdc operation.
    previous = {'init':'project','opt':'init','debug_materialized':'opt',
                'place':'debug_materialized','physopt':'place'}.get(point)
    if point == 'opt' and old.get('phase') == 'post_opt_pre_debug':
        previous = 'project'
    if point == 'place' and old.get('phase') in {'post_debug_pre_place','post_place_pre_physopt'}:previous='pre_place_restore'
    prior = report / f'constraints_{previous}.json' if previous else parent
    if point == 'route':
        prior = parent
    previous_value = json.loads(prior.read_text())
    for name, digest in previous_value['hashes'].items():
        constraint_source(name, previous_value)
    hashes = {**previous_value['hashes'], **hashes}
    debug_registry = report / f'tool_debug_registry_{point}.tsv'
    debug_metadata = dict(previous_value.get('tool_debug_metadata', {}))
    if debug_registry.exists():
        allowed = set((report / f'tool_debug_xdc_{point}.txt').read_text().splitlines())
        owners = set()
        for row in (report/f'tool_debug_xdc_ownership_{point}.tsv').read_text().splitlines():
            owner = row.split('\t')
            associated = len(owner) == 4 and owner[3] == 'actual_debug_core=dbg_hub;cell=dbg_hub;component=dbg_hub'
            require(len(owner) in {3,4} and owner[0] and (':dbg_hub:' in owner[1] or
                    (owner[1] == 'xilinx.com:ip:xsdbm:3.0' and associated)), 'invalid actual debug XDC owner')
            owners.add(owner[2])
        require(owners == allowed, 'actual debug XDC owner/source mismatch')
        for row in debug_registry.read_text().splitlines()[1:]:
            f = row.split('\t');require(len(f)==9,'malformed tool debug metadata')
            require(f[0] in allowed,'unowned debug constraint')
            require(f[0] not in debug_metadata or debug_metadata[f[0]] == f[1:-1], 'tool debug XDC metadata changed')
            require(f[0] in hashes or point == 'debug_materialized', 'new tool debug constraints outside actual debug materialization')
            if f[0] not in hashes:
                debug_command_receipt(report)
            debug_metadata[f[0]] = f[1:-1]
            if f[0] in hashes:
                constraint_source(f[0], {'hashes':hashes, 'source_archives':previous_value.get('source_archives',{})})
            else:
                hashes[f[0]]=sha256(Path(f[0]))
    retained = retain_debug_sources(report, hashes, debug_metadata, previous_value)
    actual=[]
    live_log=report/'vivado.log'
    if live_log.exists():
        for number,line in enumerate(live_log.read_text(errors='replace').splitlines(),1):
            match=re.match(r"Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?",line)
            if not match:continue
            name=match.group(1)
            require(name in hashes,'new unclassified effective constraint during checkpoint continuation')
            actual.append(dict(line=number,path=name,scope=match.group(2),sha256=hashes[name]))
    actual_path=report/f'actual_xdc_reads_{point}.json'
    actual_path.write_text(json.dumps(dict(mode='embedded_checkpoint_inherited',inherited_from=file_id(parent),new_actual_reads=actual),indent=2)+'\n')
    result=dict(phase=point,mode='embedded_checkpoint_inherited',candidate_metadata=metadata,metadata=metadata,
                tool_debug_metadata=debug_metadata,hashes=hashes,parent=file_id(prior),
                source_archives=retained,
                generated_source_candidates=previous_value.get('generated_source_candidates',old.get('generated_source_candidates',{})),
                registry=file_id(report/f'xdc_registry_{point}_hashed.tsv'),actual_reads=file_id(actual_path))
    (report/f'constraints_{point}.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def phase_coverage(point: str, report: Path, counts: dict, bb: int, restored: bool) -> str:
    """The unique proven tool placeholder may reach OPT/debug generation only."""
    require(all(counts.get(x, -1) == 0 for x in ("multiple_clock", "generated_clocks", "loops", "pulse_width_clock")),
            "unresolved clock definition/loop at diagnostic init/physical stage")
    if placement_coverage(counts, bb):
        return "COMPLETE_INTERNAL"
    require(point == "init" or (point == "opt" and restored),
            "unresolved blackbox or internal timing coverage before place")
    require(bb == 1, "debug exception requires its unique actual blackbox")
    proof = key_values(report / f"debug_proof_{point}.txt")["verified"] == "1"
    fanout = {row.split("\t")[2] for row in (report / f"debug_{point}.tsv").read_text().splitlines()
              if row.startswith("DEBUG_CLOCK_FANOUT\t")}
    require(debug_gap_coverage(report / f"check_timing_{point}.rpt", fanout, proof), "unverified debug clock/blackbox gap")
    return "PENDING_TOOL_DEBUG_MATERIALIZATION"


def debug_clock_facts(path: Path, *, effective_path: Path | None = None) -> dict:
    pins, endpoint_clocks, clocks, properties, nets, drivers, starts = {}, {}, {}, {}, {}, {}, {}
    def names(value):return [word.strip('{}') for word in value.split()]
    for row in path.read_text().splitlines():
        f=row.split('\t')
        if f[0] == 'DEBUG_PIN_CLOCKS':pins[f[1]]=names(f[2])
        elif f[0] == 'DEBUG_ENDPOINT_CLOCKS':endpoint_clocks[(f[1],f[2])]=names(f[3])
        elif f[0] == 'DEBUG_ACTUAL_CLOCK':clocks.setdefault(f[1],{})[f[2]]=f[3]
        elif f[0] == 'PROPERTY' and f[1] == 'dbg_hub':properties[f[2]]=f[3]
        elif f[0] == 'DEBUG_PIN_NETS':nets[f[1]]=set(names(f[2]))
        elif f[0] == 'DEBUG_OUTPUT_DRIVER':drivers.setdefault(f[1],[]).append({'pin':f[2],'ref':f[3],'refpin':f[4]})
        elif f[0] == 'DEBUG_OUTPUT_STARTPOINTS':starts[f[1]]=names(f[2])
    input_clocks=pins.get('dbg_hub/clk',[])
    outputs={f'dbg_hub/sl_iport{d}_o[1]':pins.get(f'dbg_hub/sl_iport{d}_o[1]',[]) for d in (0,1)}
    require(len(input_clocks) == 1 and all(outputs.values()) and endpoint_clocks and all(endpoint_clocks.values()),
            'actual hub input/output/fanout clock observations incomplete')
    used=set(input_clocks)|{clock for values in outputs.values() for clock in values}|{clock for values in endpoint_clocks.values() for clock in values}
    for clock in used:
        require(clock in clocks and {'PERIOD','MASTER_CLOCK','SOURCE_PINS','IS_GENERATED','WAVEFORM'} <= set(clocks[clock]),
                'actual hub clock period/master/source properties incomplete')
        period=float(clocks[clock]['PERIOD']);require(math.isfinite(period) and period > 0, 'invalid actual hub clock period')
    input_hz=1e9/float(clocks[input_clocks[0]]['PERIOD'])
    declared=float(properties['C_CLK_INPUT_FREQ_HZ'])
    issues=[];input_clock=input_clocks[0]
    def rooted(clock, seen=frozenset()):
        if clock == input_clock:return True
        if clock in seen or clock not in clocks:return False
        masters=names(clocks[clock].get('MASTER_CLOCK',''))
        return len(masters)==1 and clocks[clock].get('IS_GENERATED','').lower() in {'1','true'} and rooted(masters[0],seen|{clock})
    divider=properties.get('C_ENABLE_CLK_DIVIDER','').lower()
    if divider not in {'0','false','1','true'}:issues.append('unknown actual clock-divider configuration')
    for pin,values in outputs.items():
        if not drivers.get(pin) or not starts.get(pin):issues.append(f'unknown actual output driver/startpoint {pin}')
        direct=bool(nets.get(pin,set()) & nets.get('dbg_hub/clk',set()))
        for clock in values:
            same_period=math.isclose(float(clocks[clock]['PERIOD']),float(clocks[input_clock]['PERIOD']),rel_tol=1e-6)
            same_wave=clocks[clock].get('WAVEFORM') == clocks[input_clock].get('WAVEFORM')
            if not ((rooted(clock) or (direct and same_period and same_wave)) and clocks[clock].get('SOURCE_PINS')):
                issues.append(f'unknown actual output clock ancestry/source {pin} {clock}')
            if divider in {'0','false'} and not same_period:
                issues.append(f'undivided output period differs from actual input {pin} {clock}')
        observed={clock for (output,_),values in endpoint_clocks.items() if output==pin for clock in values}
        if observed != set(values):issues.append(f'output/fanout clock relationship differs {pin}')
    effective=effective_path or path.parent/'debug_hub_effective_debug_materialized.xdc'
    if not effective.is_file():issues.append('missing actual hub effective constraint scope export')
    return {'source':file_id(path),'input_clocks':input_clocks,'outputs':outputs,'clocks':clocks,
            'actual_output_drivers':drivers,'actual_output_startpoints':starts,
            'relationship_qualified':not issues,'relationship_issues':issues,
            'effective_hub_constraints':file_id(effective) if effective.is_file() else None,
            'fanout_endpoint_count':len(endpoint_clocks),'fanout_by_output':{pin:sum(p==pin for p,_ in endpoint_clocks) for pin in outputs},
            'fanout_clock_names':sorted({clock for values in endpoint_clocks.values() for clock in values}),
            'declared_input_hz':declared,'actual_input_hz':input_hz,'divider':properties.get('C_ENABLE_CLK_DIVIDER'),
            'declared_matches_actual_input':math.isclose(declared,input_hz,rel_tol=1e-6),
            'review':'diagnostic relation only; declared frequency mismatch retained; unknown output ancestry or undivided period mismatch blocks place'}


def hook_batch(point: str, report: Path) -> None:
    """One small process validates every frozen row; avoids 339 large forks."""
    import os
    lineage = synth_lineage(*(Path(os.environ[k]).resolve() for k in
        ("HAP_PROJECT_DIR", "HAP_SYNTH_REPORT_DIR", "HAP_SYNTH_ATTEMPT_DIR")))
    input_manifest(report / "stage_inputs.sha256")
    constraints = constraint_chain(point, report)
    require(point != 'opt' or os.environ.get('HAP_EXECUTION_MODE') == 'checkpoint_restored_commands',
            'native project mode has no qualified explicit pre-place debug admission')
    gate_issues=[]
    def collect(name, action):
        try:return action()
        except Exception as exc:
            gate_issues.append(f'{name}: {type(exc).__name__}: {exc}')
            return None
    counts = collect('clock_counts',lambda:check_timing_counts(report / f"check_timing_{point}.rpt")) or {}
    bb = int(key_values(report / f"{point}_result.txt")["blackboxes"])
    coverage = collect('clock_coverage',lambda:phase_coverage(point, report, counts, bb, os.environ.get("HAP_EXECUTION_MODE") == "checkpoint_restored_commands"))
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


def debug_command_receipt(report: Path) -> dict:
    condition = key_values(report/'debug_materialization_condition.txt')
    count = int(condition['debug_core_count'])
    require(count >= 0 and condition.get('condition') == 'actual_get_debug_cores_nonempty', 'missing actual debug implementation condition')
    receipt = key_values(report/'debug_materialization_command_result.txt')
    expected = 'implement_debug_core' if count else 'set ::m002_debug_skipped no_debug_cores'
    require(receipt.get('command') == expected and receipt.get('phase') == 'debug_materialization' and
            receipt.get('native_tcl_code') == '0' and int(receipt['ended_epoch']) >= int(receipt['started_epoch']),
            'debug materialization command did not actually complete')
    return {'condition':file_id(report/'debug_materialization_condition.txt'),
            'command':file_id(report/'debug_materialization_command_result.txt')}


def verify_reset_proof(structure: dict) -> None:
    require(structure.get('qualified') is True, 'actual current reset proof is not qualified')
    verify_identity(structure['source'])
    for export in structure.get('explicit_primitive_exports',[]):
        verify_identity(export['netlist'])
        for identity in export.get('primitive_models',[]):verify_identity(identity)


def verify_cdc_proof(value: dict) -> None:
    if value.get('classification')=='classified_reset_cdc_diagnostic_only':
        require(value.get('formal_reset_cdc_safety')=='OPEN' and value.get('classified_opt_reset')==8 and
                value.get('new_critical')==0 and len(value.get('auxiliary_cdc_report_sources',[])) in {0,4} and
                len(value.get('proof_sources',[]))-len(value.get('auxiliary_cdc_report_sources',[])) in {4,5} and
                all(identity in value['proof_sources'] for identity in value.get('auxiliary_cdc_report_sources',[])),
                'invalid diagnostic-only reset CDC receipt')
        for identity in value['proof_sources']:verify_identity(identity)


def pre_place_evidence(report: Path, *, create: bool = False) -> dict:
    """Independent strict gate bound to the post-debug DCP before any placement."""
    if (report/'recovery_parent.json').is_file() and json.loads((report/'recovery_parent.json').read_text()).get('phase')=='post_debug_pre_place':
        return restored_pre_place_evidence(report,create=create)
    command = debug_command_receipt(report)
    result = key_values(report/'debug_materialized_result.txt')
    require(result.get('phase') == 'debug_materialized' and result.get('completed') == '1' and
            result.get('diagnostic_eligible') == '1' and result.get('blackboxes') == '0' and
            result.get('clock_coverage') == 'COMPLETE_INTERNAL', 'debug materialized pre-place admission incomplete')
    counts = check_timing_counts(report/'check_timing_debug_materialized.rpt')
    require(placement_coverage(counts, 0), 'debug materialized internal timing coverage incomplete')
    integrity = json.loads((report/'integrity_debug_materialized.json').read_text())
    require(integrity.get('phase') == 'debug_materialized' and integrity['reset_structure'].get('qualified') is True,
            'debug materialized actual reset structure is not qualified')
    verify_reset_proof(integrity['reset_structure'])
    verify_cdc_proof(integrity['cdc_classification'])
    require(not integrity.get('gate_issues') and integrity['debug_clock_observation'].get('relationship_qualified') is True,
            'actual pre-place debug output clock relationship unresolved')
    verify_identity(integrity['debug_clock_observation']['source'])
    verify_identity(integrity['debug_clock_observation']['effective_hub_constraints'])
    require(integrity['constraints'] == file_id(report/'constraints_debug_materialized.json') and
            integrity['cdc_classification'].get('new_critical') == 0, 'pre-place effective constraints/CDC integrity mismatch')
    constraints = json.loads((report/'constraints_debug_materialized.json').read_text())
    for name in constraints['hashes']:
        constraint_source(name, constraints)
    value = {**command, 'phase':'debug_materialized_pre_place', 'physical_signoff':False,
             'checkpoint':file_id(report/'debug_materialized.dcp'), 'clock_coverage':counts,
             **{k:file_id(report/n) for k,n in (
                 ('result','debug_materialized_result.txt'),('admission','admission_debug_materialized.txt'),
                 ('constraints','constraints_debug_materialized.json'),('integrity','integrity_debug_materialized.json'))}}
    if create:
        require(not (report/'place_command_result.txt').exists(), 'pre-place evidence created after placement')
        (report/'pre_place_evidence.json').write_text(json.dumps(value,indent=2)+'\n')
    else:
        old = json.loads((report/'pre_place_evidence.json').read_text())
        require(old == value, 'pre-place admission/checkpoint/command evidence changed')
    return value


def artifact_id(path: Path) -> dict:
    path = path.resolve(strict=True)
    require(path.is_file(), f"missing artifact {path}")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def verify_identity(identity: dict) -> None:
    require(artifact_id(Path(identity["path"])) == identity, f"evidence identity changed: {identity['path']}")


def manifest_records(path: Path) -> dict[Path, str]:
    records = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, "malformed archived stage manifest")
        digest, name = match.groups()
        source = Path(name)
        require(source.is_absolute() and source not in records, "duplicate/relative stage input")
        records[source] = digest
    require(bool(records), "empty stage input manifest")
    return records


def validate_stage_archive(report: Path, stage_identity: dict, archive_identity: dict) -> dict:
    verify_identity(stage_identity)
    verify_identity(archive_identity)
    archive = input_manifest(Path(archive_identity["path"]))
    require(all(p.parent == report / "stage_sources" for p in archive), "stage archive outside immutable source snapshot")
    original = manifest_records(Path(stage_identity["path"]))
    for source, digest in original.items():
        archived = report / "stage_sources" / source.name
        if archived in archive:
            require(archive[archived] == digest, "archived execution code differs from old stage manifest")
        else:
            require(source.is_file() and sha256(source) == digest, f"design/probe input changed: {source}")
    return original


def prior_hooks(project: Path) -> None:
    owner = json.loads((project / "m002_physical_hook_owner.json").read_text())
    require(owner["project"] == str(project), "foreign implementation hook owner")
    report = Path(owner["report"])
    require(report.is_relative_to(ROOT / "vivado/reports"), "foreign implementation hook report")
    command = json.loads((report / "command.json").read_text())
    require(command["stage"] == "place" and command["synthesis"]["project"] == str(project), "foreign prior hook command")
    records = validate_stage_archive(report, owner["stage_inputs"], owner["archive"])
    required = {Path(__file__).parent / "m002_impl_threads.tcl", *Path(__file__).parent.glob("m002_diagnostic_*_post.tcl")}
    require(required <= set(records), "prior hook provenance missing expected scripts")


def parent_recovered_place(path: Path, project: Path, lineage: dict) -> dict:
    value=json.loads(path.read_text());report=path.parent
    auth=full_impl.report_authorization(report)
    if auth:require(value.get('execution_authorization')==auth,'recovered E003 parent authorization mismatch')
    require(value.get('schema')==SCHEMA and value.get('stage')=='place' and value.get('execution_mode')=='checkpoint_restored_commands', 'wrong recovered parent mode/schema')
    require(value.get('execution_state')=='completed' and value.get('diagnostic_eligible') is True and value.get('physical_signoff') is False and
            value.get('project')==str(project) and value.get('synthesis')==lineage,'recovered parent is not a completed qualified diagnostic')
    launcher=key_values(report/'launcher_status.txt')
    require(launcher.get('exit_code')=='0' and launcher.get('native_exit_code')=='0' and launcher.get('stage')=='place' and launcher.get('project')==str(project) and launcher.get('reports')==str(report),'recovered parent launcher failed')
    status=json.loads((Path(value['managed_attempt'])/'status.json').read_text())
    require(status['stage']=='place' and status['project']==str(project) and status['report']==str(report) and status['exit_code']==0 and
            status['native_exit_code']==0 and not status['stop_reason'] and not status['owned_survivors'],'recovered parent supervisor failed/survivors')
    for key in ('checkpoint','stage_inputs','archived_stage_sources','native_checkpoint_manifest','implementation_settings','constraints','recovery_parent','actual_xdc_reads'):
        verify_identity(value[key])
    verify_identity(value['restored_runtime_settings'])
    require(key_values(Path(value['restored_runtime_settings']['path'])).get('ip_cache_after') == 'disable',
            'recovered parent actual checkpoint project cache policy is not disabled')
    validate_stage_archive(report,value['stage_inputs'],value['archived_stage_sources'])
    require(Path(value['checkpoint']['path'])==report/'physopt.dcp' and
            set(input_manifest(Path(value['native_checkpoint_manifest']['path'])))=={report/'physopt.dcp'},'recovered parent is not its actual physopt DCP')
    require(not value['native_parent_receipts'],'recovered parent must not fabricate project-run receipts')
    restarted=value.get('restored_checkpoint_phase')=='post_debug_pre_place'
    placed=value.get('restored_checkpoint_phase')=='post_place_pre_physopt'
    if placed:
        require(set(value.get('command_receipts',{}))=={'physopt'} and
                value.get('historical_command_receipts')==json.loads(Path(value['recovery_parent']['path']).read_text())['historical_command_receipts'],
                'placed parent historical/new command scopes mismatch')
        for identity in value['historical_command_receipts'].values():verify_identity(identity)
        verify_identity(value['physical_resume_admission']);physical_resume_evidence(report,frozen_source=True)
        verify_identity(value['completed_place_POST']);completed_placed_post(report)
    if restarted:
        require(set(value.get('command_receipts',{}))=={'place','physopt'} and
                value.get('historical_command_receipts')==json.loads(Path(value['recovery_parent']['path']).read_text())['historical_command_receipts'],
                'restarted parent historical/new command scopes mismatch')
        for identity in value['historical_command_receipts'].values():verify_identity(identity)
    log_derived_opt = value.get('inherited_opt_execution_proof')
    if log_derived_opt:
        require(auth and auth['profile'] == full_impl.OPTIMIZED_PROFILE, 'log-derived OPT inheritance outside E005')
        fresh_opt.verify_inherited_proof(sys.modules[__name__], log_derived_opt, project, lineage, report)
        require(set(value['command_receipts']) == {'debug_materialization','place','physopt'}, 'fresh OPT inherited/new command scopes changed')
    for point,command in ((('physopt','phys_opt_design'),) if placed else (('place','place_design'),('physopt','phys_opt_design')) if restarted or log_derived_opt else
                           (('opt','opt_design'),('place','place_design'),('physopt','phys_opt_design'))):
        identity=value['command_receipts'][point];verify_identity(identity)
        receipt=key_values(Path(identity['path']))
        require(receipt.get('native_tcl_code')=='0' and receipt.get('command')==fresh_opt.expected_physical_command(point, command, auth) and receipt.get('phase')==point,'recovered parent native phase failed')
    verify_identity(value['pre_place'])
    if not placed:pre_place_evidence(report)
    verify_identity(value['integrity'])
    integrity=json.loads(Path(value['integrity']['path']).read_text())
    require(integrity.get('phase') == 'physopt', 'parent final physical integrity phase mismatch')
    verify_reset_proof(integrity['reset_structure'])
    verify_cdc_proof(integrity['cdc_classification'])
    constraints=json.loads(Path(value['constraints']['path']).read_text())
    require(constraints['mode']=='embedded_checkpoint_inherited','recovered parent effective constraint mode changed')
    for name in constraints['hashes']:
        constraint_source(name, constraints)
    return value


def parent_place(path: Path, project: Path, lineage: dict) -> dict:
    value = json.loads(path.read_text())
    if value.get("execution_mode") == "checkpoint_restored_commands":
        return parent_recovered_place(path, project, lineage)
    require(value.get("schema") == SCHEMA and value.get("stage") == "place", "wrong parent diagnostic schema/stage")
    require(value.get("execution_state") == "completed" and value.get("diagnostic_eligible") is True,
            "parent placement is not a completed diagnostic candidate")
    require(value.get("project") == str(project) and value.get("physical_signoff") is False,
            "parent placement project/signoff identity mismatch")
    require(value["synthesis"] == lineage, "parent placement synthesis identity changed")
    report = path.parent
    launcher = key_values(report / "launcher_status.txt")
    require(launcher == {"stage": "place", "exit_code": "0", "native_exit_code": "0", "project": str(project), "reports": str(report)},
            "parent launcher did not actually succeed for this project/report")
    attempt = Path(value["managed_attempt"])
    status = json.loads((attempt / "status.json").read_text())
    require(status["stage"] == "place" and status["project"] == str(project) and status["report"] == str(report) and
            status["exit_code"] == 0 and status["native_exit_code"] == 0 and not status["stop_reason"] and
            not status["owned_survivors"], "parent supervisor did not actually finish successfully")
    command = json.loads((report / "command.json").read_text())
    require(command["managed_attempt"] == str(attempt) and command["synthesis"] == lineage and command["stage"] == "place",
            "parent command/managed identity mismatch")
    for key in ("checkpoint", "stage_inputs", "archived_stage_sources", "native_checkpoint_manifest", "implementation_settings", "constraints"):
        verify_identity(value[key])
    validate_stage_archive(report, value["stage_inputs"], value["archived_stage_sources"])
    native = input_manifest(Path(value["native_checkpoint_manifest"]["path"]))
    expected = project / "scalellm_vcu118_f05.runs/impl_1/scalellm_vcu118_f05_bd_wrapper_physopt.dcp"
    require(set(native) == {expected}, "parent native checkpoint is not this project's actual physopt")
    run = expected.parent
    receipts = value["native_parent_receipts"]
    require(set(receipts) == {".phys_opt_design.end.rst", ".vivado.end.rst"}, "missing native completion receipts")
    for name, identity in receipts.items():
        verify_identity(identity)
        require(sha256(run / name) == identity["sha256"], f"parent native completion receipt changed: {name}")
    require(not (run / ".phys_opt_design.error.rst").exists() and not (run / ".vivado.error.rst").exists(),
            "parent native implementation has an error receipt")
    old_constraints = json.loads(Path(value["constraints"]["path"]).read_text())
    require(all(Path(n).is_file() and sha256(Path(n)) == h for n, h in old_constraints["hashes"].items()), "parent effective XDC changed")
    return value


def route_counts(path: Path) -> dict:
    text = path.read_text()
    result = {}
    patterns = {"routable": r"# of routable nets", "fully_routed": r"# of fully routed nets",
                "unrouted": r"# of unrouted nets", "partially_routed": r"# of partially routed nets",
                "routing_errors": r"# of nets with routing errors"}
    for key, label in patterns.items():
        match = re.search(label + r"\s*[:|]?\s*([0-9,]+)", text, re.I)
        require(match is not None, f"missing actual route count: {key}")
        result[key] = int(match.group(1).replace(",", ""))
    require(result["routable"] > 0 and result["fully_routed"] <= result["routable"], "invalid/empty route statistics")
    result["complete"] = result["fully_routed"] == result["routable"] and all(
        result[k] == 0 for k in ("unrouted", "partially_routed", "routing_errors"))
    return result


def loaded_constraints(log: Path, output: Path, inherited: dict | None = None, effective: dict | None = None) -> dict:
    records = []
    for number, line in enumerate(log.read_text(errors="replace").splitlines(), 1):
        match = re.search(r"^Parsing XDC File \[([^]]+)\](?: for cell '([^']+)')?", line)
        if match:
            source = Path(match.group(1))
            real_source = constraint_source(str(source), effective) if effective else source
            require(real_source.is_file(), f"actual loaded constraint disappeared: {source}")
            records.append({"line": number, "path": str(source), "scope": match.group(2),
                            "sha256": sha256(real_source), "bytes": real_source.stat().st_size,
                            "retained_source": file_id(real_source) if real_source != source else None})
    require(bool(records) or inherited is not None, "no actual implementation XDC reads recorded")
    if inherited:
        if "recovery" in inherited:
            verify_identity(inherited["recovery"])
            original=json.loads(Path(inherited["recovery"]["path"]).read_text())
            require(original['phase'] in {'project_init_after_link_before_opt','post_opt_pre_debug','post_debug_pre_place','post_place_pre_physopt'} and original['actual_reads'], 'missing inherited project-init constraints')
            verify_identity(original['checkpoint'])
            inherited={"mode":"embedded_checkpoint_inherited","recovery_parent":inherited['recovery'],"original_actual_reads":original['actual_reads']}
        else:
            verify_identity(inherited["evidence"])
            parent = json.loads(Path(inherited["evidence"]["path"]).read_text())
            verify_identity(parent["constraints"])
            verify_identity(parent["actual_xdc_reads"])
            inherited = {"mode": "checkpoint_inherited", "parent_checkpoint": inherited["checkpoint"],
                         "parent_constraints": parent["constraints"], "parent_actual_reads": parent["actual_xdc_reads"]}
    output.write_text(json.dumps({"source_log": str(log), "records": records, "inherited": inherited}, indent=2) + "\n")
    return file_id(output)


def finalize(stage: str, project: Path, report: Path, lineage: dict, parent: dict | None) -> dict:
    import os
    restored = os.environ.get("HAP_EXECUTION_MODE") == "checkpoint_restored_commands"
    point = "physopt" if stage == "place" else "route"
    result = key_values(report / f"{point}_result.txt")
    require(result.get("completed") == "1" and result.get("diagnostic_eligible") == "1",
            "physical hook did not complete/admit this diagnostic candidate")
    metrics = timing_metrics(report / f"timing_{point}.rpt")
    counts = check_timing_counts(report / f"check_timing_{point}.rpt")
    require(placement_coverage(counts, int(result["blackboxes"])), "physical coverage incomplete")
    checkpoint = file_id(report / f"{point}.dcp")
    required = [f"timing_{point}.rpt", f"check_timing_{point}.rpt", f"clocks_{point}.rpt",
                f"clock_interaction_{point}.rpt", f"cdc_{point}.rpt", f"drc_{point}.rpt",
                f"exceptions_{point}.rpt", f"pulse_width_{point}.rpt", f"bus_skew_{point}.rpt",
                f"utilization_{point}.rpt", f"paths_setup_{point}.rpt", f"paths_hold_{point}.rpt"]
    if stage == "route":
        required.append("route_status_route.rpt")
    restored_parent=json.loads((report/'recovery_parent.json').read_text()) if restored and stage=='place' else None
    restarted_pre_place=bool(restored_parent and restored_parent.get('phase')=='post_debug_pre_place')
    restarted_placed=bool(restored_parent and restored_parent.get('phase')=='post_place_pre_physopt')
    log_derived_opt=bool(restored_parent and restored_parent.get('opt_execution_proof_kind')=='native_project_log_derived')
    if restarted_placed:
        physical_resume_evidence(report)
        completed_placed_post(report)
    elif restored and stage=='place':pre_place_evidence(report)
    evidence = {
        "schema": SCHEMA, "mode": "diagnostic", "stage": stage,
        "execution_mode": "checkpoint_restored_commands" if restored else "project_runs",
        "restored_checkpoint_phase": json.loads((report/'recovery_parent.json').read_text())['phase'] if restored and stage == 'place' else None,
        "recovery_parent": file_id(report / "recovery_parent.json") if restored and stage == "place" else None,
        "command_receipts": {p:file_id(report/f"{p}_command_result.txt") for p in
            (("physopt",) if restarted_placed else ("place","physopt") if restarted_pre_place else ("debug_materialization","place","physopt") if log_derived_opt else ("opt","debug_materialization","place","physopt") if stage == "place" else ("route",))} if restored else {},
        "historical_command_receipts": restored_parent["historical_command_receipts"] if restarted_pre_place or restarted_placed else {},
        "inherited_opt_execution_proof": restored_parent["inherited_opt_execution_proof"] if log_derived_opt else None,
        "command_execution_scope": "new_place_POST_physopt__inherited_opt_debug_place" if restarted_placed else "new_place_physopt__inherited_opt_debug" if restarted_pre_place else "original_stage_flow",
        "physical_resume_admission": file_id(report/"physical_resume_evidence.json") if restarted_placed else None,
        "completed_place_POST": file_id(report/"integrity_place.json") if restarted_placed else None,
        "pre_place": restored_parent["inherited_pre_place"] if restarted_placed else file_id(report/'pre_place_evidence.json') if restored and stage == 'place' else None,
        "integrity": file_id(report/f'integrity_{point}.json'),
        "execution_state": "completed", "diagnostic_eligible": True,
        "timing_verdict": "FAIL" if timing_verdict(metrics) == "FAIL" else "NOT_EVALUABLE",
        "timing_summary_verdict": timing_verdict(metrics), "bus_skew_review": "OPEN", "physical_signoff": False,
        "managed_attempt": __import__("os").environ["HAP_CURRENT_ATTEMPT_DIR"],
        "project": str(project), "part": "xcvu9p-flga2104-2L-e", "tool_version": "2025.2",
        "synthesis": lineage, "stage_inputs": file_id(report / "stage_inputs.sha256"),
        "archived_stage_sources": file_id(report / "archived_sources.sha256"),
        "implementation_settings": file_id(report / "implementation_settings.txt"),
        "implementation_settings_scope": "candidate_project_settings" if restored else "effective_project_run_settings",
        "restored_runtime_settings": file_id(report/'restored_runtime_settings.txt') if restored else None,
        "checkpoint": checkpoint, "metrics_ns": metrics, "clock_coverage": counts,
        "native_checkpoint_manifest": file_id(report / "implementation_checkpoint.sha256"),
        "constraints": file_id(report / f"constraints_{point}.json"),
        "native_parent_receipts": {} if restored else {name: artifact_id(report / "native_run_receipts" / name) for name in
            ((".phys_opt_design.end.rst", ".vivado.end.rst") if stage == "place" else (".route_design.end.rst", ".vivado.end.rst"))},
        "route": route_counts(report / "route_status_route.rpt") if stage == "route" else None,
        "drc_disposition": "no error/critical blocker; ordinary warnings retained",
        "cdc_review_status": "OPEN: reset CDC and CE-controlled memory classifications retained",
        "reports": {name: file_id(report / name) for name in required},
        "actual_xdc_reads": loaded_constraints(report / "implementation_run.log", report / "actual_xdc_reads.json",
            {"recovery":file_id(report / "recovery_parent.json")} if restored and stage == "place" else parent,
            json.loads((report/f'constraints_{point}.json').read_text()) if restored else None),
        "parent": parent,
    }
    auth=full_impl.report_authorization(report)
    if auth:
        evidence["execution_authorization"]=auth
        if stage=="route":full_impl.require_complete_route(evidence["route"])
    (report / "diagnostic_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


if __name__ == "__main__":
    import sys
    require(len(sys.argv) == 4, "expected ACTION PHASE REPORT")
    if sys.argv[1] == "hook-batch":
        hook_batch(sys.argv[2], Path(sys.argv[3]).resolve())
    elif sys.argv[1] == "constraints":
        constraint_chain(sys.argv[2], Path(sys.argv[3]).resolve())
    elif sys.argv[1] == "physical-resume":
        physical_resume_evidence(Path(sys.argv[3]).resolve(),create=True)
    elif sys.argv[1] == "pre-place":
        pre_place_evidence(Path(sys.argv[3]).resolve(), create=True)
    elif sys.argv[1] == "prior-hooks":
        prior_hooks(Path(sys.argv[3]).resolve())
    elif sys.argv[1] == "claim-hooks":
        import os
        project = Path(os.environ["HAP_PROJECT_DIR"])
        report = Path(sys.argv[3]).resolve()
        (project / "m002_physical_hook_owner.json").write_text(json.dumps({
            "project": str(project), "report": str(report),
            "stage_inputs": file_id(report / "stage_inputs.sha256"),
            "archive": file_id(report / "archived_sources.sha256")}, indent=2) + "\n")
    else:
        raise ValueError("unknown action")
