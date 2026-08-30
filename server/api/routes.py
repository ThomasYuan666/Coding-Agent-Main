from pathlib import Path

from fastapi import Body, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..workspace.path_utils import resolve_root, safe_path
from .websocket import websocket_endpoint

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'web'

app = FastAPI()
app.mount('/static', StaticFiles(directory=WEB), name='static')
app.websocket('/ws')(websocket_endpoint)


@app.get('/')
async def index():
    return FileResponse(WEB / 'index.html')


@app.put('/api/file')
async def save_file(data: dict = Body(...)):
    root = resolve_root(data['root'])
    target = Path(safe_path(root, data['path']))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data['content'], encoding='utf-8')
    return {'ok': True}
