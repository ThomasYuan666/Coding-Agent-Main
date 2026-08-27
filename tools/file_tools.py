from pathlib import Path

from config.settings import WORKSPACE


def _path(relative: str) -> Path:
    root = WORKSPACE.resolve()
    target = (root / relative).resolve()
    if target != root and root not in target.parents:
        raise ValueError("路径必须位于 workspace 内。")
    return target


def _confirm(action: str) -> bool:
    return input(f"即将{action}，是否继续？[y/N] ").strip().lower() in {"y", "yes"}


def list_files() -> str:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    return "\n".join(str(p.relative_to(WORKSPACE)) for p in WORKSPACE.rglob("*")) or "(目录为空)"


def read_file(path: str) -> str:
    return _path(path).read_text(encoding="utf-8")


def write_file(path: str, content: str) -> str:
    target = _path(path)
    if not _confirm(f"写入文件 {path}"):
        return "用户拒绝了写入操作。请尝试其他方案。"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {path}。"


def delete_file(path: str) -> str:
    target = _path(path)
    if not _confirm(f"删除文件 {path}"):
        return "用户拒绝了删除操作。请尝试其他方案。"
    target.unlink()
    return f"已删除 {path}。"
