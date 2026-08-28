import json
from pathlib import Path

class ConversationManager:
    def __init__(self, root):
        self.file = Path(root) / '.coding-agent' / 'conversation.json'

    def load(self):
        try: return json.loads(self.file.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError): return []

    def save(self, messages):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding='utf-8')

    def add(self, message):
        messages = self.load(); messages.append(message); self.save(messages)
