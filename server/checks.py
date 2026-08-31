import ast
import json
import shutil
import subprocess
from pathlib import Path


def run_checks(root):
    base = Path(root)
    results = []
    js_files = list(base.rglob('*.js'))
    py_files = list(base.rglob('*.py'))
    html_files = list(base.rglob('*.html'))
    for path in js_files:
        if not shutil.which('node'):
            results.append(_item('javascript_syntax', 'skipped', path.name, '未找到 node'))
            break
        result = subprocess.run(['node', '--check', str(path)], cwd=base, capture_output=True, text=True)
        results.append(_item('javascript_syntax', 'passed' if result.returncode == 0 else 'failed', str(path.relative_to(base)), result.stderr or result.stdout))
    for path in py_files:
        try:
            ast.parse(path.read_text(encoding='utf-8'))
            results.append(_item('python_syntax', 'passed', str(path.relative_to(base)), ''))
        except (SyntaxError, UnicodeDecodeError) as exc:
            results.append(_item('python_syntax', 'failed', str(path.relative_to(base)), str(exc)))
    for path in html_files:
        results.append(_item('html_files', 'passed', str(path.relative_to(base)), '文件存在'))
    package = base / 'package.json'
    if package.is_file():
        try:
            scripts = json.loads(package.read_text(encoding='utf-8')).get('scripts', {})
        except (OSError, json.JSONDecodeError) as exc:
            results.append(_item('package_json', 'failed', 'package.json', str(exc)))
        else:
            for script in ('test', 'build'):
                if script not in scripts:
                    continue
                if not (base / 'node_modules').is_dir():
                    results.append(_item(f'npm_{script}', 'skipped', script, '未安装 node_modules'))
                    continue
                command = ['npm', 'test'] if script == 'test' else ['npm', 'run', 'build']
                result = subprocess.run(command, cwd=base, capture_output=True, text=True, timeout=120)
                results.append(_item(f'npm_{script}', 'passed' if result.returncode == 0 else 'failed', script, (result.stdout + result.stderr)[-4000:]))
    if any(path.name.startswith('test_') or path.name.endswith('_test.py') for path in py_files):
        if shutil.which('pytest'):
            result = subprocess.run(['pytest', '-q'], cwd=base, capture_output=True, text=True, timeout=120)
            results.append(_item('pytest', 'passed' if result.returncode == 0 else 'failed', '', (result.stdout + result.stderr)[-4000:]))
        else:
            results.append(_item('pytest', 'skipped', '', '未安装 pytest'))
    status = 'failed' if any(item['status'] == 'failed' for item in results) else 'passed'
    return {'result': json.dumps({'status': status, 'checks': results}, ensure_ascii=False)}


def _item(name, status, target, output):
    return {'name': name, 'status': status, 'target': target, 'output': output}
