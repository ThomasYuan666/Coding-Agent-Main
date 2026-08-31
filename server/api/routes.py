from pathlib import Path

from fastapi import Body, FastAPI, Query
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

@app.get('/api/screenshot')
async def screenshot(root: str = Query(...), path: str = Query('latest.png')):
    workspace = Path(resolve_root(root))
    try:
        workspace.relative_to(Path(resolve_root('.')))
    except ValueError:
        return {'error': 'invalid workspace'}
    base = workspace / '.coding-agent' / 'screenshots'
    target = Path(safe_path(str(base), path))
    if target.suffix.lower() != '.png' or not target.is_file():
        return {'error': 'screenshot not found'}
    return FileResponse(target, media_type='image/png')


@app.put('/api/file')
async def save_file(data: dict = Body(...)):
    root = resolve_root(data['root'])
    target = Path(safe_path(root, data['path']))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(data['content'], encoding='utf-8')
    return {'ok': True}
