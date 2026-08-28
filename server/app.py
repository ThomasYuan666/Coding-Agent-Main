import json, subprocess, asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, Body
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from agent.model_client import chat
from config.settings import MAX_TURNS
from tools.registry import TOOL_DEFINITIONS

ROOT=Path(__file__).resolve().parents[1]; WEB=ROOT/'web'; app=FastAPI(); app.mount('/static',StaticFiles(directory=WEB),name='static')
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
    return {'path': path, 'name': Path(path).name if path else ''}
@app.get('/api/files')
def files(path:str): return [str(p.relative_to(path)) for p in safe(path).rglob('*') if p.is_file() and '.coding-agent' not in p.parts]
@app.get('/api/file',response_class=PlainTextResponse)
def read(root:str,path:str): return safe(root,path).read_text(encoding='utf-8')
@app.put('/api/file')
def write(d:dict=Body(...)): safe(d['root'],d['path']).write_text(d['content'],encoding='utf-8'); return {'ok':True}
@app.get('/api/history')
def history(root:str): return load(root)
@app.websocket('/ws')
async def socket(ws:WebSocket):
    await ws.accept()
    while True:
        req=await ws.receive_json(); root=req['root']; msgs=load(root)
        if not msgs: msgs=[{'role':'system','content':f'你是 Windows 编程助手，只能通过工具操作工作区 {root}。'}]
        msgs.append({'role':'user','content':req['content']})
        for _ in range(MAX_TURNS):
            loop=asyncio.get_running_loop()
            def emit(k,t): asyncio.run_coroutine_threadsafe(ws.send_json({'type':k,'text':t}),loop)
            resp=await loop.run_in_executor(None,chat,msgs,TOOL_DEFINITIONS,emit); msg=resp['choices'][0]['message']; msgs.append(msg)
            calls=msg.get('tool_calls') or []
            if not calls: save(root,msgs); await ws.send_json({'type':'done'}); break
            for c in calls:
                name=c['function']['name']; args=json.loads(c['function'].get('arguments') or '{}'); ok=True
                if name in {'write_file','delete_file','run_command'}:
                    await ws.send_json({'type':'confirm','tool':name,'args':args}); ok=(await ws.receive_json()).get('approved',False)
                try: result=execute(root,name,args) if ok else '用户拒绝了该操作，请尝试其他方案。'
                except Exception as e: result='工具执行失败：'+str(e)
                msgs.append({'role':'tool','tool_call_id':c['id'],'content':result}); save(root,msgs); await ws.send_json({'type':'tool','tool':name,'result':result})
