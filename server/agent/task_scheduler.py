"""Run one independent Agent task per workspace."""

import asyncio
import uuid
from pathlib import Path

from .agent_loop import agent_turn, cancel_pending, resolve_approval
from ..context.conversation import ConversationManager
from .task_manager import TaskManager
from ..testing.browser_session import close as close_browser


class WorkspaceSession:
    def __init__(self, root, websocket, client):
        self.root = str(Path(root).resolve())
        self.websocket = websocket
        self.client = client
        self.manager = ConversationManager(self.root)
        self.pending = None
        self.task = None
        self.task_id = None
        self.status = 'idle'
        self._send_lock = asyncio.Lock()

    async def send(self, event):
        payload = dict(event)
        payload.setdefault('workspace', self.root)
        if self.task_id:
            payload.setdefault('task_id', self.task_id)
        async with self._send_lock:
            await self.websocket.send_json(payload)

    async def send_json(self, event):
        """Compatibility adapter for agent_loop's websocket interface."""
        await self.send(event)

    def busy(self):
        return self.task is not None

    async def start(self, data):
        if self.busy():
            return False
        self.task_id = uuid.uuid4().hex
        self.status = 'running'
        await self.send({'type': 'agent_status', 'status': self.status})
        self.task = asyncio.create_task(agent_turn(
            self, self.client, self.manager, self.root, data['turn_id'],
            data['model'], data['reasoning_effort'],
        ))
        self.task.add_done_callback(lambda task: asyncio.create_task(self.finish_task(task)))
        return True

    async def approve(self, approved):
        if not self.pending or self.busy():
            return False
        pending = self.pending
        self.pending = None
        self.status = 'running'
        await self.send({'type': 'agent_status', 'status': self.status})
        self.task = asyncio.create_task(resolve_approval(
            self, self.client, self.manager, self.root, pending, approved,
        ))
        self.task.add_done_callback(lambda task: asyncio.create_task(self.finish_task(task)))
        return True

    async def finish_task(self, task):
        if task.cancelled():
            if self.task is task:
                self.task = None
            return
        try:
            result = await task
        except Exception as exc:
            self.pending = None
            self.task = None
            self.status = 'failed'
            await close_browser(self.root)
            await self.send({'type': 'error', 'content': f'Agent 执行失败：{exc}'})
            await self.send({'type': 'end'})
            await self.send({'type': 'agent_status', 'status': self.status})
            return
        if isinstance(result, dict) and result.get('items'):
            self.pending = result
            self.status = 'waiting_approval'
            await self.send({'type': 'agent_status', 'status': self.status})
        else:
            self.pending = None
            self.status = 'completed'
            await self.send({'type': 'agent_status', 'status': self.status})
        self.task = None

    async def stop(self):
        if not self.task and not self.pending:
            return
        if self.pending:
            cancel_pending(self.manager, self.pending)
            self.pending = None
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None
        await close_browser(self.root)
        self.status = 'idle'
        await self.send({'type': 'stopped'})

    async def resend_pending(self):
        if not self.pending:
            return
        from .agent_loop import _show_pending
        await _show_pending(self, self.root, self.pending['items'][self.pending['index']])


class TaskScheduler:
    def __init__(self, websocket, client):
        self.websocket = websocket
        self.client = client
        self.sessions = {}

    def get(self, root):
        key = str(Path(root).resolve())
        session = self.sessions.get(key)
        if session is None:
            session = WorkspaceSession(key, self.websocket, self.client)
            self.sessions[key] = session
        return session

    def status_list(self):
        return [{'workspace': session.root, 'status': session.status, 'task_id': session.task_id}
                for session in self.sessions.values()]

    def task_list(self, container):
        result = []
        for child in Path(container).iterdir():
            if not child.is_dir() or child.name.startswith('.'):
                continue
            for task in TaskManager(child).load():
                task['workspace'] = str(child.resolve())
                result.append(task)
        return result

    async def close(self):
        for session in self.sessions.values():
            try:
                await session.stop()
            except Exception:
                pass
