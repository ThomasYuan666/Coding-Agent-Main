import asyncio
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from .file_ops import build_tree
from .file_watcher import start as start_watcher, watch_loop
from .llm import LLMClient
from .path_utils import CONTAINER, resolve_root, safe_path
from .rollback import RollbackManager
from .context_manager import ContextManager
from .task_manager import TaskManager
from .task_scheduler import TaskScheduler
from config.settings import AVAILABLE_MODELS, CONTEXT_LIMIT, DEFAULT_MODEL, DEFAULT_REASONING, MODEL_VISION, REASONING_LEVELS, get_api_key


def contains_image(messages):
    return any(
        isinstance(message.get('content'), list)
        and any(part.get('type') == 'image_url' for part in message['content'])
        for message in messages
    )


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client = LLMClient(get_api_key())
    scheduler = TaskScheduler(websocket, client)
    root = None
    state = {'root': None}
    queue = asyncio.Queue()
    observer = start_watcher(CONTAINER, asyncio.get_running_loop(), queue)
    watch_task = asyncio.create_task(watch_loop(websocket, CONTAINER, state, queue))
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get('action')
            if action == 'set_container':
                await websocket.send_json({'type': 'container', 'files': build_tree(str(CONTAINER))})
                await websocket.send_json({'type': 'workspace_statuses', 'items': scheduler.status_list()})
                await websocket.send_json({'type': 'tasks', 'tasks': scheduler.task_list(CONTAINER)})
            elif action == 'set_root':
                candidate = resolve_root(data['root'])
                if candidate.is_dir() and CONTAINER.resolve() in candidate.parents:
                    root = str(candidate)
                    session = scheduler.get(root)
                    state['root'] = root
                    await websocket.send_json({'type': 'root_set', 'root': root})
                    await _send_history(websocket, session)
            elif action == 'files' and root:
                await websocket.send_json({'type': 'files', 'workspace': root, 'files': build_tree(root)})
            elif action == 'read' and root:
                await _read_file(websocket, root, data['path'])
            elif action == 'rollback' and root:
                session = scheduler.get(root)
                if not session.busy() and not session.pending:
                    await _rollback(websocket, session, data.get('turn_id'), client)
            elif action == 'compact' and root:
                session = scheduler.get(root)
                if not session.busy() and not session.pending:
                    await _compact(websocket, session, client)
            elif action == 'message' and root:
                session = scheduler.get(root)
                if not session.busy() and await _start_turn(session, data):
                    await session.start(data)
            elif action in {'approve', 'reject'}:
                target = _target_session(scheduler, data.get('workspace') or root)
                if target and (not data.get('task_id') or data.get('task_id') == target.task_id):
                    await target.approve(action == 'approve')
            elif action == 'stop':
                target = _target_session(scheduler, data.get('workspace') or root)
                if target and (not data.get('task_id') or data.get('task_id') == target.task_id):
                    await target.stop()
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        print(f'[websocket] error: {type(exc).__name__}: {exc}')
    finally:
        watch_task.cancel()
        try:
            await watch_task
        except asyncio.CancelledError:
            pass
        observer.stop()
        observer.join(timeout=2)
    await scheduler.close()


def _target_session(scheduler, value):
    if not value:
        return None
    candidate = resolve_root(value)
    return scheduler.get(candidate)


async def _start_turn(session, data):
    websocket = session
    manager, root = session.manager, session.root
    model = data.get('model', DEFAULT_MODEL)
    reasoning_effort = data.get('reasoning_effort', DEFAULT_REASONING)
    if model not in AVAILABLE_MODELS:
        await websocket.send_json({'type': 'error', 'content': '不支持的模型'})
        await websocket.send_json({'type': 'end'})
        return False
    if reasoning_effort not in REASONING_LEVELS:
        await websocket.send_json({'type': 'error', 'content': '不支持的推理深度'})
        await websocket.send_json({'type': 'end'})
        return False
    data['model'] = model
    data['reasoning_effort'] = reasoning_effort
    messages = manager.load()
    content = data['content']
    has_image = _content_contains_image(content)
    if (has_image or contains_image(messages)) and model != MODEL_VISION:
        await websocket.send_json({'type': 'error', 'content': '包含图片的对话只能使用 Vision 模型'})
        await websocket.send_json({'type': 'end'})
        return False
    turn_id = uuid.uuid4().hex
    data['turn_id'] = turn_id
    manager.add({'role': 'user', 'content': content, 'turn_id': turn_id})
    RollbackManager(root).begin(turn_id, len(manager.load()) - 1)
    await websocket.send_json({'type': 'user', 'content': content, 'turn_id': turn_id})
    await websocket.send_json({'type': 'rollback_state', 'turn_ids': _rollback_turn_ids(root)})
    await websocket.send_json({'type': 'start'})
    return True


def _content_contains_image(content):
    return isinstance(content, list) and any(
        isinstance(part, dict) and part.get('type') == 'image_url'
        for part in content
    )


async def _read_file(websocket, root, path):
    try:
        target = safe_path(root, path)
        with open(target, encoding='utf-8') as file:
            content = file.read()
        await websocket.send_json({'type': 'file_content', 'workspace': root, 'path': path, 'content': content})
    except Exception as exc:
        await websocket.send_json({'type': 'error', 'content': str(exc)})


async def _rollback(websocket, session, turn_id, client):
    root, manager = session.root, session.manager
    length = RollbackManager(root).restore(turn_id)
    if length is None:
        return
    manager.save(manager.load()[:length])
    context = ContextManager(root)
    context.invalidate()
    if context.needs_initial_summary(manager.load()):
        await websocket.send_json({'type': 'context_status', 'status': 'compacting'})
        await context.compact(manager.load(), client)
        await websocket.send_json({'type': 'context_status', 'status': 'ready'})
    await _send_history(websocket, session)
    await websocket.send_json({'type': 'files', 'workspace': root, 'files': build_tree(root)})
    await websocket.send_json({'type': 'rollback_done', 'turn_id': turn_id})


async def _compact(websocket, session, client):
    root, manager = session.root, session.manager
    context = ContextManager(root)
    await websocket.send_json({'type': 'context_status', 'status': 'compacting'})
    if not await context.compact(manager.load(), client):
        await websocket.send_json({'type': 'context_status', 'status': 'ready'})
        return
    await websocket.send_json({'type': 'context_status', 'status': 'ready'})


def _rollback_turn_ids(root):
    return [record['turn_id'] for record in RollbackManager(root).load()]


async def _send_history(websocket, session):
    root, manager = session.root, session.manager
    await websocket.send_json({
        'type': 'history',
        'workspace': root,
        'messages': manager.load(),
        'rollback_turn_ids': _rollback_turn_ids(root),
    })
    usage = ContextManager(root).last_usage()
    await websocket.send_json({'type': 'tasks', 'workspace': root, 'tasks': TaskManager(root).load()})
    await session.send({'type': 'agent_status', 'status': session.status})
    await session.resend_pending()
    if usage:
        await websocket.send_json({
            'type': 'context_usage',
            'usage': {'prompt_tokens': usage},
            'limit': CONTEXT_LIMIT,
        })
