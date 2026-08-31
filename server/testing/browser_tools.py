import json

from .browser_session import get, close
from .browser_observer import observe


async def execute(name, args, root):
    if name == 'browser_close':
        await close(root)
        return {'result': '浏览器测试会话已关闭。'}
    session = await get(root)
    page = session.page
    if name == 'browser_open':
        value = args.get('url')
        if not value or value.startswith('file://'):
            return {'result': '请先读取工作区文件，并提供要打开的 HTML 相对路径，例如 /index.html。'}
        url = value if value.startswith(('http://', 'https://')) else session.preview_base_url.rstrip('/') + '/' + value.lstrip('/')
        await page.goto(url, wait_until='domcontentloaded')
    elif name == 'browser_click':
        await page.locator(args['selector']).click()
    elif name == 'browser_press':
        await page.keyboard.press(args['key'])
    elif name == 'browser_type':
        await page.locator(args['selector']).fill(args.get('text', ''))
    elif name == 'browser_wait':
        await page.wait_for_timeout(min(int(args.get('ms', 500)), 10000))
    elif name == 'browser_observe':
        pass
    else:
        return {'result': f'未知浏览器工具：{name}'}
    return {'result': await _result(page, args.get('expression'))}


async def _result(page, expression=None):
    return json.dumps(await observe(page, expression), ensure_ascii=False)
