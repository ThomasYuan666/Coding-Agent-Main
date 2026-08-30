import json
import uuid
from datetime import datetime
from pathlib import Path


class TaskManager:
    def __init__(self, root):
        self.file = Path(root) / '.coding-agent' / 'tasks.json'

    def load(self):
        try:
            data = json.loads(self.file.read_text(encoding='utf-8'))
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self, tasks):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding='utf-8')

    def create(self, goal, steps):
        task = {'task_id': uuid.uuid4().hex, 'goal': goal, 'status': 'running', 'plans': [{
            'plan_id': uuid.uuid4().hex, 'goal': goal, 'status': 'running',
            'steps': [{'step_id': uuid.uuid4().hex, 'title': str(step), 'status': 'pending'} for step in steps]
        }], 'created_at': datetime.now().isoformat(timespec='seconds')}
        tasks = self.load(); tasks.append(task); self._save(tasks)
        return task

    def add_plan(self, task_id, goal, steps):
        tasks = self.load()
        task = next((item for item in tasks if item.get('task_id') == task_id), None)
        if not task:
            return None
        task['plans'].append({
            'plan_id': uuid.uuid4().hex,
            'goal': goal,
            'status': 'running',
            'steps': [{'step_id': uuid.uuid4().hex, 'title': str(step), 'status': 'pending'} for step in steps],
        })
        task['status'] = 'running'
        self._save(tasks)
        return task

    def update_step(self, task_id, step_id, status, reason=''):
        tasks = self.load(); task = next((item for item in tasks if item.get('task_id') == task_id), None)
        if not task: return None
        for plan in task['plans']:
            for step in plan['steps']:
                if step['step_id'] == step_id:
                    step['status'] = status
                    if reason: step['reason'] = reason
        self._save(tasks); return task

    def finish(self, task_id):
        tasks = self.load(); task = next((item for item in tasks if item.get('task_id') == task_id), None)
        if not task: return None
        task['status'] = 'completed'
        for plan in task['plans']:
            if plan['status'] == 'running': plan['status'] = 'completed'
        self._save(tasks); return task
