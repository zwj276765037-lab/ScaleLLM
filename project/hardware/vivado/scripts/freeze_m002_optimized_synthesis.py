#!/usr/bin/env python3
"""Bind a new successful E005 synthesis to actual produced and consumed DCPs."""
from pathlib import Path
import argparse
import json
import re
import m002_execution_profile as policy
import m002_synthesis_recovery as recovery
from m002_physical_evidence import input_manifest, file_id, sha256, require, synth_lineage, cdc_critical_records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('project','report','attempt'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--handover',type=Path,help='closed original same-PID supervision handover; no synthetic wait status')
    args=parser.parse_args();project,report,attempt=(getattr(args,k).resolve() for k in ('project','report','attempt'))
    require(not (attempt/'frozen_synthesis_anchor.json').exists(),'synthesis already frozen')
    if args.handover:
        recovery._base(project,report,attempt,args.handover.resolve())
    else:
        status=json.loads((attempt/'status.json').read_text())
        require(status.get('exit_code')==0 and status.get('native_exit_code')==0 and not status.get('stop_reason') and not status.get('owned_survivors'),'new synthesis did not complete cleanly')
    workspace=Path(__file__).resolve().parents[4]
    auth=policy.authorization(workspace,'synth',attempt,report,policy.OPTIMIZED_PROFILE)
    require(json.loads((attempt/'execution_authorization.json').read_text())==auth,'synthesis authorization changed')
    log=report/'vivado.log';raw=log.read_bytes();text=raw.decode(errors='replace')
    runs=[];produced={}
    for directory in sorted((project/'scalellm_vcu118_f05.runs').glob('*synth_1')):
        name=directory.name
        if name != 'synth_1' and not name.startswith('scalellm_vcu118_f05_bd_'):continue
        cp=directory/('scalellm_vcu118_f05_bd_wrapper.dcp' if name=='synth_1' else name.removesuffix('_synth_1')+'.dcp')
        end=directory/'.vivado.end.rst'
        require(cp.is_file() and end.is_file() and not (directory/'.vivado.error.rst').exists(),'incomplete actual synthesized run')
        runs.append(dict(run=name,checkpoint=str(cp),end_receipt=str(end)))
        require(cp.name not in produced,'duplicate produced DCP filename');produced[cp.name]=cp
    consumed=[]
    for number,line in enumerate(text.splitlines(),1):
        match=re.search(r"Reading design checkpoint '([^']+)' for cell '([^']+)'",line)
        if match:consumed.append(dict(line=number,path=match[1],cell=match[2]))
    require(len(runs)==23 and len(consumed)==22,'new actual top/OOC graph is not expected fixed board topology')
    allpaths={Path(x['checkpoint']) for x in runs}|{Path(x['path']) for x in consumed}
    require(len(allpaths)==45,'duplicate/incomplete new DCP graph')
    cpids={str(path):dict(bytes=path.stat().st_size,mtime_ns=path.stat().st_mtime_ns,sha256=sha256(path)) for path in sorted(allpaths)}
    pairs=[]
    for row in consumed:
        cp=Path(row['path']);source=produced[cp.name]
        require(cp.is_relative_to(project/'scalellm_vcu118_f05.gen') and cpids[str(cp)]['sha256']==cpids[str(source)]['sha256'],'consumed checkpoint differs from actual new OOC output')
        pairs.append(dict(produced=str(source),consumed=str(cp),sha256=cpids[str(cp)]['sha256']))
    binding=dict(observed_utc=policy.now().isoformat(),scope='new E005 produced top/OOC and native consumed IP paths',project=str(project),source_log=file_id(log),source_log_prefix_bytes=len(raw),source_log_prefix_sha256=sha256(log),run_records=runs,consumed_ip_records=consumed,identical_copy_pairs=pairs,checkpoints=cpids)
    policy.save(attempt/'synth_checkpoint_bindings.json',binding)
    (attempt/'synth_checkpoint_bindings.sha256').write_text(''.join(f"{cpids[str(path)]['sha256']}  {path}\n" for path in sorted(allpaths)))
    cdc=report/'cdc_post_synth.rpt';cdc_critical_records(cdc)
    rows=[];clocks={}
    for number,line in enumerate(cdc.read_text().splitlines(),1):
        for key in ('Source Clock','Destination Clock'):
            if line.startswith(key+':'):clocks[key]=line.split(':',1)[1].strip()
        if re.match(r'^\s*\d+\s+CDC-\d+\s+Critical\s+',line):rows.append(dict(line=number,source_clock=clocks['Source Clock'],destination_clock=clocks['Destination Clock'],raw=line.strip()))
    policy.save(attempt/'cdc_critical_rows.json',dict(observed_utc=policy.now().isoformat(),source=file_id(cdc),rows=rows))
    if args.handover:recovery.record_recovery(project,report,attempt,args.handover.resolve())
    names=['inputs.sha256','build_identity.txt','fresh_synth_complete.txt','synth_checkpoint_bindings.sha256','synth_checkpoint_bindings.json',recovery.RECEIPT if args.handover else 'status.json']
    anchors={name:sha256((report if name in names[:3] else attempt)/name) for name in names}
    policy.save(attempt/'frozen_synthesis_anchor.json',dict(project=str(project),report=str(report),execution_authorization=auth,source_rows=len(input_manifest(report/'inputs.sha256')),anchors=anchors))
    lineage=synth_lineage(project,report,attempt)
    policy.save(attempt/'qualified_synthesis_lineage.json',lineage)
    print(json.dumps(lineage,indent=2))


if __name__=='__main__':main()
