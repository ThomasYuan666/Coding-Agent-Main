import os
import subprocess
from .path_utils import safe_path


def execute(name, arguments, root, approved=False):
    tool = name
    action = arguments
    if tool in {'write_file', 'delete_file', 'run_command'} and not approved:
        return {'needs_approval': True, 'command': action.get('command') or action.get('path', ''), 'reason': '此操作可能修改工作区'}
    try:
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
