import json, subprocess, asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, Body
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from agent.model_client import chat
from config.settings import MAX_TURNS
from tools.registry import TOOL_DEFINITIONS

ROOT=Path(__file__).resolve().parents[1]; WEB=ROOT/'web'; app=FastAPI(); app.mount('/static',StaticFiles(directory=WEB),name='static')
RECENT_FILE = ROOT / '.coding-agent' / 'recent_workspaces.json'
def recent_load():
    try: return json.loads(RECENT_FILE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError): return []
def recent_save(items):
    RECENT_FILE.parent.mkdir(exist_ok=True); RECENT_FILE.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
def remember(path):
    path=str(Path(path).resolve()); items=[x for x in recent_load() if x.get('path') != path]
    items.insert(0, {'path':path,'name':Path(path).name}); recent_save(items[:8]); return items[:8]
def safe(root, rel=''):
    base=Path(root).resolve(); target=(base/rel).resolve()
    if not base.is_dir() or (target!=base and base not in target.parents): raise ValueError('路径不在工作区内')
    return target
def hist(root): return safe(root)/'.coding-agent'/'conversation.json'
def load(root):
    try: return json.loads(hist(root).read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError): return []
def save(root,msgs):
    p=hist(root); p.parent.mkdir(exist_ok=True); p.write_text(json.dumps(msgs,ensure_ascii=False,indent=2),encoding='utf-8')
def execute(root,name,a):
    if name=='list_files': return '\n'.join(str(p.relative_to(root)) for p in safe(root).rglob('*') if p.is_file() and '.coding-agent' not in p.parts) or '(目录为空)'
    if name=='read_file': return safe(root,a['path']).read_text(encoding='utf-8')
    if name=='write_file':
        p=safe(root,a['path']); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(a['content'],encoding='utf-8'); return '已写入 '+a['path']
    if name=='delete_file': safe(root,a['path']).unlink(); return '已删除 '+a['path']
    if name=='run_command':
        r=subprocess.run(a['command'],cwd=safe(root),shell=True,capture_output=True,text=True,timeout=120); return f'退出码：{r.returncode}\n{r.stdout}{r.stderr}'.strip()
    raise ValueError('未知工具：'+name)
@app.get('/')
def index(): return FileResponse(WEB/'index.html')
@app.get('/api/workspace')
def choose():
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$d=New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$d.Description='选择已有工作区'; "
        "if($d.ShowDialog() -eq 'OK'){Write-Output $d.SelectedPath}"
    )
    result = subprocess.run(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
        capture_output=True, text=True, timeout=300,
    )
    path = result.stdout.strip()
    return {'path': path, 'name': Path(path).name if path else '', 'recent': remember(path) if path else recent_load()}
@app.get('/api/recent')
def recent(): return [x for x in recent_load() if Path(x.get('path','')).is_dir()]
@app.delete('/api/recent')
def remove_recent(path: str):
    items=[x for x in recent_load() if x.get('path') != path]; recent_save(items); return items
@app.get('/api/files')
def files(path:str): return [str(p.relative_to(path)) for p in safe(path).rglob('*') if p.is_file() and '.coding-agent' not in p.parts]
@app.get('/api/file',response_class=PlainTextResponse)
def read(root:str,path:str): return safe(root,path).read_text(encoding='utf-8')
@app.put('/api/file')
def write(d:dict=Body(...)): safe(d['root'],d['path']).write_text(d['content'],encoding='utf-8'); return {'ok':True}
@app.get('/api/history')
def history(root:str): return load(root)
stop_flags={}
@app.websocket('/ws')
async def socket(ws:WebSocket):
    await ws.accept(); session_id=str(id(ws)); stop_flags[session_id]=False
    try:
        while True:
            req=await ws.receive_json()
            if req.get('action')=='stop': stop_flags[session_id]=True; await ws.send_json({'type':'stopped'}); continue
            if req.get('action')=='revert':
                root=req['root']; msgs=load(root)
                if len(msgs)>1: msgs=msgs[:-2]; save(root,msgs)
                await ws.send_json({'type':'reverted'}); continue
            root=req['root']; msgs=load(root); stop_flags[session_id]=False
            if not msgs: msgs=[{'role':'system','content':f'你是 Windows 编程助手，只能通过工具操作工作区 {root}。'}]
            msgs.append({'role':'user','content':req['content']})
            for _ in range(MAX_TURNS):
                if stop_flags[session_id]: await ws.send_json({'type':'stopped'}); break
                loop=asyncio.get_running_loop()
                def emit(k,t): asyncio.run_coroutine_threadsafe(ws.send_json({'type':k,'text':t}),loop)
                resp=await loop.run_in_executor(None,chat,msgs,TOOL_DEFINITIONS,emit); msg=resp['choices'][0]['message']; msgs.append(msg)
                calls=msg.get('tool_calls') or []
                if not calls: save(root,msgs); await ws.send_json({'type':'done'}); break
                for c in calls:
                    if stop_flags[session_id]: break
                    name=c['function']['name']; args=json.loads(c['function'].get('arguments') or '{}'); ok=True
                    if name in {'write_file','delete_file','run_command'}:
                        await ws.send_json({'type':'confirm','tool':name,'args':args}); ok=(await ws.receive_json()).get('approved',False)
                    try: result=execute(root,name,args) if ok else '用户拒绝了该操作，请尝试其他方案。'
                    except Exception as e: result='工具执行失败：'+str(e)
                    msgs.append({'role':'tool','tool_call_id':c['id'],'content':result}); save(root,msgs); await ws.send_json({'type':'tool','tool':name,'result':result})
    finally: stop_flags.pop(session_id,None)
