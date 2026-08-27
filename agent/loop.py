import json

from agent.model_client import chat
from config.settings import MAX_TURNS, WORKSPACE
from tools.registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS


SYSTEM = f"你是 Windows 环境下的编程助手。只能通过工具操作 {WORKSPACE} 内的文件。需要修改文件或执行命令时使用工具；任务完成后简洁总结。"


def run_session() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "system", "content": SYSTEM}]
    print(f"工作目录：{WORKSPACE}\n输入任务，按 Ctrl+C 退出。")
    while True:
        user_input = input("\n你：").strip()
        if not user_input:
            continue
        messages.append({"role": "user", "content": user_input})
        for _ in range(MAX_TURNS):
            response = chat(messages, TOOL_DEFINITIONS)
            message = response["choices"][0]["message"]
            messages.append(message)
            calls = message.get("tool_calls") or []
            if not calls:
                break
            for call in calls:
                name = call["function"]["name"]
                args = json.loads(call["function"].get("arguments") or "{}")
                print(f"\n工具：{name} {args}")
                try:
                    result = TOOL_FUNCTIONS[name](**args)
                except Exception as exc:
                    result = f"工具执行失败：{exc}"
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
        else:
            print("\n本轮执行次数已达到上限，请换一种描述继续。")
