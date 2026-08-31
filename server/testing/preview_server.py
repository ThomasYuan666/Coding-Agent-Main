import socket
import subprocess
import sys
from pathlib import Path

_servers = {}


def start(root):
    root_path = Path(root).resolve()
    stop(root)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, '-m', 'http.server', str(port), '--bind', '127.0.0.1'],
        cwd=str(root_path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f'http://127.0.0.1:{port}/'
    _servers[str(root_path)] = {'process': process, 'url': url}
    return {'result': f'预览服务已启动：{url}', 'preview_url': url, 'preview_status': 'running'}


def ensure(root):
    current = _servers.get(str(Path(root).resolve()))
    if current and current['process'].poll() is None:
        return {'result': f'Preview service is running: {current["url"]}', 'preview_url': current['url'], 'preview_status': 'running'}
    return start(root)


def stop(root):
    current = _servers.pop(str(Path(root).resolve()), None)
    process = current['process'] if current else None
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
    return {'result': '预览服务已停止', 'preview_status': 'stopped'}
