"""Closed actual congestion report and same-phase scope comparison only."""
import sys
sys.dont_write_bytecode=True
def guard(event,args):
    if event=='open' and args and isinstance(args[0],(str,bytes)):
        name=args[0].decode() if isinstance(args[0],bytes) else args[0]
        if name.lower().endswith('.dcp'):raise RuntimeError('DCP content access forbidden')
sys.addaudithook(guard)
import json,hashlib,re,itertools
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
ROOT=Path('/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM')
REPORT=ROOT/'project/hardware/vivado/reports/m002_E008_R001_AT004_C01_PDU_resume_full_implementation'
OUT=Path(__file__).resolve().parent
C01='scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf'
def read(path):return json.loads(Path(path).read_text())
def identity(path):
    path=Path(path).resolve();assert path.suffix.lower()!='.dcp';a=path.stat();h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4194304),b''):h.update(block)
    b=path.stat();assert(a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns)
    return dict(path=str(path),bytes=b.st_size,sha256=h.hexdigest())
def save(path,value):
    with path.open('x') as stream:stream.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
parent=read(REPORT/'recovery_parent.json')
paths=[REPORT/'congestion_place.rpt',Path(parent['source_report'])/'congestion_place.rpt']
ids=[identity(path) for path in paths]
assert ids[0]['bytes']==35748 and ids[0]['sha256']=='3d97ea117077657e671da6a087e176d3ad7c2fd5cd25501a604164f321b76191'
assert ids[1]['sha256']=='0b95a7cc6612be99e5208b93bad917c5edb2387dc18e63cb76f226943b6af868'

def parse(path):
    lines=path.read_text().splitlines()
    header={line[1:].split(':',1)[0].strip():line.split(':',1)[1].strip() for line in lines[:11] if line.startswith('|') and ':' in line}
    assert header['Design State']=='Fully Placed' and header['Design']=='scalellm_vcu118_f05_bd_wrapper'
    assert header['Command']=='report_design_analysis -congestion -min_congestion_level 3 -file '+str(path)
    assert 'Vivado v.2025.2' in header['Tool Version'] and 'Build 6299465' in header['Tool Version']
    heading=next(line for line in lines if line.startswith('| Direction'))
    columns=[value.strip() for value in heading.strip('|').split('|')]
    assert columns==['Direction','Type','Level','Window','Combined LUTs','Avg LUT Inputs','LUT','LUTRAM','Flop','MUXF','RAMB','URAM','DSP','CARRY','SRL','Cell Names']
    rows=[]
    for number,line in enumerate(lines,1):
        if not any(line.startswith('| '+direction) for direction in ['North','South','East','West']):continue
        values=[value.strip() for value in line.strip('|').split('|')];assert len(values)==len(columns)
        row=dict(zip(columns,values));row['line']=number;row['Level']=int(row['Level'])
        assert re.fullmatch(r'\([A-Z0-9_]+,[A-Z0-9_]+\)',row['Window'])
        for key in ['Combined LUTs','LUT','LUTRAM','Flop','MUXF','RAMB','URAM','DSP','CARRY','SRL']:
            value=row[key];assert value=='NA' or re.fullmatch(r'\d+%',value) and 0<=int(value[:-1])<=100
        assert 0<float(row['Avg LUT Inputs'])<=6
        row['listed_contributors']=[]
        for item in row['Cell Names'].split(','):
            match=re.fullmatch(r'(.+)\((\d+)%\)',item);assert match
            row['listed_contributors'].append(dict(NAME=match[1],reported_percent=int(match[2])))
        assert len(row['listed_contributors'])==3
        rows.append(row)
    assert len(rows)==48
    keys={(row['Direction'],row['Type'],row['Level']) for row in rows}
    assert keys==set(itertools.product(['North','South','East','West'],['Global','Long','Short'],[3,4,5,6]))
    return dict(header=header,rows=rows,rows_count=len(rows),levels=dict(Counter(row['Level'] for row in rows)),
        types=dict(Counter(row['Type'] for row in rows)),highest_reported_level=max(row['Level'] for row in rows),
        exact_C01_listed_rows=[dict(line=row['line'],Direction=row['Direction'],Type=row['Type'],Level=row['Level'],Window=row['Window'],C01_reported_percent=next(item['reported_percent'] for item in row['listed_contributors'] if item['NAME']==C01)) for row in rows if any(item['NAME']==C01 for item in row['listed_contributors'])],
        global_level6_windows=[{key:row[key] for key in ['Direction','Type','Level','Window','LUT','Flop','listed_contributors']} for row in rows if row['Type']=='Global' and row['Level']==6])
actual,old=[parse(path) for path in paths]
old_by_key={(row['Direction'],row['Type'],row['Level']):row for row in old['rows']}
same_windows=[row['Window'] for row in actual['rows'] if row['Window']==old_by_key[(row['Direction'],row['Type'],row['Level'])]['Window']]
assert not same_windows and not actual['exact_C01_listed_rows'] and len(old['exact_C01_listed_rows'])==24

markers=[]
with (REPORT/'vivado.log').open() as stream:
    for number,line in enumerate(stream,1):
        if line.startswith('report_design_analysis: Time (s):') or line.startswith('E005_OPTIMIZED_STRUCTURE_COMPLETED place'):
            markers.append(dict(line=number,text=line.rstrip()))
assert any(row['text'].startswith('report_design_analysis: Time (s):') for row in markers)
output=OUT/'place_congestion_scope_review.json'
save(output,dict(recorded_utc=datetime.now(timezone.utc).isoformat(),reviewer='A007',
    execution='completed_closed_native_congestion_text_parse_and_same_phase_comparison',
    verdict='accept_reported_adaptive_window_evidence; no_fixed_window_or_candidate_pressure_improvement_established',
    applicability='AT004 Fully Placed graph, native placer final level report with min_congestion_level3; no routed congestion or full POST/locality qualification',
    review='accepted_substep_no_new_gate',actual_report=ids[0],baseline_report=ids[1],actual=actual,baseline=old,
    same_direction_type_level_same_window_count=0,native_completed_report_lines=markers,
    observations=['Both reports contain 48 native rows: four directions, Global/Long/Short, levels3/4/5/6. Highest reported level remains6.',
        'All48 matched direction/type/level windows differ physically from the old report; direct row percentage subtraction is not a fixed-region comparison.',
        'The exact C01 hierarchy is named among the three listed contributors in0 current rows versus24 previous rows. This establishes only changed membership in the reported contributor lists; it does not prove zero candidate congestion, all-P landing, full absence from hot regions or causal relief.',
        'Native windows and exact contributor strings are preserved. No SLR column is present; coordinate Y alone is not independently mapped to SLR in this review.'],
    limits=['This is selected thresholded/adaptive placer window reporting, not an exhaustive fixed-bin demand/capacity map. Levels below3, unlisted windows and contributors are not a zero measurement.',
        'Fixed original hotspot window congestion remains UNAVAILABLE in this evidence; no separate query is launched.',
        'Listed LUT/Flop/BRAM/DSP/URAM percentages are native window resource fields, not SLL bandwidth, net demand, route completion probability or C01 resource fraction. NA remains NA.',
        'Only three hierarchy contributors are listed per row; their percentages can involve nested scopes. No whole-device or exclusive attribution is inferred by summation.',
        'Actual candidate reconciliation/SLR2 compliance and complete POST are separate. Full route status and routed timing remain required.',
        'No EDA/DCP/process control or production/consumed-package/engineering-summary edits.'],audit_program=identity(__file__)))
human=OUT/'place_congestion_scope_review.md'
with human.open('x') as stream:
    stream.write('# AT004 place 拥塞报告覆盖审核\n\n'
                 'execution：实际闭合报告解析完成；verdict：接受工具给出的自适应窗口证据，尚不支持固定窗口或候选压力改善；applicability：Fully Placed / min_congestion_level 3；review：A007，无新增停点。\n\n'
                 '本轮与旧 E005 都有 48 行：四方向 × Global/Long/Short × level3/4/5/6，最高报告 level 仍为 6。同方向/类型/level 的 48 个窗口坐标全部改变，不能直接相减窗口百分比当作同一区域改善。\n\n'
                 'C01 字面 hierarchy 在本轮每行所列的三个贡献者中出现 0 次，旧轮为 24 次。只能确认所列热点贡献者发生变化；缺席不能证明候选拥塞为零、所有 P 已迁移、完全离开热点或是 C01 导致的改善。候选实落仍待完整 locality/reconciliation。\n\n'
                 '报告提供工具选择的窗口、资源百分比及每行三个 hierarchy 贡献者，不是完整固定网格 demand/capacity，也未提供 SLR 列；本审核未将 tile Y 数值自行映射为 SLR。低于level3、未列窗口/贡献者不可当0，NA不改为0。原热点固定窗口拥塞仍为 UNAVAILABLE，本次没有额外查询。\n\n'
                 '保留当前高拥塞风险，待完整POST和最终route/timing验收；本子步骤不判断布通或C01方法成功。\n\n'
                 '[机器审核与实际窗口](place_congestion_scope_review.json)\n')
print(json.dumps(dict(review=identity(output),human=identity(human),rows=48,highest_reported_level=6,current_C01_listed_rows=0,prior_C01_listed_rows=24,same_windows=0),ensure_ascii=False))
