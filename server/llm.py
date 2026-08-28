import json
import urllib.error
import urllib.request


class LLMClient:
    def __init__(self, key):
        self.key = key
        self.url = 'https://api.deepseek.com/chat/completions'

    def chat(self, messages):
        body = {'model': 'deepseek-v4-flash', 'messages': messages, 'stream': True}
        req = urllib.request.Request(self.url, json.dumps(body).encode(), {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.key}'})
        with urllib.request.urlopen(req, timeout=120) as response:
            for line in response:
                text = line.decode('utf-8', errors='replace').strip()
                if text.startswith('data:') and text[5:].strip() != '[DONE]':
                    try:
                        content = json.loads(text[5:]).get('choices', [{}])[0].get('delta', {}).get('content')
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
