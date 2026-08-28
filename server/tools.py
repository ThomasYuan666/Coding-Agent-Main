"""工具执行模块 - 负责执行各种工具操作"""
import os
import subprocess
import difflib


def generate_diff(old: str, new: str, path: str) -> str:
    """生成文件修改的 unified diff 格式"""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f'a/{path}',
        tofile=f'b/{path}',
        lineterm=''
    )
    return ''.join(diff)


def execute(action: dict, root: str) -> dict:
    """
    执行工具操作

    Args:
        action: 包含 tool 和参数的字典
        root: 工作区根目录

    Returns:
        执行结果，可能包含 result、diff、needs_approval 等字段
    """
    tool = action.get('tool')

    if tool == 'read_file':
        path = os.path.join(root, action['path'])
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {'result': content}
        except Exception as e:
            return {'result': f'错误: {str(e)}'}

    elif tool == 'write_file':
        path = os.path.join(root, action['path'])
        old_content = ''

        # 获取旧内容用于生成 diff
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
            except:
                old_content = ''

        # 写入新内容
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(action['content'])

            # 生成 diff
            diff_text = generate_diff(old_content, action['content'], action['path'])

            return {
                'result': f"已写入 {action['path']}",
                'diff': diff_text
            }
        except Exception as e:
            return {'result': f'错误: {str(e)}'}

    elif tool == 'execute_bash':
        cmd = action['command']

        # 危险命令需要用户确认
        dangerous = ['rm', 'del', 'format', 'mkfs', 'dd', '>']
        if any(d in cmd for d in dangerous):
            return {
                'needs_approval': True,
                'command': cmd,
                'reason': '此命令可能删除或覆盖文件'
            }

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout + result.stderr
            return {'result': output or '命令执行完成'}
        except subprocess.TimeoutExpired:
            return {'result': '错误: 命令执行超时'}
        except Exception as e:
            return {'result': f'错误: {str(e)}'}

    else:
        return {'result': f'未知工具: {tool}'}
