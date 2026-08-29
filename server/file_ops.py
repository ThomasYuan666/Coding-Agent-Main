"""文件系统操作模块"""
import os
from typing import List, Dict, Any


def build_tree(path: str, prefix: str = '') -> List[Dict[str, Any]]:
    """
    构建文件树结构

    Args:
        path: 目录路径
        prefix: 相对路径前缀（用于递归）

    Returns:
        文件树列表，每个元素包含 name, path, type
    """
    result = []

    # 忽略的目录
    ignore = {'.git', '__pycache__', 'node_modules', '.coding-agent', '.venv', 'venv'}

    try:
        items = sorted(os.listdir(path))
    except (FileNotFoundError, PermissionError):
        return result

    for item in items:
        if item.startswith('.') and item not in {'.env', '.gitignore'}:
            continue
        if item in ignore:
            continue

        full_path = os.path.join(path, item)
        rel_path = os.path.join(prefix, item) if prefix else item

        if os.path.isdir(full_path):
            result.append({
                'name': item,
                'path': rel_path,
                'type': 'folder',
                'children': build_tree(full_path, rel_path)
            })
        else:
            result.append({
                'name': item,
                'path': rel_path,
                'type': 'file'
            })

    return result
