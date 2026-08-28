import json
from pathlib import Path
from fastapi import Body, FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from config.settings import get_api_key
from .conversation import ConversationManager
from .file_ops import build_tree
from .llm import LLMClient
from .tools import execute

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
    root = resolve_root(data['root']); target = (root / data['path']).resolve()
    if root not in target.parents: return {'ok': False, 'error': '路径不在当前工作区内'}
    target.parent.mkdir(parents=True, exist_ok=True); target.write_text(data['content'], encoding='utf-8')
    return {'ok': True}

async def agent_turn(ws, client, manager, root):
    print(f'[agent] turn root={root}')
    try:
        response = None
        for event in client.stream_chat(manager.load()):
            if event['type'] == 'reasoning':
                await ws.send_json({'type': 'reasoning', 'content': event['content']})
            elif event['type'] == 'content':
                await ws.send_json({'type': 'chunk', 'content': event['content']})
            elif event['type'] == 'done':
                response = event['result']
    except Exception as exc:
        print(f'[agent] model error: {type(exc).__name__}: {exc}')
        await ws.send_json({'type': 'error', 'content': f'模型调用失败：{exc}'})
        await ws.send_json({'type': 'end'})
        return None
    calls = response.get('tool_calls', [])
    if not calls:
        manager.add({'role': 'assistant', 'content': response.get('content', ''), 'reasoning_content': response.get('reasoning_content', '')}); await ws.send_json({'type': 'end'}); return None
    manager.add({'role': 'assistant', 'content': response.get('content') or None, 'reasoning_content': response.get('reasoning_content', ''), 'tool_calls': calls})
    for call in calls:
        name = call['function']['name']
        print(f'[tool] requested name={name}')
        try: args = json.loads(call['function']['arguments'] or '{}')
        except json.JSONDecodeError as exc:
            print(f'[tool] invalid arguments name={name}: {exc}')
            args = {}
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
    return await agent_turn(ws, client, manager, root)

@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept(); root = None; manager = None; pending = None; client = LLMClient(get_api_key())
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
                    target = (Path(root) / data['path']).resolve()
                    if Path(root) not in target.parents: raise ValueError('路径不在当前工作区内')
                    await ws.send_json({'type': 'file_content', 'path': data['path'], 'content': target.read_text(encoding='utf-8')})
                except Exception as exc: await ws.send_json({'type': 'error', 'content': str(exc)})
            elif action == 'message' and root and manager:
                manager.add({'role': 'user', 'content': data['content']}); await ws.send_json({'type': 'user', 'content': data['content']}); await ws.send_json({'type': 'start'}); pending = await agent_turn(ws, client, manager, root)
            elif action in {'approve', 'reject'} and pending and root and manager:
                call = pending['call']; result = execute(pending['name'], pending['args'], root, approved=action == 'approve')
                if action == 'reject': result = {'result': '用户拒绝了该操作，请尝试其他方案。'}
                manager.add({'role': 'tool', 'tool_call_id': call['id'], 'content': result['result']}); await ws.send_json({'type': 'tool', 'tool': pending['name'], 'result': result['result']})
                if action == 'approve' and pending['name'] in {'write_file', 'delete_file'}:
                    await ws.send_json({'type': 'files', 'files': build_tree(root)})
                pending = await agent_turn(ws, client, manager, root)
    except Exception as exc:
        print(f'WebSocket error: {type(exc).__name__}: {exc}')
