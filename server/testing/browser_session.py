from pathlib import Path

from .preview_server import ensure, stop


class BrowserSession:
    def __init__(self, root):
        self.root = str(Path(root).resolve())
        self.playwright = None
        self.browser = None
        self.page = None

    async def start(self):
        if self.page and not self.page.is_closed():
            return self.page
        from playwright.async_api import async_playwright
        preview = ensure(self.root)
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False, slow_mo=300, args=['--window-size=1100,800']
        )
        context = await self.browser.new_context(viewport={'width': 1060, 'height': 700})
        self.page = await context.new_page()
        self.page._preview_url = preview['preview_url']
        return self.page

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.page = self.browser = self.playwright = None
        stop(self.root)


_sessions = {}


async def get(root):
    key = str(Path(root).resolve())
    session = _sessions.get(key)
    if session is None:
        session = BrowserSession(key)
        _sessions[key] = session
    try:
        await session.start()
    except Exception:
        _sessions.pop(key, None)
        await session.close()
        raise
    return session


async def close(root):
    session = _sessions.pop(str(Path(root).resolve()), None)
    if session:
        await session.close()
    else:
        stop(root)


async def close_all():
    for root in list(_sessions):
        await close(root)
