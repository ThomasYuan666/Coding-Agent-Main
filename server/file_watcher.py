import asyncio
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .file_ops import build_tree


IGNORED_PARTS = {'.git', '__pycache__', 'node_modules', '.coding-agent', '.venv', 'venv'}


class _ChangeHandler(FileSystemEventHandler):
    def __init__(self, loop, queue):
        self.loop = loop
        self.queue = queue

    def on_any_event(self, event):
        if _is_relevant(event.src_path):
            self.loop.call_soon_threadsafe(self.queue.put_nowait, event.src_path)


def _is_relevant(path):
    return not any(part in IGNORED_PARTS for part in Path(path).parts)


def start(root, loop, queue):
    observer = Observer()
    observer.schedule(_ChangeHandler(loop, queue), str(root), recursive=True)
    observer.start()
    return observer


async def watch_loop(websocket, container, state, queue):
    while True:
        await queue.get()
        await asyncio.sleep(0.15)
        while not queue.empty():
            queue.get_nowait()
        await websocket.send_json({'type': 'container', 'files': build_tree(str(container))})
        if state.get('root'):
            await websocket.send_json({'type': 'files', 'files': build_tree(state['root'])})
