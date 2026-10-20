#!/usr/bin/env python3
"""Generate bounded project navigation without moving or judging research evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, unquote

import research

CONFIG = '.research-agent/navigation.json'
STATE = '.research-agent/navigation_state.json'
DISCUSSIONS = '.research-agent/discussions.json'
MARKER = 'navigation'
LIMIT = 1048576
ROLES = {'controller': '项目主控与架构评判', 'engineering': '工程实现与验证',
         'research': '研究探索与瓶颈分析', 'questions': '技术问答'}
DISCUSSION_STATES = {'awaiting_answer': '待答复', 'awaiting_implementation': '已答复待实施',
                     'awaiting_verification': '待验证', 'closed': '已关闭'}


def initialize(root, new=False):
    path = research.checked(root, CONFIG)
    if not path.exists():
        research.write_json(path, {'schema': 1, 'layout_version': 2 if new else 1,
                                  'current_mission': None, 'dependencies': {}, 'discussions': {}})


def cell(value, limit=230):
    return research.table_text(str(value or '未登记'), limit)


def slug(value):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip(' .')[:60] or '讨论'


def link(page, label, target):
    rel = os.path.relpath(target, str(Path(page).parent)).replace(os.sep, '/')
    return f'[{cell(label)}]({quote(rel, safe="/")})'


def detail_path(item):
    path = Path(item['path'])
    return ((path.parent if path.name == 'contract.md' else path.with_suffix('')) / 'README.md').as_posix()


class Reader:
    def __init__(self, root):
        self.root, self.inputs, self.warnings = root, {}, []

    def path(self, rel):
        return research.checked(self.root, rel)

    def text(self, rel):
        path = self.path(rel)
        if not path.is_file():
            return ''
        if path.stat().st_size > LIMIT:
            self.warnings.append(f'文件超过导航读取上限，未读取：{rel}')
            return ''
        raw = path.read_bytes()
        self.inputs[rel] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        return raw.decode('utf-8', errors='replace')

    def obj(self, rel):
        text = self.text(rel)
        if not text:
            return {}
        try:
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError('object expected')
            return value
        except (ValueError, TypeError):
            self.warnings.append(f'JSON未能读取，保持待核实：{rel}')
            return {}

    def children(self, rel):
        path = self.path(rel)
        if not path.is_dir():
            return []
        children = sorted(path.iterdir(), key=lambda p: p.name)
        if len(children) > 4096:
            raise research.ResearchError(f'Navigation directory exceeds 4096 direct entries: {rel}')
        # Do not follow links into code, model data or external experiments.
        return [p.relative_to(self.root).as_posix() for p in children if not p.is_symlink()]


def fields(text):
    found = {}
    for key, val in re.findall(r'^\s*(execution_state|verdict|review_state|Published|Publication|Research verdict):\s*(.+)$', text, re.M):
        found[key] = val.strip()
    return found


def excerpt(text, limit=900):
    # Preserve source prose; do not synthesize a scientific conclusion.
    body = text.split('\n---\n')[0].strip()
    return body[:limit] + ('\n\n（摘录截断；完整记录见链接。）' if len(body) > limit else '')


def rebase(reader, text, source, page):
    """Rebase quoted links; preserve unresolvable references as visible text."""
    def replace(match):
        label, target = match.groups()
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
            return match.group(0)
        raw = unquote(target.split('#', 1)[0])
        if raw.startswith(str(reader.root) + '/'):
            dest = Path(raw)
        elif re.match(r'^(goal|mission|project|results|source|question|agent)/', raw):
            dest = reader.root / raw
        else:
            dest = reader.root / Path(source).parent / raw
        try:
            rel = Path(os.path.normpath(dest)).relative_to(reader.root).as_posix()
            if reader.path(rel).exists():
                return link(page, label, rel)
        except (ValueError, research.ResearchError, OSError):
            pass
        reader.warnings.append('原文链接未解析：' + source + ' → ' + target)
        return label + '（原文引用：`' + target + '`；待核实）'
    return re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)', replace, text)


def discovered_links(reader, page, text):
    text = text.replace(str(reader.root) + '/', '')
    candidates = re.findall(r'(?:goal|mission|project|results|source|question|agent)/[^\s`<>\[\]()，。；]+', text)
    targets = []
    for candidate in candidates:
        rel = candidate.rstrip('.,;:')
        try:
            path = reader.path(rel)
            if path.exists() and rel not in targets:
                targets.append(rel)
        except (research.ResearchError, OSError):
            continue
    return [link(page, Path(rel).name, rel) for rel in targets[:40]]


def collect(root):
    reader = Reader(root)
    data = reader.obj('.research-agent/project.json')
    if data.get('schema') != 1 or not isinstance(data.get('records'), dict):
        raise research.ResearchError('Invalid project registry; navigation preserved')
    config = research.read_json(reader.path(CONFIG)) if reader.path(CONFIG).exists() else {'schema': 1, 'layout_version': 1, 'current_mission': None, 'dependencies': {}, 'discussions': {}}
    if config.get('schema') != 1 or not isinstance(config.get('discussions'), dict):
        raise research.ResearchError('Invalid navigation configuration; existing identities preserved')
    groups = data['records']
    missions, experiments, runs, agents = {}, {}, {}, {}
    for mid, item in sorted(groups['mission'].items()):
        contract = reader.text(item['path'])
        summary = f'results/missions/{mid}_summary.md'
        missions[mid] = {**item, 'contract_text': contract, 'summary_path': summary,
                         'summary_text': reader.text(summary), 'detail': detail_path(item),
                         'tasks': [sm for sm in groups['small-mission'].values() if sm.get('mission') == mid]}
        for sm in missions[mid]['tasks']:
            sm['contract_text'] = reader.text(sm['path'])
            sm['review_path'] = f"results/reviews/{sm['id']}.md"
            sm['review_text'] = reader.text(sm['review_path'])
    for eid, item in sorted(groups['experiment'].items()):
        exp = {**item, 'documents': {}, 'runs': [], 'legacy': []}
        for kind, rel in [('source', 'experiment_source/summary.md'), ('protocol', 'experiment_source/protocol.md'),
                          ('results', 'experiment_results/summary.md'), ('status', 'experiment_status/summary.md')]:
            path = item['path'] + '/' + rel
            exp['documents'][kind] = {'path': path, 'text': reader.text(path)}
        exp['reported'] = fields(exp['documents']['status']['text'])
        for runpath in reader.children(item['path'] + '/experiment_results/runs'):
            if not re.fullmatch(r'R\d{3,}', Path(runpath).name) or not reader.path(runpath).is_dir():
                continue
            run = {'path': runpath, 'id': Path(runpath).name, 'experiment': eid,
                   'record': reader.text(runpath + '/run.md'), 'attempts': [], 'notes': [], 'evidence': []}
            children = reader.children(runpath)
            if reader.path(runpath + '/attempts').is_dir():
                children += reader.children(runpath + '/attempts')
            for child in children:
                path = reader.path(child)
                if path.is_file() and path.suffix == '.md' and path.name not in ('README.md', 'run.md'):
                    run['notes'].append(child)
                if path.is_file() and path.name in ('copy_receipt.json', 'receipt.json', 'input_manifest.json', 'manifest.json', 'execution_identity.json', 'verification.json', 'result.json', 'status.json'):
                    run['evidence'].append(child)
                    reader.text(child)
                if not path.is_dir() or path.name in ('data', 'logs', 'reports', 'attempts', 'publication_history', 'preimage', 'work'):
                    continue
                metadata = {}
                receipt = None
                for name in ('run.json', 'receipt.json', 'result.json', 'verification.json', 'copy_receipt.json'):
                    if reader.path(child + '/' + name).is_file():
                        receipt = child + '/' + name
                        metadata = reader.obj(receipt)
                        break
                evidence = [child + '/' + name for name in ('report.md', 'results.md', 'input_manifest.json', 'manifest.json')
                            if reader.path(child + '/' + name).is_file()]
                if receipt or evidence or '/attempts/' in child:
                    phases = []
                    for phase in ('static', 'pilot', 'full'):
                        phase_meta = metadata.get(phase)
                        if isinstance(phase_meta, dict):
                            phases.append(phase + '=' + str(phase_meta.get('status', '未登记')))
                    status = '; '.join(phases) or metadata.get('execution_state') or metadata.get('status') or '未登记；查看原记录'
                    run['attempts'].append({'path': child, 'name': path.name, 'receipt': receipt,
                                            'status': status, 'scope': metadata.get('scope', metadata.get('applicability', '')),
                                            'evidence': evidence})
            exp['runs'].append(runpath)
            runs[runpath] = run
        for legacy in reader.children(item['path'] + '/experiment/results'):
            if reader.path(legacy).is_dir():
                summary = next((legacy + '/' + n for n in ('stage_results.md', 'summary.md', 'results.md', 'README.md')
                                if reader.path(legacy + '/' + n).is_file()), legacy)
                exp['legacy'].append(summary)
        experiments[eid] = exp
    for aid, item in sorted(groups['agent'].items()):
        agents[aid] = {**item, 'report': reader.obj(item['path'] + '/state.json')}
    workspace = reader.obj('.research-agent/codex_workspace.json')
    receipts = []
    for path in reader.children('.research-agent/communications'):
        if path.endswith('.json'):
            receipt = reader.obj(path)
            if receipt.get('id'):
                receipts.append({**receipt, 'receipt_path': path})
    receipts.sort(key=lambda m: (m.get('created_at', ''), m['id']))
    message_by_id = {m['id']: m for m in receipts}
    root_for = {}
    for m in receipts:
        current, seen = m, set()
        while current.get('in_reply_to') in message_by_id and current['id'] not in seen:
            seen.add(current['id'])
            current = message_by_id[current['in_reply_to']]
        if current['id'] in seen:
            reader.warnings.append('回复链存在循环：' + m['id'])
        elif current.get('in_reply_to') and current.get('in_reply_to') not in message_by_id:
            reader.warnings.append('回复链缺少原消息：' + current['in_reply_to'])
        root_for[m['id']] = current['id']
    mapping = config.setdefault('discussions', {})
    next_id = max([int(v['id'][1:]) for v in mapping.values()] + [0]) + 1
    discussions = {}
    overrides = research.read_json(reader.path(DISCUSSIONS)) if reader.path(DISCUSSIONS).exists() else {}
    reader.text(DISCUSSIONS)
    if not isinstance(overrides, dict):
        raise research.ResearchError('Invalid discussion state store; history preserved')
    for m in receipts:
        rid = root_for[m['id']]
        if rid not in mapping:
            first = message_by_id[rid]
            title = next((line.strip('# ').strip() for line in first.get('text', '').splitlines() if line.strip()), rid)
            cid = f'C{next_id:03d}'
            next_id += 1
            mapping[rid] = {'id': cid, 'title': title[:100], 'path': 'communication/' + cid + '_' + slug(title)}
        identity = mapping[rid]
        cid = identity['id']
        if cid not in discussions:
            discussions[cid] = {**identity, 'messages': [], 'root_message': rid}
        discussions[cid]['messages'].append(m)
    for cid, d in discussions.items():
        delivered = [m for m in d['messages'] if m.get('status') == 'delivered']
        replied = any(m.get('in_reply_to') and m.get('kind') in ('answer', 'decision') for m in delivered)
        d['state'] = 'awaiting_implementation' if replied else 'awaiting_answer'
        d['state_basis'] = '有回复，实施/验证闭环待负责人确认' if replied else '尚无已归档答复；不代表对方未处理'
        history = overrides.get(cid, [])
        d['history'] = history
        if history:
            d['state'] = history[-1]['state']
            d['state_basis'] = history[-1]['note']
    # Only management files and one level of the global result directory are examined.
    references = []
    for path in reader.children('results'):
        if path.endswith('.md') and Path(path).name != 'index.md':
            text = reader.text(path)
            ids = [m['id'] for m in receipts if m['id'] in text]
            references.append({'path': path, 'text': text, 'message_ids': ids})
    return {'name': data['name'], 'config': config, 'reader': reader, 'missions': missions,
            'experiments': experiments, 'runs': runs, 'agents': agents, 'workspace': workspace,
            'discussions': discussions, 'references': references, 'questions': groups.get('question', {}),
            'goal': reader.text('goal/goal.md'), 'overview': reader.text('results/overview.md'),
            'current': reader.text('mission/current.md'), 'events': reader.obj('.research-agent/events.json')}


def render(snapshot):
    s, pages = snapshot, {}
    r = s['reader']
    def put(page, title, lines):
        pages[page] = '\n'.join(['# ' + title, '', *lines, '',
                                 '本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。', ''])
    p = 'README.md'
    current_id = s['config'].get('current_mission')
    current = s['missions'].get(current_id)
    lines = [f"项目根：`{r.root}`", '', '## 查看入口', '',
             '| 记录 | 入口 |', '| --- | --- |']
    for label, target in [('目标与历史', 'goal/goal.md'), ('所有 mission', 'mission/index.md'),
                          ('实验与每次结果', 'project/index.md'), ('agent 讨论与待办', 'communication/index.md'),
                          ('用户技术问答', 'question/index.md'), ('四个职责会话', 'agent/index.md'),
                          ('全项目报告与历史', 'results/index.md')]:
        lines.append('| ' + label + ' | ' + link(p, '打开', target) + ' |')
    lines += ['', '## 当前任务', '']
    if current:
        lines += [link(p, current_id + ' · ' + current['title'], current['detail']), '',
                  '合同：' + link(p, '原始任务定义', current['path'])]
        deps = s['config'].get('dependencies', {}).get(current_id, [])
        if deps:
            lines += ['前置任务：' + '、'.join(link(p, d + ' · ' + s['missions'][d]['title'], s['missions'][d]['detail']) for d in deps)]
    else:
        lines += ['当前 mission 尚未明确登记。', link(p, '负责人维护的当前任务记录', 'mission/current.md')]
    if s['config'].get('implementation_root'):
        lines += ['唯一实现入口：' + link(p, '工程代码', s['config']['implementation_root'])]
    lines += ['', '## 最新执行报告', '', '| 职责 | 当前任务 / 阶段 | 执行状态 | 上报时间 | 下一步 / 阻塞 |', '| --- | --- | --- | --- | --- |']
    for a in s['agents'].values():
        report = a['report']
        lines.append('| ' + ' | '.join([cell(a['title']), cell((report.get('current_task') or '') + '\n' + (report.get('stage') or '')),
                                       cell(report.get('execution_state')), cell(report.get('reported_at')),
                                       cell((report.get('next_step') or '') + '\n' + (report.get('blocker') or ''))]) + ' |')
    lines += ['', '## 当前证据范围（来自负责人概览，截取）', '', rebase(r, excerpt(s['overview'], 1800), 'results/overview.md', p), '',
              link(p, '完整概览及审核来源', 'results/overview.md'), '', '## 最近讨论', '']
    for d in sorted(s['discussions'].values(), key=lambda x: x['messages'][-1].get('created_at', ''), reverse=True)[:6]:
        lines += ['- ' + link(p, d['id'] + ' · ' + d['title'], d['path'] + '/thread.md') + ' — ' + DISCUSSION_STATES[d['state']]]
    if not s['discussions']:
        lines += ['暂无已归档跨会话消息。']
    put(p, s['name'] + ' 项目首页', lines)
    p = 'mission/index.md'
    lines = ['| Mission | 详情 | 合同 | 任务总结的状态（仅该报告范围） | 关联实验 / 前置 |', '| --- | --- | --- | --- | --- |']
    for mid, m in s['missions'].items():
        reported = fields(m['summary_text'])
        es = [e['id'] for e in s['experiments'].values() if e.get('mission') == mid]
        deps = s['config'].get('dependencies', {}).get(mid, [])
        lines.append('| ' + ' | '.join([mid, link(p, m['title'], m['detail']), link(p, '合同', m['path']),
                                       cell(reported.get('execution_state')) + ' / ' + cell(reported.get('verdict')),
                                       cell(', '.join(es)) + '；前置 ' + cell(', '.join(deps))]) + ' |')
        mp = m['detail']
        detail = [link(mp, '任务合同', m['path']) + ' · ' + link(mp, '任务总结', m['summary_path']), '',
                  '## 执行子任务与主控审核', '', '| 子任务 | 定义 | 完整审核历史 |', '| --- | --- | --- |']
        for sm in m['tasks']:
            detail += ['| ' + cell(sm['id'] + ' · ' + sm['title']) + ' | ' + link(mp, '定义', sm['path']) + ' | ' + link(mp, '审核', sm['review_path']) + ' |']
        detail += ['', '## 关联实验', '']
        for e in s['experiments'].values():
            if e.get('mission') == mid:
                detail += ['- ' + link(mp, e['id'] + ' · ' + e['title'], e['path'] + '/README.md') + ' — ' + cell(e['reported'].get('execution_state'))]
        for dep in s['config'].get('dependencies', {}).get(mid, []):
            detail += ['- 前置：' + link(mp, dep + ' · ' + s['missions'][dep]['title'], s['missions'][dep]['detail'])]
        detail += ['', '## 任务总结原文摘录', '', rebase(r, excerpt(m['summary_text'], 1600), m['summary_path'], mp), '', '## 相关决定、变更与讨论', '']
        for ref in s['references']:
            if mid in ref['text'] or any(sm['id'] in ref['text'] for sm in m['tasks']):
                detail += ['- ' + link(mp, Path(ref['path']).stem, ref['path'])]
        for d in s['discussions'].values():
            if any(mid in msg.get('text', '') for msg in d['messages']):
                detail += ['- ' + link(mp, d['id'] + ' · ' + d['title'], d['path'] + '/thread.md')]
        put(mp, mid + ' · ' + m['title'], detail)
    put(p, 'Mission 索引', lines)
    p = 'project/index.md'
    lines = ['| 实验 | 详情 | Mission / 子任务 | 最新发布的执行 / 研究状态 | 运行批次 |', '| --- | --- | --- | --- | --- |']
    for eid, e in s['experiments'].items():
        batch_links = ' · '.join(link(p, s['runs'][rp]['id'], rp + '/README.md') for rp in e['runs']) or '暂无运行批次'
        lines += ['| ' + eid + ' | ' + link(p, e['title'], e['path'] + '/README.md') + ' | ' + cell(e.get('mission')) + ' / ' + cell(e.get('small_mission')) + ' | ' + cell(e['reported'].get('execution_state')) + ' / ' + cell(e['reported'].get('verdict', e['reported'].get('Research verdict'))) + ' | ' + batch_links + ' |']
        ep = e['path'] + '/README.md'
        detail = ['关联：' + cell(e.get('mission')) + ' / ' + cell(e.get('small_mission')), '', '## 原始管理记录', '']
        for k, label in [('protocol', '实验协议'), ('source', '来源摘要'), ('results', '结果摘要'), ('status', '状态摘要')]:
            detail += ['- ' + link(ep, label, e['documents'][k]['path'])]
        detail += ['', '## 当前结果摘录', '', rebase(r, excerpt(e['documents']['results']['text'], 1400), e['documents']['results']['path'], ep), '',
                   '## 每个运行批次', '', '| 批次 | 详情 | 具体尝试数量 |', '| --- | --- | --- |']
        for runpath in e['runs']:
            run = s['runs'][runpath]
            detail += ['| ' + run['id'] + ' | ' + link(ep, '本批结果与证据', runpath + '/README.md') + ' | ' + str(len(run['attempts'])) + ' |']
            rp = runpath + '/README.md'
            runlines = [(link(rp, '负责人维护的本批运行记录', runpath + '/run.md') if run['record'] else '未发现独立 run.md；原目录和收据保留。'), '', rebase(r, excerpt(run['record'], 1200), runpath + '/run.md', rp), '',
                        '## 具体尝试与冻结结果', '', '| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |', '| --- | --- | --- | --- |']
            for at in run['attempts']:
                refs = ([link(rp, '执行收据', at['receipt'])] if at['receipt'] else []) + [link(rp, Path(f).name, f) for f in at['evidence']]
                runlines += ['| ' + link(rp, at['name'], at['path']) + ' | ' + cell(at['status']) + ' | ' + cell(at['scope']) + ' | ' + ' · '.join(refs) + ' |']
            runlines += ['', '## 本批问题与交付文件', '']
            runlines += ['- ' + link(rp, Path(n).name, n) for n in run['notes']]
            runlines += ['', '## 本批原始收据与输入身份', '']
            runlines += ['- ' + link(rp, Path(n).name, n) for n in run['evidence']]
            runlines += ['', '历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。']
            put(rp, eid + ' / ' + run['id'] + ' 运行结果', runlines)
        detail += ['', '## 原工程历史结果', '']
        detail += ['- ' + link(ep, Path(f).parent.name if f.endswith('.md') else Path(f).name, f) for f in e['legacy']]
        put(ep, eid + ' · ' + e['title'], detail)
    put(p, '实验与结果索引', lines)
    p = 'communication/index.md'
    lines = ['| 讨论 | 当前闭环状态 | 最新消息时间（UTC） | 消息数 |', '| --- | --- | --- | --- |']
    for cid, d in sorted(s['discussions'].items()):
        dp = d['path'] + '/thread.md'
        lines += ['| ' + link(p, cid + ' · ' + d['title'], dp) + ' | ' + DISCUSSION_STATES[d['state']] + ' | ' + cell(d['messages'][-1].get('created_at')) + ' | ' + str(len(d['messages'])) + ' |']
        detail = ['状态：**' + DISCUSSION_STATES[d['state']] + '**。' + d['state_basis'], '',
                  '送达状态与实施、验证状态分别登记。旧讨论的闭环状态需负责人确认，不能仅凭回复自动关闭。', '', '## 消息时间线', '']
        for msg in d['messages']:
            detail += ['### ' + msg['id'], '', cell(msg.get('created_at')) + ' · ' + ROLES.get(msg.get('from_role'), cell(msg.get('from_role'))) + ' → ' + ROLES.get(msg.get('to_role'), cell(msg.get('to_role'))),
                       '', '类型：' + cell(msg.get('kind')) + '；送达：' + cell(msg.get('status')) + '；回复关联：' + cell(msg.get('in_reply_to')),
                       '', rebase(r, msg.get('text', '（正文未归档）'), msg.get('message_file', 'message.md'), dp), '', link(dp, '原始消息收据', msg['receipt_path'])]
            linked = discovered_links(r, dp, msg.get('text', ''))
            if linked:
                detail += ['', '相关文件：' + ' · '.join(linked)]
        detail += ['', '## 相关决定和审核', '']
        for ref in s['references']:
            if set(ref['message_ids']) & {m['id'] for m in d['messages']}:
                detail += ['- ' + link(dp, Path(ref['path']).stem, ref['path'])]
        for transition in d['history']:
            detail += ['', '### 状态确认 ' + transition['at'], '', ROLES[transition['by']] + '：' + transition['note'] + ' → ' + DISCUSSION_STATES[transition['state']],
                       '', ' · '.join(link(dp, Path(f).name, f) for f in transition['evidence'])]
        put(dp, cid + ' · ' + d['title'], detail)
    lines += ['', '本列表覆盖统一通信账本中的消息；未归档的原生会话历史不冒充已归档记录。']
    put(p, '会话通信与待办索引', lines)
    p = 'question/index.md'
    lines = ['| 用户问题 | 定义 | 回答与依据 |', '| --- | --- | --- |']
    for qid, q in sorted(s['questions'].items()):
        lines += ['| ' + cell(qid + ' · ' + q['title']) + ' | ' + link(p, '问题', q['path'] + '/question.md') + ' | ' + link(p, '回答', q['path'] + '/answer.md') + ' |']
    if not s['questions']:
        lines += ['', '尚无以 Q 编号登记的用户问题。工程内部问题见 ' + link(p, '会话讨论', 'communication/index.md') + '。']
    for f in r.children('question'):
        if f.endswith('.md') and Path(f).name not in ('index.md', 'question_manage.md'):
            lines += ['- 旧问答记录：' + link(p, Path(f).stem, f)]
    put(p, '用户技术问答索引', lines)
    p = 'agent/index.md'
    lines = ['| 会话职责 | 实际对话 | 状态报告 | 负责人结果 |', '| --- | --- | --- | --- |']
    for role, label in ROLES.items():
        slot = s['workspace'].get('slots', {}).get(role, {})
        thread = slot.get('thread', {})
        actual = f"[进入会话](codex://threads/{thread['id']})" if thread.get('id') else '未绑定'
        a = next((a for a in s['agents'].values() if a.get('role') == role), None)
        lines += ['| ' + label + ' | ' + actual + ' | ' + (link(p, '最新状态', a['path'] + '/status.md') if a else '独立问答入口') + ' | ' + (link(p, '结果', a['path'] + '/result.md') if a else link(p, '用户问答', 'question/index.md')) + ' |']
    lines += ['', '内部 A 编号保留绑定兼容；当前工作以负责人的最新状态报告为准，不以旧登记归属替代。']
    put(p, '四个职责会话', lines)
    p = 'results/index.md'
    lines = ['全项目结果汇总的固定入口。新运行原始证据放在对应实验批次中；历史原位置保留。', '',
             '- ' + link(p, '当前概览', 'results/overview.md'), '- ' + link(p, '旧审核队列及正文历史（事件登记可能不完整）', 'results/review_queue.md'),
             '- ' + link(p, '所有任务及审核详情', 'mission/index.md'), '- ' + link(p, '所有实验及原始结果', 'project/index.md'), '', '## 既有专题报告', '']
    lines += ['- ' + link(p, Path(f['path']).stem, f['path']) for f in s['references'] if Path(f['path']).name not in ('index.md', 'overview.md', 'review_queue.md')]
    put(p, '全项目报告索引', lines)
    return pages


def check_pages(root, pages):
    errors = []
    for rel, body in pages.items():
        research.checked(root, rel)
        for target in re.findall(r'\]\(([^\s)]+)\)', body):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            target = unquote(target.split('#', 1)[0])
            dest = root / Path(rel).parent / target
            try:
                normalized = Path(os.path.normpath(dest)).relative_to(root).as_posix()
                # Generated pages may link to each other before their first write.
                if normalized not in pages and not (root / normalized).exists():
                    errors.append({'page': rel, 'target': target, 'reason': 'missing'})
            except ValueError:
                errors.append({'page': rel, 'target': target, 'reason': 'outside project'})
    return errors


def refresh_locked(root, dry_run=False):
    s = collect(root)
    pages = render(s)
    errors = check_pages(root, pages)
    if errors:
        raise research.ResearchError('Navigation links failed validation: ' + json.dumps(errors[:12], ensure_ascii=False))
    reader = s['reader']
    # Exclude generated state and timestamps: an unchanged refresh is idempotent.
    identity = {'inputs': {k: v for k, v in reader.inputs.items() if k not in (CONFIG, STATE)},
                'config': s['config'], 'pages': pages}
    revision = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    prior = reader.obj(STATE)
    generated_at = prior.get('generated_at') if prior.get('revision') == revision else research.now()
    writes, archives = {}, {}
    for rel, body in pages.items():
        path = research.checked(root, rel)
        text = path.read_text(encoding='utf-8') if path.is_file() else ''
        prefix = f'<!-- research-agent:{MARKER}:begin -->'
        if text and prefix not in text:
            raw = path.read_bytes()
            archive = '.research-agent/navigation_history/' + hashlib.sha256(raw).hexdigest() + '.md'
            archives[archive] = raw.decode('utf-8')
            text = '\n历史原文已保留：' + link(rel, '整理前原文', archive) + '\n'
        header = '生成时间（UTC）：' + generated_at + '。来源修订：`' + revision[:12] + '`。\n\n'
        rendered = research.managed_content(text, header + body, MARKER)
        if not path.exists() or path.read_text(encoding='utf-8') != rendered:
            writes[rel] = rendered
    # Validate all destinations before any mutation; refuse even intermediate symlinks.
    for rel in (*writes, *archives, CONFIG, STATE):
        research.checked(root, rel)
    result = {'ok': True, 'revision': revision, 'generated_at': generated_at, 'pages': len(pages),
              'changed_pages': len(writes), 'missions': len(s['missions']), 'experiments': len(s['experiments']),
              'runs': len(s['runs']), 'attempts': sum(len(v['attempts']) for v in s['runs'].values()),
              'discussions': len(s['discussions']), 'messages': sum(len(d['messages']) for d in s['discussions'].values()),
              'warnings': reader.warnings, 'broken_links': errors, 'dry_run': dry_run}
    if not dry_run:
        for rel, content in archives.items():
            research.create_text(root, rel, content)
        for rel, content in writes.items():
            research.atomic_text(research.checked(root, rel), content)
        if reader.obj(CONFIG) != s['config']:
            research.write_json(research.checked(root, CONFIG), s['config'])
        state = {**{k: v for k, v in result.items() if k not in ('changed_pages', 'dry_run')},
                 'inputs': {k: v for k, v in reader.inputs.items() if k not in (CONFIG, STATE)},
                 'page_hashes': {rel: hashlib.sha256(research.checked(root, rel).read_bytes()).hexdigest() for rel in pages}}
        state_path = research.checked(root, STATE)
        if not state_path.exists() or research.read_json(state_path) != state:
            research.write_json(state_path, state)
    return result


def refresh(root, dry_run=False):
    with research.project_lock(root):
        return refresh_locked(root, dry_run)


def safe_refresh_locked(root):
    try:
        return refresh_locked(root)
    except (research.ResearchError, OSError, ValueError, KeyError) as exc:
        # Delivery / experiment publication remains successful if navigation fails.
        return {'ok': False, 'error': str(exc), 'recovery': 'organize.py refresh --root ' + str(root)}


def configure(args):
    root = research.root_path(args.root)
    with research.project_lock(root):
        initialize(root)
        config = research.read_json(research.checked(root, CONFIG))
        data = research.project(root)
        if getattr(args, 'upgrade_layout', False):
            config['layout_version'] = 2
        if args.current_mission:
            research.record(data, 'mission', args.current_mission)
            config['current_mission'] = args.current_mission
        if args.implementation_root:
            research.checked(root, args.implementation_root, exists=True)
            config['implementation_root'] = args.implementation_root
        for dependency in args.dependency or []:
            current, previous = dependency.split(':')
            research.record(data, 'mission', current)
            research.record(data, 'mission', previous)
            if current == previous:
                raise research.ResearchError('A mission cannot depend on itself')
            config.setdefault('dependencies', {}).setdefault(current, [])
            if previous not in config['dependencies'][current]:
                config['dependencies'][current].append(previous)
        def visit(mid, active, done):
            if mid in active:
                raise research.ResearchError('Mission dependency cycle rejected')
            if mid in done:
                return
            for previous in config['dependencies'].get(mid, []):
                visit(previous, active | {mid}, done)
            done.add(mid)
        visited = set()
        for mid in config['dependencies']:
            visit(mid, set(), visited)
        research.write_json(research.checked(root, CONFIG), config)
        return refresh_locked(root)


def discussion(args):
    root = research.root_path(args.root)
    with research.project_lock(root):
        snapshot = collect(root)
        if args.id not in snapshot['discussions']:
            raise research.ResearchError('Unknown discussion ID')
        caller = os.environ.get('CODEX_THREAD_ID')
        thread = snapshot['workspace'].get('slots', {}).get(args.by, {}).get('thread', {}).get('id')
        if caller and caller != thread:
            raise research.ResearchError('Discussion owner does not match current chat')
        note = research.nonempty(args.note, 'note')
        evidence = research.evidence_paths(root, args.evidence or [])
        if args.state == 'closed' and not evidence:
            raise research.ResearchError('Closing a discussion requires implementation or verification evidence')
        path = research.checked(root, DISCUSSIONS)
        store = research.read_json(path) if path.exists() else {}
        store.setdefault(args.id, []).append({'state': args.state, 'by': args.by, 'note': note,
                                             'evidence': evidence, 'at': research.now()})
        research.write_json(path, store)
        return refresh_locked(root)


def attempt(args):
    root = research.root_path(args.root)
    if not re.fullmatch(r'AT\d{3,}', args.id) or not re.fullmatch(r'R\d{3,}', args.run):
        raise research.ResearchError('Expected Rxxx and ATxxx identities')
    title = research.literal_name(args.title, 'attempt title')
    with research.project_lock(root):
        exp = research.record(research.project(root), 'experiment', args.experiment)
        base = exp['path'] + '/experiment_results/runs/' + args.run
        research.checked(root, base + '/run.md', exists=True)
        candidates = list(research.checked(root, base).glob('attempts/' + args.id + '_*'))
        rel = base + '/attempts/' + args.id + '_' + title
        if candidates and candidates[0].relative_to(root).as_posix() != rel:
            raise research.ResearchError('Attempt ID already belongs to another title')
        payload = research.read_json(Path(args.input)) if args.input else {'execution_state': 'planned'}
        if not isinstance(payload, dict) or payload.get('execution_state') not in ('planned', 'running', 'completed', 'failed', 'cost_stop'):
            raise research.ResearchError('Attempt requires an explicit execution_state')
        payload = {**payload, 'schema': 1, 'id': args.id, 'experiment': args.experiment, 'run': args.run, 'title': title}
        if payload['execution_state'] in ('completed', 'failed', 'cost_stop'):
            for key in ('command', 'code_identity', 'input_identity', 'started_at', 'finished_at', 'scope'):
                research.nonempty(payload.get(key), key)
            if 'exit_status' not in payload:
                raise research.ResearchError('Terminal attempt requires exit_status, null only when no process was launched')
            research.evidence_paths(root, payload.get('evidence', []), exp['path'])
            if not payload.get('evidence'):
                raise research.ResearchError('Terminal attempt requires actual evidence')
        metadata = research.checked(root, rel + '/run.json')
        old = research.read_json(metadata) if metadata.exists() else None
        if old and old.get('execution_state') in ('completed', 'failed', 'cost_stop') and old != payload:
            raise research.ResearchError('Terminal attempt is immutable; create a new AT identity')
        if old != payload:
            if old:
                digest = hashlib.sha256(metadata.read_bytes()).hexdigest()
                research.create_text(root, rel + '/history/' + digest + '.json', metadata.read_text(encoding='utf-8'))
            research.write_json(metadata, payload)
        research.checked(root, rel + '/evidence').mkdir(parents=True, exist_ok=True)
        research.create_text(root, rel + '/report.md', '# ' + args.id + ' · ' + title + '\n\n记录目的、实际结果、适用范围、限制及原始证据。登记不代表已执行或通过。\n')
        return {'path': rel, 'execution_state': payload['execution_state'], 'navigation': safe_refresh_locked(root)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest='command', required=True)
    for command in ('refresh', 'check', 'configure', 'discussion', 'attempt'):
        p = sub.add_parser(command)
        p.add_argument('--root', required=True)
        if command == 'configure':
            p.add_argument('--current-mission')
            p.add_argument('--implementation-root')
            p.add_argument('--dependency', action='append')
            p.add_argument('--upgrade-layout', action='store_true', help='Use the new layout only for newly registered records; existing paths stay pinned')
        elif command == 'discussion':
            p.add_argument('--id', required=True)
            p.add_argument('--state', choices=DISCUSSION_STATES, required=True)
            p.add_argument('--by', choices=ROLES, required=True)
            p.add_argument('--note', required=True)
            p.add_argument('--evidence', action='append')
        elif command == 'attempt':
            p.add_argument('--experiment', required=True)
            p.add_argument('--run', required=True)
            p.add_argument('--id', required=True)
            p.add_argument('--title', required=True)
            p.add_argument('--input')
    args = cli.parse_args()
    try:
        if args.command in ('refresh', 'check'):
            value = refresh(research.root_path(args.root), args.command == 'check')
        else:
            value = {'configure': configure, 'discussion': discussion, 'attempt': attempt}[args.command](args)
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except (research.ResearchError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
