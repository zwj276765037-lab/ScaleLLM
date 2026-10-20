#!/usr/bin/env python3
"""Bounded console data projection and explicit agent status reports; no process control."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

import research

MAX_JSON = 2 * 1024 * 1024
MAX_RECORDS = 250
TEXT_CAP = 8000
TOTAL_TEXT_CAP = 400000


def read_json(path):
    if path.stat().st_size > MAX_JSON:
        raise research.ResearchError(f'console metadata exceeds {MAX_JSON} bytes: {path.name}')
    return research.read_json(path)


def stamp(path):
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()


class Reader:
    def __init__(self, root):
        self.root, self.used, self.warnings = root, 0, []

    def text(self, relative, cap=TEXT_CAP):
        path = research.checked(self.root, relative)
        if not path.exists():
            self.warnings.append(f'缺少记录：{relative}')
            return ''
        if not path.is_file():
            raise research.ResearchError(f'console document is not a file: {relative}')
        available = min(cap, max(0, TOTAL_TEXT_CAP - self.used))
        with path.open(encoding='utf-8') as stream:
            value = stream.read(available + 1)
        if len(value) > available:
            self.warnings.append(f'摘要已截短：{relative}')
        value = value[:available]
        self.used += len(value)
        return value

    def modified(self, relative):
        path = research.checked(self.root, relative)
        return stamp(path) if path.is_file() else None

    def records(self, data, kind):
        records = data['records'].get(kind, {})
        if not isinstance(records, dict) or any(not isinstance(v, dict) for v in records.values()):
            raise research.ResearchError(f'invalid {kind} registry')
        items = list(records.values())
        if len(items) > MAX_RECORDS:
            self.warnings.append(f'{kind} 超过 {MAX_RECORDS} 条，请按当前 mission 缩小范围。')
        return items[:MAX_RECORDS]


def explicit(text, field):
    found = re.findall(rf'(?im)^\s*(?:[-*]\s*)?{re.escape(field)}\s*[:：]\s*([^\n]+)', text)
    return found[-1].strip().rstrip('。.;；') if found else None


def execution(text):
    values = [explicit(text, key) for key in ('execution_state', 'Execution state')]
    for value in values:
        if value:
            match = re.match(r'(planned|running|blocked|failed|completed|paused)\b', value)
            if match:
                return match[1]
    return 'unknown'


def excerpt(text, maximum=240):
    lines = [line.strip().lstrip('#').strip() for line in text.splitlines() if line.strip() and not line.startswith(('<!--', '|', '---'))]
    return ' '.join(lines)[:maximum]


def thread_bindings(root, data):
    path = research.checked(root, 'agent/thread_bindings.json')
    if not path.is_file():
        return {}
    value = read_json(path)
    if not isinstance(value, dict) or value.get('schema') != 1 or not isinstance(value.get('bindings'), dict):
        raise research.ResearchError('invalid persistent conversation bindings')
    bindings = value['bindings']
    if len(bindings) > MAX_RECORDS:
        raise research.ResearchError('too many persistent conversation bindings')
    agents = data['records'].get('agent', {})
    for identifier, binding in bindings.items():
        if identifier not in agents or not isinstance(binding, dict):
            raise research.ResearchError(f'invalid agent conversation binding: {identifier}')
        if not isinstance(binding.get('id'), str) or not re.fullmatch(
                r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', binding['id']):
            raise research.ResearchError(f'invalid conversation ID: {identifier}')
        for field in ('hostId', 'title'):
            text = binding.get(field)
            if text is not None and (not isinstance(text, str) or len(text) > 500 or any(ord(c) < 32 for c in text)):
                raise research.ResearchError(f'invalid conversation {field}: {identifier}')
    return bindings


def projection(root):
    with research.project_lock(root):
        data = read_json(research.checked(root, '.research-agent/project.json', exists=True))
        if data.get('schema') != 1 or not isinstance(data.get('records'), dict):
            raise research.ResearchError('unsupported project registry')
        bindings = thread_bindings(root, data)
        reader = Reader(root)
        event_store = read_json(research.checked(root, '.research-agent/events.json', exists=True))
        if not isinstance(event_store, dict):
            raise research.ResearchError('invalid event registry; cannot establish review status')
        goal = reader.text('goal/goal.md')
        overview = reader.text('results/overview.md')
        experiments = []
        for item in reader.records(data, 'experiment'):
            paths = {key: f"{item['path']}/{folder}/summary.md" for key, folder in (
                ('source', 'experiment_source'), ('results', 'experiment_results'), ('status', 'experiment_status'))}
            texts = {key: reader.text(path) for key, path in paths.items()}
            status = texts['status']
            verdict = explicit(status, 'Research verdict') or explicit(status, 'verdict') or 'unassessed'
            if verdict not in research.VERDICTS:
                verdict = 'unassessed'
            experiments.append({'id': item['id'], 'title': item['title'], 'mission_id': item['mission'],
                                'small_mission_id': item['small_mission'], 'kind': item.get('experiment_kind'),
                                'execution_state': execution(status), 'verdict': verdict,
                                'applicability': explicit(status, 'Applicability') or explicit(status, 'applicability'),
                                'summaries': texts, 'summary_paths': paths,
                                'updated_at': reader.modified(paths['status'])})
        agents = []
        for item in reader.records(data, 'agent'):
            status_path = f"{item['path']}/status.md"
            status = reader.text(status_path)
            mission_text = reader.text(f"{item['path']}/mission.md", 4000)
            result = reader.text(f"{item['path']}/result.md", 4000)
            state_path = research.checked(root, f"{item['path']}/state.json")
            state = read_json(state_path) if state_path.is_file() else {}
            if not isinstance(state, dict) or state and state.get('schema') != 1:
                raise research.ResearchError(f"unsupported agent state: {item['id']}")
            if state:
                validate_report(root, {k: v for k, v in state.items() if k not in ('schema', 'reported_at')})
                if not isinstance(state.get('reported_at'), str):
                    raise research.ResearchError(f"agent report time missing: {item['id']}")
                dt.datetime.fromisoformat(state['reported_at'].replace('Z', '+00:00'))
            settings = research.resolve_settings(root, data, item['role'], item['small_mission'], item['id'])
            observed = state.get('execution_state') or execution(status)
            if observed not in (*research.STATES, 'unknown'):
                observed = 'unknown'
            binding = bindings.get(item['id'], {})
            thread_id = state.get('thread_id') or binding.get('id')
            matched_binding = thread_id is not None and thread_id == binding.get('id')
            agents.append({'id': item['id'], 'title': item['title'], 'role': item['role'],
                           'mission_id': item.get('mission') or research.record(data, 'small-mission', item['small_mission'])['mission'],
                           'small_mission_id': item['small_mission'], 'experiment_id': item.get('experiment'),
                           'execution_state': observed, 'current_task': state.get('current_task') or item['title'],
                           'stage': state.get('stage'), 'progress': state.get('progress'),
                           'blocker': state.get('blocker'), 'next_step': state.get('next_step'),
                           'resource': state.get('resource'), 'desired_model': settings['expected']['model'],
                           'desired_effort': settings['expected']['effort'], 'configuration_source': settings['source'],
                           'actual_model': state.get('actual_model'), 'actual_effort': state.get('actual_effort'),
                           'configuration_evidence': state.get('configuration_evidence'),
                           'runtime_id': state.get('runtime_id'), 'thread_id': thread_id,
                           'thread_host_id': binding.get('hostId') if matched_binding else None,
                           'thread_title': binding.get('title') if matched_binding else None,
                           'thread_binding_source': 'structured_report' if state.get('thread_id') else 'project_binding' if matched_binding else None,
                           'reported_at': state.get('reported_at'), 'record_updated_at': reader.modified(status_path),
                           'observation_source': 'structured_report' if state else 'markdown_record',
                           'status_document': status_path, 'mission_document': f"{item['path']}/mission.md",
                           'config_document': f"{item['path']}/config.md", 'result_document': f"{item['path']}/result.md",
                           'status_text': status, 'mission_text': mission_text, 'result_text': result})
        reviews = []
        for identifier, item in event_store.items():
            research.safe_id(identifier)
            if not isinstance(item, dict) or item.get('event_id') != identifier or item.get('trigger') not in research.TRIGGERS:
                raise research.ResearchError(f'invalid stage event: {identifier}')
            research.record(data, 'small-mission', item.get('small_mission'))
            for key in ('summary', 'impact', 'action', 'created_at'):
                research.nonempty(item.get(key), key)
            if type(item.get('requires_decision')) is not bool or any(not isinstance(item.get(k), list) for k in ('evidence', 'affected', 'reviews')):
                raise research.ResearchError(f'invalid event lists or decision requirement: {identifier}')
            for relative in item['evidence']:
                research.checked(root, relative)
            for decision in item['reviews']:
                if not isinstance(decision, dict) or decision.get('decision') not in research.DECISIONS:
                    raise research.ResearchError(f'invalid review history: {identifier}')
                for key in ('at', 'note'):
                    research.nonempty(decision.get(key), key)
            reviews.append({**item, 'status': item.get('reviews', [])[-1]['decision'] if item.get('reviews') else 'pending',
                            'last_decision_at': item.get('reviews', [])[-1]['at'] if item.get('reviews') else None,
                            'revision': research.event_revision(item), 'review_path': f"results/reviews/{item['small_mission']}.md"})
        reviews.sort(key=lambda v: (v['status'] not in ('approved', 'acknowledged'), v['requires_decision'], v['last_decision_at'] or v['created_at']), reverse=True)
        if len(reviews) > MAX_RECORDS:
            reader.warnings.append(f'阶段事件超过 {MAX_RECORDS} 条，优先显示待处理事项；完整历史保留在 results/reviews。')
            reviews = reviews[:MAX_RECORDS]
        questions = []
        for item in reader.records(data, 'question'):
            text = reader.text(f"{item['path']}/question.md", 4000)
            answer = reader.text(f"{item['path']}/answer.md", 4000)
            questions.append({'id': item['id'], 'title': item['title'], 'role': item.get('role'),
                              'small_mission_id': item.get('small_mission'), 'state': explicit(text, '状态') or explicit(text, 'status') or '待核实',
                              'question': text, 'answer': answer, 'question_path': f"{item['path']}/question.md", 'answer_path': f"{item['path']}/answer.md"})
        documents = {}
        for name, rel in {'goal': 'goal/goal.md', 'mission': 'mission/current.md', 'overview': 'results/overview.md',
                          'methods': 'source/method.md', 'hardware_metrics': 'results/hardware_metrics.md',
                          'hardware_progress': 'results/hardware_progress.md', 'method_verdicts': 'results/method_verdicts.md',
                          'software': 'results/software_experiments.md'}.items():
            path = research.checked(root, rel)
            if path.is_file():
                documents[name] = {'path': rel, 'content': goal if name == 'goal' else overview if name == 'overview' else reader.text(rel)}
        result = {'schema': 1, 'project': {'name': data['name'], 'root': str(root), 'goal': goal, 'overview': overview},
                  'agents': agents, 'experiments': experiments, 'reviews': reviews, 'questions': questions,
                  'missions': reader.records(data, 'mission'), 'small_missions': reader.records(data, 'small-mission'),
                  'documents': documents, 'warnings': reader.warnings, 'text_characters': reader.used,
                  'observation': 'durable project reports, not direct runtime process telemetry'}
        result['revision'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        result['read_at'] = research.now()
        return result


def validate_report(root, payload):
    allowed = {'execution_state', 'current_task', 'stage', 'progress', 'blocker', 'next_step', 'resource',
               'actual_model', 'actual_effort', 'configuration_evidence', 'runtime_id', 'thread_id'}
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise research.ResearchError('agent report contains unsupported fields')
    if payload.get('execution_state') not in research.STATES:
        raise research.ResearchError('agent report requires an execution_state')
    for field in allowed - {'progress', 'execution_state'}:
        value = payload.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 and c != '\n' for c in value)):
            raise research.ResearchError(f'invalid report field: {field}')
    progress = payload.get('progress')
    if progress is not None:
        if not isinstance(progress, dict) or set(progress) - {'completed', 'total', 'unit'}:
            raise research.ResearchError('invalid progress')
        complete, total = progress.get('completed'), progress.get('total')
        if type(complete) not in (int, float) or type(total) not in (int, float) or not 0 <= complete <= total or not total > 0 or total == float('inf'):
            raise research.ResearchError('progress requires 0 <= completed <= total and a finite positive total')
        if 'unit' in progress and (not isinstance(progress['unit'], str) or len(progress['unit']) > 100):
            raise research.ResearchError('invalid progress unit')
    actual_model, actual_effort = payload.get('actual_model'), payload.get('actual_effort')
    if actual_model is not None or actual_effort is not None:
        research.valid_model(actual_model, actual_effort)
        evidence = payload.get('configuration_evidence')
        if not evidence or not research.checked(root, evidence, exists=True).is_file():
            raise research.ResearchError('reported actual model requires project-relative configuration evidence')
    return dict(payload)


def report(args):
    root = research.root_path(args.root)
    payload = read_json(Path(args.input))
    with research.project_lock(root):
        data = research.project(root)
        agent = research.record(data, 'agent', args.agent)
        state = {'schema': 1, **validate_report(root, payload), 'reported_at': research.now()}
        state_path = research.checked(root, f"{agent['path']}/state.json")
        md_path = research.checked(root, f"{agent['path']}/status.md", exists=True)
        md = md_path.read_text(encoding='utf-8')
        progress = state.get('progress')
        lines = ['## 最新状态报告', '', f"execution_state: {state['execution_state']}", f"reported_at: {state['reported_at']}",
                 f"current_task: {state.get('current_task') or agent['title']}", f"stage: {state.get('stage') or '未报告'}",
                 f"progress: {progress['completed']}/{progress['total']} {progress.get('unit','')}" if progress else 'progress: 未报告',
                 f"blocker: {state.get('blocker') or '未报告'}", f"next_step: {state.get('next_step') or '未报告'}", '',
                 '此为负责人提供的状态报告；记录更新时间不等于进程心跳。']
        rendered = research.managed_content(md, '\n'.join(lines), 'agent-report')
        previous = state_path.read_text(encoding='utf-8') if state_path.exists() else None
        try:
            research.write_json(state_path, state)
            research.atomic_text(md_path, rendered)
        except Exception:
            if previous is None:
                state_path.unlink(missing_ok=True)
            else:
                research.atomic_text(state_path, previous)
            research.atomic_text(md_path, md)
            raise
        import organize
        navigation = organize.safe_refresh_locked(root)
    return {'agent': args.agent, 'reported_at': state['reported_at'], 'process_controlled': False, 'notification_delivered': False, 'navigation': navigation}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('snapshot'); p.add_argument('--root', required=True)
    p = sub.add_parser('report'); p.add_argument('--root', required=True); p.add_argument('--agent', required=True); p.add_argument('--input', required=True)
    p = sub.add_parser('document'); p.add_argument('--root', required=True); p.add_argument('--path', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'snapshot':
            value = projection(research.root_path(args.root))
        elif args.command == 'report':
            value = report(args)
        else:
            root = research.root_path(args.root)
            with research.project_lock(root):
                path = research.checked(root, args.path, exists=True)
                if path.suffix.lower() not in ('.md', '.txt', '.log', '.json', '.bib') or not path.is_file():
                    raise research.ResearchError('console supports text evidence and Markdown documents')
                with path.open(encoding='utf-8') as stream:
                    content = stream.read(131073)
                value = {'path': args.path, 'content': content[:131072], 'truncated': len(content) > 131072, 'modified': stamp(path)}
        print(json.dumps(value, ensure_ascii=False, allow_nan=False))
        return 0
    except (research.ResearchError, OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
