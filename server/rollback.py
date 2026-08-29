import json
import os
from pathlib import Path
from .path_utils import safe_path

class RollbackManager:
    def __init__(self, root):
        self.root = Path(root)
        self.file = self.root / '.coding-agent' / 'snapshots.json'

    def load(self):
        try: return json.loads(self.file.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError): return []

    def begin(self, turn_id, history_length):
        records = [r for r in self.load() if r['turn_id'] != turn_id]
        records.append({'turn_id': turn_id, 'history_length': history_length, 'files': []})
        self._save(records[-3:])

    def record(self, turn_id, change):
        records = self.load()
        for record in records:
            if record['turn_id'] == turn_id and not any(f['path'] == change['path'] for f in record['files']):
                record['files'].append({'path': change['path'], 'exists': change['exists'], 'content': change['old_content']})
        self._save(records)

    def restore(self, turn_id):
        records = self.load()
        record = next((r for r in records if r['turn_id'] == turn_id), None)
        if not record: return None
        for item in record['files']:
            target = Path(safe_path(self.root, item['path']))
            if item['exists']:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item['content'], encoding='utf-8')
            elif target.exists(): target.unlink()
        return record['history_length']

    def _save(self, records):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
