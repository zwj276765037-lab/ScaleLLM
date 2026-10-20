#!/usr/bin/env python3
"""User-authorized hourly wakeups of this existing engineering chat only."""
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import sys
import time
import uuid
from zoneinfo import ZoneInfo


def atomic(path, data):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    folder = args.config.resolve().parent
    lock = (folder / 'scheduler.lock').open('a+')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    config = json.loads(args.config.read_text())
    if args.check:
        print(json.dumps({'enabled': config['enabled'], 'thread_id': config['thread_id'],
            'next_report': datetime.fromtimestamp(config['next_due_epoch'], ZoneInfo('Asia/Shanghai')).isoformat(),
            'interval_seconds': config['interval_seconds'], 'unresolved_delivery': config.get('unresolved_delivery')}, ensure_ascii=False))
        return
    now = time.time()
    if not args.probe and (not config['enabled'] or now < config['next_due_epoch'] or config.get('unresolved_delivery')):
        return
    sys.path.insert(0, config['rpc_helper_directory'])
    from codex_rpc import CodexRpc
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    receipt_path = folder / 'receipts' / (('probe_' if args.probe else 'hourly_') + stamp + '.json')
    receipt_path.parent.mkdir(exist_ok=True)
    receipt = {'created_at': datetime.now(timezone.utc).isoformat(), 'thread_id': config['thread_id'],
               'client_user_message_id': str(uuid.uuid4()), 'state': 'prepared', 'probe': args.probe}
    sending = False
    try:
        with CodexRpc(timeout=30) as rpc:
            current = rpc.request('thread/read', {'threadId': config['thread_id'], 'includeTurns': False})['thread']
            if current['id'] != config['thread_id'] or current['cwd'] != config['project_root']:
                raise RuntimeError('Live chat identity or project directory changed; refusing delivery')
            receipt['recipient_status_before'] = current.get('status')
            if args.probe:
                prompt = ('[GSM8K每小时汇报：本机定时通道连通性测试]\n'
                    '用户已在本对话明确要求“一小时汇报一次进度”。这是为落实该请求进行的一次通道测试，'
                    '不是新的工程指令。保持当前任务和授权；不要重复创建定时器、不要启动额外实验。'
                    '在本轮最终答复中确认本对话已收到测试即可，定时器首次正式汇报仍按配置中的一小时后执行。')
            else:
                prompt = ('[GSM8K每小时进度汇报：用户授权的本机定时触发]\n'
                    '用户原话：“一小时汇报一次进度”。每次都应向用户报告，运行无变化也需简短说明；'
                    '这是汇报请求，不代表新增工程授权。\n'
                    f"项目：{config['project_root']}\n配置与投递证据：{args.config.resolve()}\n"
                    '读取E010最新三摘要及当前实际运行的current_state.json、worker manifest/summary，必要时核对PID。'
                    '先用北京时间报告：当前smoke/pilot/formal阶段、各阶段完成组数/30、正式已完成题数/39570、'
                    '两张GPU各自模型/配置与进度、本小时增量、失败/阻塞和下一步。'
                    '只在有实测依据时估算剩余时间；无NVML则不得编造利用率。'
                    '训练smoke/pilot不能当正式ACC，正式结果仅在独立复算完整通过后报告。'
                    '若发现已失败须明确报告并按原授权继续常规排查，保持原始证据、单卡单worker、M003硬件禁区；'
                    '不要因本通知终止正常GPU任务，不改全局接口或放宽验收。'
                    '本定时器只唤醒当前对话，不绑定或通知其他旧会话。'
                    '补测完整完成并汇报最终表格后，将此配置enabled设为false，结束每小时提醒；'
                    '用户要求停止时也关闭配置。')
            receipt['prompt'] = prompt
            receipt['state'] = 'sending'
            atomic(receipt_path, receipt)
            # Pre-mark delivery uncertainty so a crash cannot cause duplicate sends.
            config['unresolved_delivery'] = str(receipt_path)
            atomic(args.config, config)
            sending = True
            result = rpc.request('turn/start', {'threadId': config['thread_id'],
                'clientUserMessageId': receipt['client_user_message_id'],
                'input': [{'type': 'text', 'text': prompt}]})
            turn_id = result.get('turn', {}).get('id')
            if not turn_id:
                raise RuntimeError('No turn identity in wakeup acceptance')
            receipt.update(state='accepted', accepted_at=datetime.now(timezone.utc).isoformat(), turn_id=turn_id)
            atomic(receipt_path, receipt)
            config['unresolved_delivery'] = None
            config['last_acceptance'] = str(receipt_path)
            if not args.probe:
                config['last_report_trigger_epoch'] = now
                while config['next_due_epoch'] <= now:
                    config['next_due_epoch'] += config['interval_seconds']
            atomic(args.config, config)
            print(json.dumps({'state': 'accepted', 'turn_id': turn_id, 'receipt': str(receipt_path)}, ensure_ascii=False))
    except Exception as exc:
        receipt.update(state='unknown' if sending else 'failed_before_send', error=str(exc))
        atomic(receipt_path, receipt)
        if not sending:
            config['last_error'] = str(receipt_path)
            atomic(args.config, config)
        raise


if __name__ == '__main__':
    main()
