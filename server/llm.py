import json
import httpx
from config.settings import DEFAULT_MODEL

TOOLS = [
    {'type': 'function', 'function': {'name': 'read_file', 'description': '读取当前工作区内的文本文件', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}},
    {'type': 'function', 'function': {'name': 'write_file', 'description': '创建或覆盖当前工作区内的文件', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['path', 'content']}}},
    {'type': 'function', 'function': {'name': 'delete_file', 'description': '删除当前工作区内的文件', 'parameters': {'type': 'object', 'properties': {'path': {'type': 'string'}}, 'required': ['path']}}},
    {'type': 'function', 'function': {'name': 'run_command', 'description': '在当前工作区执行 Windows 命令', 'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}
]

class LLMClient:
    def __init__(self, key):
        self.key = key
        self.url = 'https://api.deepseek.com/chat/completions'

    async def stream_chat(self, messages, model=DEFAULT_MODEL):
        body = {'model': model, 'messages': _api_messages(messages), 'tools': TOOLS, 'stream': True}
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
                        delta = json.loads(text[5:])['choices'][0]['delta']
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


def _api_messages(messages):
    """Remove local UI metadata before sending messages to DeepSeek."""
    allowed = {'role', 'content', 'tool_calls', 'tool_call_id', 'name', 'reasoning_content'}
    return [{key: value for key, value in message.items() if key in allowed} for message in messages]
