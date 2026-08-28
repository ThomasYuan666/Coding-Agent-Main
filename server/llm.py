import json
import urllib.request

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

    def chat(self, messages):
        body = {'model': 'deepseek-v4-flash', 'messages': messages, 'tools': TOOLS, 'stream': True}
        request = urllib.request.Request(self.url, json.dumps(body).encode(), {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.key}'})
        content = ''
        reasoning = ''
        calls = {}
        print(f'[llm] request messages={len(messages)}')
        with urllib.request.urlopen(request, timeout=120) as response:
            for line in response:
                text = line.decode('utf-8', errors='replace').strip()
                if text.startswith('data:') and text[5:].strip() != '[DONE]':
                    delta = json.loads(text[5:])['choices'][0]['delta']
                    content += delta.get('content') or ''
                    reasoning += delta.get('reasoning_content') or ''
                    for part in delta.get('tool_calls') or []:
                        index = part.get('index', 0)
                        call = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                        call['id'] = call['id'] or part.get('id', '')
                        fn = part.get('function') or {}
                        call['function']['name'] += fn.get('name') or ''
                        call['function']['arguments'] += fn.get('arguments') or ''
        result = {'content': content, 'reasoning_content': reasoning, 'tool_calls': list(calls.values())}
        print(f'[llm] response content={len(content)} reasoning={len(reasoning)} tools={[c["function"]["name"] for c in result["tool_calls"]]}')
        return result
