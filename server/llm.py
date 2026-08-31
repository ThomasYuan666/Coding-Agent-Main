import json
import httpx
from config.settings import DEFAULT_MODEL, MODEL_VISION

TOOLS = [
    {'type': 'function', 'function': {'name': 'run_checks', 'description': '代码修改后运行无副作用基础检查。不会安装依赖或修改配置；检查通过后再进行浏览器测试。', 'parameters': {'type': 'object', 'properties': {}}}},
    {'type': 'function', 'function': {'name': 'read_file', 'description': '读取当前工作区内的文本文件', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}},
    {'type': 'function', 'function': {'name': 'write_file', 'description': '创建或覆盖当前工作区内的文件', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['path', 'content']}}},
    {'type': 'function', 'function': {'name': 'delete_file', 'description': '删除当前工作区内的文件', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}},
    {'type': 'function', 'function': {'name': 'run_command', 'description': '在当前工作区执行 Windows 命令', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}
]

TOOLS.extend([
    {'type': 'function', 'function': {'name': 'browser_open', 'description': '在当前工作区浏览器会话中打开网页。', 'parameters': {'type': 'object', 'properties': {'url': {'type': 'string'}}, 'required': []}}},
    {'type': 'function', 'function': {'name': 'browser_click', 'description': '点击网页中的元素。', 'parameters': {'type': 'object', 'properties': {'selector': {'type': 'string'}}, 'required': ['selector']}}},
    {'type': 'function', 'function': {'name': 'browser_press', 'description': '向网页发送键盘按键。', 'parameters': {'type': 'object', 'properties': {'key': {'type': 'string'}}, 'required': ['key']}}},
    {'type': 'function', 'function': {'name': 'browser_type', 'description': '向网页输入框填写文本。', 'parameters': {'type': 'object', 'properties': {'selector': {'type': 'string'}, 'text': {'type': 'string'}}, 'required': ['selector', 'text']}}},
    {'type': 'function', 'function': {'name': 'browser_wait', 'description': '等待网页状态变化。', 'parameters': {'type': 'object', 'properties': {'ms': {'type': 'integer'}}, 'required': []}}},
    {'type': 'function', 'function': {'name': 'browser_observe', 'description': '读取当前网页标题、文本和可选 JavaScript 状态。', 'parameters': {'type': 'object', 'properties': {'expression': {'type': 'string'}}, 'required': []}}},
    {'type': 'function', 'function': {'name': 'browser_close', 'description': '关闭当前工作区的浏览器测试会话。', 'parameters': {'type': 'object', 'properties': {}}}},
])

TOOLS.extend([
    {'type': 'function', 'function': {'name': 'create_plan', 'description': '为复杂编程任务创建计划，简单问答不需要调用；已有任务可追加修复计划', 'parameters': {'type': 'object', 'properties': {'task_id': {'type': 'string'}, 'goal': {'type': 'string'}, 'steps': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['goal', 'steps']}}},
    {'type': 'function', 'function': {'name': 'update_plan', 'description': '更新计划步骤状态', 'parameters': {'type': 'object', 'properties': {'task_id': {'type': 'string'}, 'step_id': {'type': 'string'}, 'status': {'type': 'string'}, 'reason': {'type': 'string'}}, 'required': ['task_id', 'step_id', 'status']}}},
    {'type': 'function', 'function': {'name': 'finish_task', 'description': '确认当前任务已经完成', 'parameters': {'type': 'object', 'properties': {'task_id': {'type': 'string'}}, 'required': ['task_id']}}},
    {'type': 'function', 'function': {'name': 'report_failure', 'description': '报告任务步骤失败原因', 'parameters': {'type': 'object', 'properties': {'task_id': {'type': 'string'}, 'step_id': {'type': 'string'}, 'reason': {'type': 'string'}}, 'required': ['task_id', 'reason']}}}
])

class LLMClient:
    def __init__(self, key):
        self.key = key
        self.url = 'https://api.deepseek.com/chat/completions'

    async def stream_chat(self, messages, model=DEFAULT_MODEL, use_tools=True, reasoning_effort='low'):
        body = {'model': model, 'messages': _api_messages(messages), 'stream': True,
                'stream_options': {'include_usage': True}}
        body['thinking'] = {'type': 'disabled' if reasoning_effort == 'off' else 'enabled'}
        if reasoning_effort != 'off':
            body['reasoning_effort'] = reasoning_effort
        if use_tools:
            body['tools'] = TOOLS
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.key}'}
        content = ''
        reasoning = ''
        calls = {}
        print(f'[llm] request messages={len(messages)}')
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            async with client.stream('POST', self.url, json=body, headers=headers) as response:
                if response.is_error:
                    details = (await response.aread()).decode('utf-8', errors='replace')
                    print(f'[llm] HTTP {response.status_code} body={details[:2000]}')
                    response.raise_for_status()
                async for line in response.aiter_lines():
                    text = line.strip()
                    if text.startswith('data:') and text[5:].strip() != '[DONE]':
                        chunk = json.loads(text[5:])
                        if chunk.get('usage'):
                            yield {'type': 'usage', 'usage': chunk['usage']}
                        if not chunk.get('choices'):
                            continue
                        delta = chunk['choices'][0]['delta']
                        content_piece = delta.get('content') or ''
                        reasoning_piece = delta.get('reasoning_content') or ''
                        content += content_piece
                        reasoning += reasoning_piece
                        if reasoning_piece: yield {'type': 'reasoning', 'content': reasoning_piece}
                        if content_piece: yield {'type': 'content', 'content': content_piece}
                        for part in delta.get('tool_calls') or []:
                            index = part.get('index', 0)
                            call = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                            call['id'] = call['id'] or part.get('id', '')
                            fn = part.get('function') or {}
                            call['function']['name'] += fn.get('name') or ''
                            call['function']['arguments'] += fn.get('arguments') or ''
        result = {'content': content, 'reasoning_content': reasoning, 'tool_calls': list(calls.values())}
        print(f'[llm] response content={len(content)} reasoning={len(reasoning)} tools={[c["function"]["name"] for c in result["tool_calls"]]}')
        yield {'type': 'done', 'result': result}

    async def summarize(self, prompt, model=DEFAULT_MODEL):
        content = ''
        usage = None
        async for event in self.stream_chat([{'role': 'user', 'content': prompt}], model, use_tools=False, reasoning_effort='off'):
            if event['type'] == 'content':
                content += event['content']
            elif event['type'] == 'usage':
                usage = event['usage']
        if not usage:
            raise RuntimeError('摘要请求未返回 usage')
        return content

    async def describe_image(self, content):
        prompt = [{'role': 'user', 'content': content + [
            {'type': 'text', 'text': '请用简洁的文字描述这张图片，供后续历史摘要使用。'}
        ]}]
        return await self._text_request(prompt, MODEL_VISION)

    async def _text_request(self, messages, model):
        content = ''
        usage = None
        async for event in self.stream_chat(messages, model, use_tools=False, reasoning_effort='off'):
            if event['type'] == 'content':
                content += event['content']
            elif event['type'] == 'usage':
                usage = event['usage']
        if not usage:
            raise RuntimeError('文本请求未返回 usage')
        return content


def _api_messages(messages):
    """Remove local UI metadata before sending messages to DeepSeek."""
    allowed = {'role', 'content', 'tool_calls', 'tool_call_id', 'name', 'reasoning_content'}
    return [{key: value for key, value in message.items() if key in allowed} for message in messages]
