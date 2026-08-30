import json
import inspect
import time


async def run(url, steps, on_step=None):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {'result': '未安装 Playwright，请执行 pip install playwright 并运行 playwright install chromium', 'status': 'error'}

    results = []
    console_errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=350,
            args=['--window-size=1100,800'],
        )
        page = await browser.new_page(viewport={'width': 1060, 'height': 700})
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        try:
            for step in steps[:20]:
                action = step.get('action')
                if on_step:
                    update = on_step({'action': action, 'status': 'running'})
                    if inspect.isawaitable(update):
                        await update
                if action == 'open':
                    await page.goto(_target_url(url, step.get('url', '/')), wait_until='domcontentloaded')
                elif action == 'go_back':
                    await page.go_back(wait_until='domcontentloaded')
                elif action == 'go_forward':
                    await page.go_forward(wait_until='domcontentloaded')
                elif action == 'reload':
                    await page.reload(wait_until='domcontentloaded')
                elif action == 'click':
                    await page.locator(step['selector']).click()
                elif action == 'press':
                    await page.keyboard.press(step['key'])
                elif action == 'type':
                    await page.locator(step['selector']).fill(step.get('text', ''))
                elif action == 'wait':
                    await page.wait_for_timeout(min(int(step.get('ms', 300)), 5000))
                elif action == 'wait_until':
                    await wait_until(page, step)
                elif action == 'read_state':
                    result = {'action': action, 'status': 'passed', 'value': await read_state(page, step)}
                    results.append(result)
                    if on_step:
                        update = on_step(result)
                        if inspect.isawaitable(update):
                            await update
                    continue
                elif action == 'assert_state':
                    await assert_state(page, step)
                elif action == 'assert_visible':
                    await page.locator(step['selector']).wait_for(state='visible', timeout=3000)
                elif action == 'assert_text':
                    actual = await page.locator(step['selector']).inner_text()
                    expected = step.get('text', '')
                    if expected not in actual:
                        raise AssertionError(f'文本不匹配：期望包含 {expected!r}，实际为 {actual!r}')
                elif action == 'read_console':
                    pass
                else:
                    raise ValueError(f'不支持的测试动作：{action}')
                result = {'action': action, 'status': 'passed'}
                results.append(result)
                if on_step:
                    update = on_step(result)
                    if inspect.isawaitable(update):
                        await update
        except Exception as exc:
            result = {'action': step.get('action', ''), 'status': 'failed', 'error': str(exc)}
            results.append(result)
            if on_step:
                update = on_step(result)
                if inspect.isawaitable(update):
                    await update
        finally:
            await browser.close()
    status = 'failed' if any(item['status'] == 'failed' for item in results) else 'passed'
    return {'result': json.dumps({'status': status, 'steps': results, 'console_errors': console_errors}, ensure_ascii=False), 'status': status}


def _target_url(base, value):
    if value.startswith('http://') or value.startswith('https://'):
        return value
    return base.rstrip('/') + '/' + value.lstrip('/')


async def wait_until(page, step):
    condition = step.get('condition')
    timeout = min(int(step.get('timeout', 3000)), 10000)
    if condition == 'selector_visible':
        await page.locator(step['selector']).wait_for(state='visible', timeout=timeout)
        return
    if condition == 'text_contains':
        await page.get_by_text(step['text'], exact=False).first.wait_for(state='visible', timeout=timeout)
        return
    if condition == 'url_contains':
        await page.wait_for_url(f"**{step['text']}**", timeout=timeout)
        return
    if condition in {'state_equals', 'state_changed'}:
        expected = step.get('value')
        expression = step.get('expression', 'window.gameState')
        before = await page.evaluate(expression) if condition == 'state_changed' else None
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            value = await page.evaluate(expression)
            if (condition == 'state_equals' and value == expected) or (condition == 'state_changed' and value != before):
                return
            await page.wait_for_timeout(100)
        raise AssertionError(f'等待条件超时：{condition}')
    raise ValueError(f'不支持的等待条件：{condition}')


async def read_state(page, step):
    return await page.evaluate(step.get('expression', 'window.gameState'))


async def assert_state(page, step):
    actual = await read_state(page, step)
    if actual != step.get('value'):
        raise AssertionError(f'状态不匹配：期望 {step.get("value")!r}，实际 {actual!r}')
