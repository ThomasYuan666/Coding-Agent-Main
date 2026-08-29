import json
import uuid
from pathlib import Path
from fastapi import Body, FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from config.settings import get_api_key
from .conversation import ConversationManager
from .file_ops import build_tree
from .llm import LLMClient
from .tools import apply_write, execute, prepare_write
from .path_utils import safe_path
from .rollback import RollbackManager

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
CONTAINER = ROOT.parent / 'workspace'
app = FastAPI()
app.mount('/static', StaticFiles(directory=WEB), name='static')

def resolve_root(value):
    path = Path(value)
    return (CONTAINER / path.name if not path.is_absolute() else path).resolve()

@app.get('/')
async def index():
    return FileResponse(WEB / 'index.html')

@app.put('/api/file')
async def save_file(data: dict = Body(...)):
    root = resolve_root(data['root'])
    target = Path(safe_path(root, data['path']))
    if root not in target.parents: return {'ok': False, 'error': '路径不在当前工作区内'}
    target.parent.mkdir(parents=True, exist_ok=True); target.write_text(data['content'], encoding='utf-8')
    return {'ok': True}

async def agent_turn(ws, client, manager, root, turn_id):
    print(f'[agent] turn root={root}')
    try:
        response = None
        async for event in client.stream_chat(manager.load()):
            if event['type'] == 'reasoning':
                await ws.send_json({'type': 'reasoning', 'content': event['content']})
            elif event['type'] == 'content':
                await ws.send_json({'type': 'chunk', 'content': event['content']})
            elif event['type'] == 'done':
                response = event['result']
    except Exception as exc:
        print(f'[agent] model error: {type(exc).__name__}: {exc!r}')
        await ws.send_json({'type': 'error', 'content': f'模型调用失败：{exc}'})
        await ws.send_json({'type': 'end'})
        return None
    calls = response.get('tool_calls', [])
    if not calls:
        manager.add({'role': 'assistant', 'content': response.get('content', ''), 'reasoning_content': response.get('reasoning_content', ''), 'turn_id': turn_id}); await ws.send_json({'type': 'end'}); return None
    manager.add({'role': 'assistant', 'content': response.get('content') or None, 'reasoning_content': response.get('reasoning_content', ''), 'tool_calls': calls, 'turn_id': turn_id})
    parsed_calls = []
    for call in calls:
        name = call['function']['name']
        print(f'[tool] requested name={name}')
        try: args = json.loads(call['function']['arguments'] or '{}')
        except json.JSONDecodeError as exc:
            print(f'[tool] invalid arguments name={name}: {exc}')
            args = {}
        parsed_calls.append((call, name, args))
    write_calls = [(call, name, args) for call, name, args in parsed_calls if name == 'write_file']
    other_calls = [(call, name, args) for call, name, args in parsed_calls if name != 'write_file']
    pending_items = []
    if write_calls:
        changes = [prepare_write(root, args['path'], args['content']) for _, _, args in write_calls]
        for call, name, args in write_calls:
            await ws.send_json({
                'type': 'tool_call',
                'tool': name,
                'arguments': json.dumps(args, ensure_ascii=False),
            })
        pending_items.append({'kind': 'diff', 'calls': write_calls, 'changes': changes})
    for call, name, args in other_calls:
        if name == 'read_file':
            result = execute(name, args, root)
            manager.add({'role': 'tool', 'tool_call_id': call['id'], 'content': result['result']})
            await ws.send_json({'type': 'tool', 'tool': name, 'result': result['result']})
        else:
            pending_items.append({'kind': 'command', 'call': call, 'name': name, 'args': args})
    if pending_items:
        pending = pending_items[0]
        if pending['kind'] == 'diff':
            await ws.send_json({'type': 'diff', 'files': pending['changes']})
        else:
            result = execute(pending['name'], pending['args'], root)
            await ws.send_json({'type': 'approval', 'tool': pending['name'], 'command': result['command'], 'reason': result['reason']})
        pending['items'] = pending_items
        pending['index'] = 0
        pending['turn_id'] = turn_id
        return pending
    for call, name, args in parsed_calls:
        result = execute(name, args, root)
        if result.get('needs_approval'):
            print(f'[tool] approval required name={name}')
            await ws.send_json({'type': 'approval', 'tool': name, 'command': result['command'], 'reason': result['reason']})
            return {'call': call, 'name': name, 'args': args}
        manager.add({'role': 'tool', 'tool_call_id': call['id'], 'content': result['result']})
        print(f'[tool] completed name={name}')
        await ws.send_json({'type': 'tool', 'tool': name, 'result': result['result']})
        if name in {'write_file', 'delete_file'}:
            await ws.send_json({'type': 'files', 'files': build_tree(root)})
    return await agent_turn(ws, client, manager, root, turn_id)

@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept(); root = None; manager = None; pending = None; turn_id = None; client = LLMClient(get_api_key())
    try:
        while True:
            data = await ws.receive_json(); action = data.get('action')
            if action == 'set_container': await ws.send_json({'type': 'container', 'files': build_tree(str(CONTAINER))})
            elif action == 'set_root':
                candidate = resolve_root(data['root'])
                if candidate.is_dir() and CONTAINER.resolve() in candidate.parents:
                    root, manager = str(candidate), ConversationManager(candidate)
                    await ws.send_json({'type': 'root_set', 'root': root}); await ws.send_json({'type': 'history', 'messages': manager.load()})
            elif action == 'files' and root: await ws.send_json({'type': 'files', 'files': build_tree(root)})
            elif action == 'read' and root:
                try:
                    target = Path(safe_path(root, data['path']))
                    if Path(root) not in target.parents: raise ValueError('路径不在当前工作区内')
                    await ws.send_json({'type': 'file_content', 'path': data['path'], 'content': target.read_text(encoding='utf-8')})
                except Exception as exc: await ws.send_json({'type': 'error', 'content': str(exc)})
            elif action == 'rollback' and root and manager:
                target_id = data.get('turn_id')
                length = RollbackManager(root).restore(target_id)
                if length is not None:
                    manager.save(manager.load()[:length])
                    await ws.send_json({'type': 'history', 'messages': manager.load()})
                    await ws.send_json({'type': 'files', 'files': build_tree(root)})
                    await ws.send_json({'type': 'rollback_done', 'turn_id': target_id})
            elif action == 'message' and root and manager:
                turn_id = uuid.uuid4().hex
                manager.add({'role': 'user', 'content': data['content'], 'turn_id': turn_id})
                RollbackManager(root).begin(turn_id, len(manager.load()) - 1)
                await ws.send_json({'type': 'user', 'content': data['content'], 'turn_id': turn_id}); await ws.send_json({'type': 'start'}); pending = await agent_turn(ws, client, manager, root, turn_id)
            elif action in {'approve', 'reject'} and pending and root and manager:
                if pending.get('items'):
                    item = pending['items'][pending['index']]
                    if item['kind'] == 'diff':
                        if action == 'approve':
                            for change in item['changes']:
                                RollbackManager(root).record(pending['turn_id'], change)
                                apply_write(root, change)
                        status = 'Files accepted and written.' if action == 'approve' else 'User rejected the file changes; try another approach.'
                        for call, _, _ in item['calls']:
                            manager.add({'role': 'tool', 'tool_call_id': call['id'], 'content': status})
                        await ws.send_json({'type': 'diff_status', 'status': 'accepted' if action == 'approve' else 'rejected'})
                        await ws.send_json({'type': 'tool', 'tool': 'write_file', 'result': status})
                        if action == 'approve': await ws.send_json({'type': 'files', 'files': build_tree(root)})
                    else:
                        call = item['call']
                        result = execute(item['name'], item['args'], root, approved=action == 'approve')
                        if action == 'reject': result = {'result': 'User rejected this command; try another approach.'}
                        manager.add({'role': 'tool', 'tool_call_id': call['id'], 'content': result['result']})
                        await ws.send_json({'type': 'tool', 'tool': item['name'], 'result': result['result']})
                    pending['index'] += 1
                    if pending['index'] < len(pending['items']):
                        next_item = pending['items'][pending['index']]
                        if next_item['kind'] == 'diff':
                            await ws.send_json({'type': 'diff', 'files': next_item['changes']})
                        else:
                            result = execute(next_item['name'], next_item['args'], root)
                            await ws.send_json({'type': 'approval', 'tool': next_item['name'], 'command': result['command'], 'reason': result['reason']})
                    else:
                        pending = await agent_turn(ws, client, manager, root, turn_id)
                    continue
                if pending.get('kind') == 'diff':
                    if action == 'approve':
                        for change in pending['changes']:
                            apply_write(root, change)
                    status = '已接受并写入文件。' if action == 'approve' else '用户拒绝了文件修改，请尝试其他方案。'
                    for call, _, _ in pending['calls']:
                        manager.add({'role': 'tool', 'tool_call_id': call['id'], 'content': status})
                    await ws.send_json({'type': 'diff_status', 'status': 'accepted' if action == 'approve' else 'rejected'})
                    await ws.send_json({'type': 'tool', 'tool': 'write_file', 'result': status})
                    if action == 'approve': await ws.send_json({'type': 'files', 'files': build_tree(root)})
                    pending = await agent_turn(ws, client, manager, root, turn_id)
                    continue
                call = pending['call']; result = execute(pending['name'], pending['args'], root, approved=action == 'approve')
                if action == 'reject': result = {'result': '用户拒绝了该操作，请尝试其他方案。'}
                manager.add({'role': 'tool', 'tool_call_id': call['id'], 'content': result['result']}); await ws.send_json({'type': 'tool', 'tool': pending['name'], 'result': result['result']})
                if action == 'approve' and pending['name'] in {'write_file', 'delete_file'}:
                    await ws.send_json({'type': 'files', 'files': build_tree(root)})
                pending = await agent_turn(ws, client, manager, root, turn_id)
    except Exception as exc:
        print(f'WebSocket error: {type(exc).__name__}: {exc}')
