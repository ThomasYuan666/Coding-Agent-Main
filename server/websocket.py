import uuid

from fastapi import WebSocket, WebSocketDisconnect

from .agent_loop import agent_turn, resolve_approval
from .conversation import ConversationManager
from .file_ops import build_tree
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
    client = LLMClient(get_api_key())
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get('action')
            if action == 'set_container':
                await websocket.send_json({'type': 'container', 'files': build_tree(str(CONTAINER))})
            elif action == 'set_root':
                candidate = resolve_root(data['root'])
                if candidate.is_dir() and CONTAINER.resolve() in candidate.parents:
                    root, manager = str(candidate), ConversationManager(candidate)
                    await websocket.send_json({'type': 'root_set', 'root': root})
                    await websocket.send_json({'type': 'history', 'messages': manager.load()})
            elif action == 'files' and root:
                await websocket.send_json({'type': 'files', 'files': build_tree(root)})
            elif action == 'read' and root:
                await _read_file(websocket, root, data['path'])
            elif action == 'rollback' and root and manager:
                await _rollback(websocket, root, manager, data.get('turn_id'))
            elif action == 'message' and root and manager:
                if await _start_turn(websocket, manager, root, data):
                    pending = await agent_turn(
                        websocket,
                        client,
                        manager,
                        root,
                        data['turn_id'],
                        data.get('model', DEFAULT_MODEL),
                    )
            elif action in {'approve', 'reject'} and pending and root and manager:
                pending = await resolve_approval(
                    websocket,
                    client,
                    manager,
                    root,
                    pending,
                    action == 'approve',
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        print(f'[websocket] error: {type(exc).__name__}: {exc}')


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
    await websocket.send_json({'type': 'history', 'messages': manager.load()})
    await websocket.send_json({'type': 'files', 'files': build_tree(root)})
    await websocket.send_json({'type': 'rollback_done', 'turn_id': turn_id})
