import subprocess

from config.settings import WORKSPACE
from tools.file_tools import _confirm


def run_command(command: str) -> str:
    if not _confirm(f"执行命令 {command}"):
        return "用户拒绝了命令执行。请尝试其他方案。"
    result = subprocess.run(command, cwd=WORKSPACE, shell=True, capture_output=True, text=True, timeout=120)
    output = (result.stdout + result.stderr).strip()
    return f"退出码：{result.returncode}\n{output}".strip()
