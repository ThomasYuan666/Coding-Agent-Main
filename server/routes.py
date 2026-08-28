import json
import os
import subprocess
from pathlib import Path
from fastapi import FastAPI, WebSocket, Body
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
async def index(): return FileResponse(WEB / 'index.html')

@app.put('/api/file')
async def save_file(data: dict = Body(...)):
    root = resolve_root(data['root'])
    target = (root / data['path']).resolve()
    if root not in target.parents:
        return {'ok': False, 'error': '路径不在当前工作区内'}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data['content'], encoding='utf-8')
    return {'ok': True}

@app.websocket('/ws')
async def websocket_endpoint(ws: WebSocket):
    await ws.accept(); root = None; manager = None; pending = None
    try:
        client = LLMClient(get_api_key())
        while True:
            data = await ws.receive_json(); action = data.get('action')
            if action == 'set_container':
                await ws.send_json({'type': 'container', 'files': build_tree(str(CONTAINER))})
                continue
            if action == 'set_root':
                requested = Path(data['root'])
                candidate = (CONTAINER / requested.name if not requested.is_absolute() else requested).resolve()
                if not candidate.is_dir() or CONTAINER.resolve() not in candidate.parents: continue
                root = str(candidate); manager = ConversationManager(root)
                await ws.send_json({'type':'root_set','root':root})
                await ws.send_json({'type':'history','messages':manager.load()})
            elif action == 'files' and root: await ws.send_json({'type':'files','files':build_tree(root)})
            elif action == 'read' and root:
                try: await ws.send_json({'type':'file_content','path':data['path'],'content':(Path(root) / data['path']).resolve().read_text(encoding='utf-8')})
                except Exception as e: await ws.send_json({'type':'error','content':str(e)})
            elif action == 'message' and root and manager:
                manager.add_message('user',data['content']); await ws.send_json({'type':'user','content':data['content']}); await ws.send_json({'type':'start'})
                full=''
                for chunk in client.chat(manager.load()): full += chunk; await ws.send_json({'type':'chunk','content':chunk})
                manager.add_message('assistant',full); await ws.send_json({'type':'end'})
                for line in full.splitlines():
                    if not line.strip().startswith('{'): continue
                    try: call=json.loads(line); result=execute(call,root)
                    except Exception: continue
                    if result.get('needs_approval'):
                        pending=call; await ws.send_json({'type':'approval','command':result['command'],'reason':result['reason']})
                    else: await ws.send_json({'type':'tool','tool':call.get('tool',''),'result':result.get('result','')})
            elif action in {'approve','reject'} and pending and root:
                if action == 'approve': result=execute(pending,root,approved=True)
                else: result={'result':'用户拒绝了该操作，请尝试其他方案。'}
                await ws.send_json({'type':'tool','tool':pending.get('tool',''),'result':result.get('result','')}); pending=None
    except Exception as exc: print('WebSocket error:', exc)
