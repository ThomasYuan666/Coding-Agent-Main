async def observe(page, expression=None):
    state = None
    if expression:
        state = await page.evaluate(expression)
    return {
        'url': page.url,
        'title': await page.title(),
        'text': (await page.locator('body').inner_text())[:12000],
        'state': state,
    }
