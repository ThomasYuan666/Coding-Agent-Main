import os
import subprocess
import difflib
from .workspace.path_utils import safe_path
from .testing.preview_server import start as start_preview, stop as stop_preview

def prepare_write(root, path, content):
    target = safe_path(root, path)
    exists = os.path.exists(target)
    old_content = open(target, encoding='utf-8').read() if exists else ''
    old_lines = old_content.splitlines(keepends=True)
    new_lines = content.splitlines(keepends=True)
    if not old_lines and old_content: old_lines = [old_content]
    if not new_lines and content: new_lines = [content]
    lines = []
    if not exists:
        lines = [{'type': 'added', 'text': line} for line in new_lines]
    else:
        for line in difflib.ndiff(old_lines, new_lines):
            if line.startswith('  '): lines.append({'type': 'same', 'text': line[2:]})
            elif line.startswith('- '): lines.append({'type': 'removed', 'text': line[2:]})
            elif line.startswith('+ '): lines.append({'type': 'added', 'text': line[2:]})
    return {'path': path, 'exists': exists, 'old_content': old_content, 'new_content': content, 'lines': lines}

def apply_write(root, change):
    target = safe_path(root, change['path'])
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, 'w', encoding='utf-8') as file:
        file.write(change['new_content'])
    return f'已写入 {change["path"]}'


def execute(name, arguments, root, approved=False):
    tool = name
    action = arguments
    if tool in {'write_file', 'delete_file', 'run_command'} and not approved:
        return {'needs_approval': True, 'command': action.get('command') or action.get('path', ''), 'reason': '此操作可能修改工作区'}
    try:
        if tool == 'start_preview':
            return start_preview(root)
        if tool == 'stop_preview':
            return stop_preview(root)
        if tool == 'read_file':
            with open(safe_path(root, action['path']), encoding='utf-8') as file:
                return {'result': file.read()}
        if tool == 'write_file':
            path = safe_path(root, action['path']); os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as file: file.write(action['content'])
            return {'result': f"已写入 {action['path']}"}
        if tool == 'delete_file':
            os.remove(safe_path(root, action['path']))
            return {'result': f"已删除 {action['path']}"}
        if tool == 'run_command':
            result = subprocess.run(action['command'], cwd=root, shell=True, capture_output=True, text=True, timeout=120)
            return {'result': f'退出码：{result.returncode}\n{result.stdout}{result.stderr}'.strip()}
        return {'result': f'未知工具：{tool}'}
    except Exception as exc:
        return {'result': f'工具执行失败：{exc}'}
