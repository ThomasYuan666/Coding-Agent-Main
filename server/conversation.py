"""对话历史管理模块"""
import json
import os
from typing import List, Dict, Any


class ConversationManager:
    """管理对话历史的加载、保存和操作"""

    def __init__(self, root: str):
        """
        初始化对话管理器

        Args:
            root: 工作区根目录
        """
        self.root = root
        self.conv_dir = os.path.join(root, '.coding-agent')
        self.conv_file = os.path.join(self.conv_dir, 'conversation.json')

    def load(self) -> List[Dict[str, Any]]:
        """
        加载对话历史

        Returns:
            消息列表
        """
        if os.path.exists(self.conv_file):
            try:
                with open(self.conv_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []

    def save(self, messages: List[Dict[str, Any]]) -> None:
        """
        保存对话历史

        Args:
            messages: 消息列表
        """
        os.makedirs(self.conv_dir, exist_ok=True)
        with open(self.conv_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)

    def revert_to(self, index: int) -> List[Dict[str, Any]]:
        """
        回退到指定消息索引

        Args:
            index: 消息索引（保留到该索引，删除之后的所有消息）

        Returns:
            截断后的消息列表
        """
        messages = self.load()
        truncated = messages[:index + 1]
        self.save(truncated)
        return truncated

    def add_message(self, role: str, content: str) -> None:
        """
        添加新消息

        Args:
            role: 消息角色 (user/assistant)
            content: 消息内容
        """
        messages = self.load()
        messages.append({'role': role, 'content': content})
        self.save(messages)

    def clear(self) -> None:
        """清空对话历史"""
        self.save([])
