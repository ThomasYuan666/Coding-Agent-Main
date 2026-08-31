import json
import os
from pathlib import Path
from ..workspace.path_utils import safe_path

class RollbackManager:
    def __init__(self, root):
        self.root = Path(root)
        self.file = self.root / '.coding-agent' / 'snapshots.json'

    def load(self):
        try: return json.loads(self.file.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError): return []

    def begin(self, turn_id, history_length):
        records = [r for r in self.load() if r['turn_id'] != turn_id]
        tasks_file = self.root / '.coding-agent' / 'tasks.json'
        try:
            tasks = json.loads(tasks_file.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            tasks = []
        screenshots = [p.name for p in (self.root / '.coding-agent' / 'screenshots').glob('*.png')] if (self.root / '.coding-agent' / 'screenshots').exists() else []
        records.append({'turn_id': turn_id, 'history_length': history_length, 'files': [], 'tasks': tasks, 'screenshots': screenshots})
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
        tasks_file = self.root / '.coding-agent' / 'tasks.json'
        if 'tasks' in record:
            tasks_file.parent.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text(json.dumps(record['tasks'], ensure_ascii=False, indent=2), encoding='utf-8')
        keep = set(record.get('screenshots', []))
        screenshot_dir = self.root / '.coding-agent' / 'screenshots'
        if screenshot_dir.exists():
            for path in screenshot_dir.glob('*.png'):
                if path.name not in keep:
                    path.unlink()
        return record['history_length']

    def _save(self, records):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
