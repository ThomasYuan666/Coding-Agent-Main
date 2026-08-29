import asyncio
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from .agent_loop import agent_turn, cancel_pending, resolve_approval
from .conversation import ConversationManager
from .file_ops import build_tree
from .file_watcher import start as start_watcher, watch_loop
from .llm import LLMClient
from .path_utils import CONTAINER, resolve_root, safe_path
from .rollback import RollbackManager
from config.settings import AVAILABLE_MODELS, DEFAULT_MODEL, MODEL_VISION, get_api_key


def contains_image(messages):
    return any(
        isinstance(message.get('content'), list)
        and any(part.get('type') == 'image_url' for part in message['content'])
        for message in messages
    )


async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    root = None
    manager = None
    pending = None
    agent_task = None
    client = LLMClient(get_api_key())
    state = {'root': None}
    queue = asyncio.Queue()
    observer = start_watcher(CONTAINER, asyncio.get_running_loop(), queue)
    watch_task = asyncio.create_task(watch_loop(websocket, CONTAINER, state, queue))
    try:
        while True:
            data = await websocket.receive_json()
            if agent_task and agent_task.done():
                pending = agent_task.result()
                agent_task = None
            action = data.get('action')
            if action == 'set_container':
                await websocket.send_json({'type': 'container', 'files': build_tree(str(CONTAINER))})
            elif action == 'set_root':
                candidate = resolve_root(data['root'])
                if candidate.is_dir() and CONTAINER.resolve() in candidate.parents:
                    root, manager = str(candidate), ConversationManager(candidate)
                    state['root'] = root
                    await websocket.send_json({'type': 'root_set', 'root': root})
                    await _send_history(websocket, root, manager)
            elif action == 'files' and root:
                await websocket.send_json({'type': 'files', 'files': build_tree(root)})
            elif action == 'read' and root:
                await _read_file(websocket, root, data['path'])
            elif action == 'rollback' and root and manager:
                await _rollback(websocket, root, manager, data.get('turn_id'))
            elif action == 'message' and root and manager and not agent_task:
                if await _start_turn(websocket, manager, root, data):
                    agent_task = asyncio.create_task(
                        agent_turn(
                            websocket,
                            client,
                            manager,
                            root,
                            data['turn_id'],
                            data.get('model', DEFAULT_MODEL),
                        )
                    )
            elif action in {'approve', 'reject'} and pending and root and manager and not agent_task:
                agent_task = asyncio.create_task(
                    resolve_approval(
                        websocket,
                        client,
                        manager,
                        root,
                        pending,
                        action == 'approve',
                    )
                )
            elif action == 'stop':
                await _stop_turn(websocket, manager, pending, agent_task)
                pending, agent_task = None, None
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
        if agent_task and not agent_task.done():
            agent_task.cancel()


async def _start_turn(websocket, manager, root, data):
    model = data.get('model', DEFAULT_MODEL)
    if model not in AVAILABLE_MODELS:
        await websocket.send_json({'type': 'error', 'content': '不支持的模型'})
        await websocket.send_json({'type': 'end'})
        return False
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
        await websocket.send_json({'type': 'file_content', 'path': path, 'content': content})
    except Exception as exc:
        await websocket.send_json({'type': 'error', 'content': str(exc)})


async def _rollback(websocket, root, manager, turn_id):
    length = RollbackManager(root).restore(turn_id)
    if length is None:
        return
    manager.save(manager.load()[:length])
    await _send_history(websocket, root, manager)
    await websocket.send_json({'type': 'files', 'files': build_tree(root)})
    await websocket.send_json({'type': 'rollback_done', 'turn_id': turn_id})


def _rollback_turn_ids(root):
    return [record['turn_id'] for record in RollbackManager(root).load()]


async def _send_history(websocket, root, manager):
    await websocket.send_json({
        'type': 'history',
        'messages': manager.load(),
        'rollback_turn_ids': _rollback_turn_ids(root),
    })


async def _stop_turn(websocket, manager, pending, task):
    if pending and manager:
        cancel_pending(manager, pending)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await websocket.send_json({'type': 'stopped'})
