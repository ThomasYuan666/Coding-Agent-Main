import json
from pathlib import Path

from config.settings import CONTEXT_LIMIT, CONTEXT_THRESHOLD, RECENT_ROUNDS, SUMMARY_TARGET, DEFAULT_MODEL


SYSTEM_PROMPT = (
    "你是一个运行在 Windows 工作区中的 coding agent。通过提供的工具完成用户任务，"
    "涉及写文件、删除文件或执行命令时必须等待用户审批。"
)


class ContextManager:
    def __init__(self, root):
        self.root = Path(root)
        self.file = self.root / '.coding-agent' / 'summary.json'

    def load_summary(self):
        try:
            data = json.loads(self.file.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {'content': '', 'covered': 0}
        except (FileNotFoundError, json.JSONDecodeError):
            return {'content': '', 'covered': 0}

    def save_summary(self, content, covered):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps({'content': content, 'covered': covered}, ensure_ascii=False, indent=2), encoding='utf-8')

    def record_usage(self, usage):
        data = self.load_summary()
        data['last_prompt_tokens'] = usage.get('prompt_tokens')
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def last_usage(self):
        return self.load_summary().get('last_prompt_tokens') or 0

    def invalidate(self):
        self.file.unlink(missing_ok=True)

    def build(self, history):
        rounds = self._rounds(history)
        recent = rounds[-RECENT_ROUNDS:]
        summary = self.load_summary().get('content', '')
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        if summary:
            messages.append({'role': 'system', 'content': f'历史摘要：\n{summary}'})
        for group in recent:
            messages.extend(group)
        return messages

    def needs_compaction(self, prompt_tokens):
        return prompt_tokens >= int(CONTEXT_LIMIT * CONTEXT_THRESHOLD)

    def needs_initial_summary(self, history):
        return not self.load_summary().get('content') and len(self._rounds(history)) > RECENT_ROUNDS

    async def compact(self, history, client):
        summary, messages, covered = self.compression_source(history)
        if not messages:
            return False
        prepared = []
        for message in messages:
            content = message.get('content')
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part.get('type') == 'text':
                        parts.append(part.get('text', ''))
                    elif part.get('type') == 'image_url':
                        parts.append(f"[图片描述] {await client.describe_image(content)}")
                        break
                prepared.append({**message, 'content': '\n'.join(parts)})
            else:
                prepared.append(message)
        content = await client.summarize(format_compression_prompt(summary, prepared), DEFAULT_MODEL)
        self.save_summary(content, covered)
        return True

    def compression_source(self, history):
        rounds = self._rounds(history)
        older = rounds[:-RECENT_ROUNDS] if len(rounds) > RECENT_ROUNDS else []
        covered = self.load_summary().get('covered', 0)
        flat = [message for group in older for message in group]
        return self.load_summary().get('content', ''), flat[covered:], len(flat)

    @staticmethod
    def _rounds(history):
        rounds, current = [], []
        for message in history:
            if message.get('role') == 'user' and current:
                rounds.append(current)
                current = []
            current.append(message)
        if current:
            rounds.append(current)
        return rounds


def format_compression_prompt(summary, messages):
    payload = json.dumps(messages, ensure_ascii=False)
    prefix = f'已有历史摘要：\n{summary}\n\n' if summary else ''
    target = int(SUMMARY_TARGET * 100)
    return prefix + f'请根据以下新增对话生成新的历史摘要。保留事实、用户偏好、已完成工作和重要文件状态，控制在上下文上限的{target}%左右。\n' + payload
