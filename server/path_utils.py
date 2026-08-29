import os
from pathlib import Path

CONTAINER = Path(__file__).resolve().parents[2] / 'workspace'

def safe_path(root, relative_path):
    base = os.path.realpath(root)
    target = os.path.realpath(os.path.join(base, relative_path))
    if target == base or not target.startswith(base + os.sep):
        raise ValueError('路径不在当前工作区内')
    return target


def resolve_root(value):
    path = Path(value)
    return (CONTAINER / path.name if not path.is_absolute() else path).resolve()
