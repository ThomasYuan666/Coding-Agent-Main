from tools.file_tools import list_files, read_file, write_file, delete_file
from tools.command_tool import run_command


TOOL_FUNCTIONS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "delete_file": delete_file,
    "run_command": run_command,
}


TOOL_DEFINITIONS = [
    {"type": "function", "function": {"name": "list_files", "description": "查看工作目录中的文件。", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "读取工作目录内的文本文件。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "整体创建或覆盖工作目录内的文本文件。执行前必须征得用户同意。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "delete_file", "description": "删除工作目录内的文件。执行前必须征得用户同意。", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "在工作目录中执行 Windows 命令。执行前必须征得用户同意。", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]
