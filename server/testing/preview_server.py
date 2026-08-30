import socket
import subprocess
import sys
from pathlib import Path

_servers = {}


def start(root):
    root_path = Path(root).resolve()
    if not (root_path / 'index.html').is_file():
        return {'result': '未找到 index.html，无法启动网页预览'}
    stop(root)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
        cwd=str(root_path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _servers[str(root_path)] = process
    url = f'http://127.0.0.1:{port}/'
    return {'result': f'预览服务已启动：{url}', 'preview_url': url, 'preview_status': 'running'}


def stop(root):
    process = _servers.pop(str(Path(root).resolve()), None)
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
    return {'result': '预览服务已停止', 'preview_status': 'stopped'}
