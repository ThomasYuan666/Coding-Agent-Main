import json
import urllib.request
import urllib.error

from config.settings import API_URL, MODEL, get_api_key


def chat(messages: list, tools: list, on_event=None) -> dict:
    body = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
        "stream": True,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_api_key()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return _read_stream(response, on_event)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"调用 DeepSeek API 失败：HTTP {exc.code} {exc.reason}\n"
            f"模型：{MODEL}\n响应内容：{raw[:2000]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"调用 DeepSeek API 失败：网络连接错误\n"
            f"地址：{API_URL}\n详细信息：{exc.reason}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"调用 DeepSeek API 失败：{type(exc).__name__}: {exc}") from exc



def _read_stream(response, on_event=None) -> dict:
    message = {"role": "assistant", "content": ""}
    tool_calls = {}
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        for choice in chunk.get("choices", []):
            delta = choice.get("delta") or {}
            content = delta.get("content")
            reasoning = delta.get("reasoning_content")
            if reasoning:
                if on_event:
                    on_event("reasoning", reasoning)
            if content:
                message["content"] += content
                if on_event:
                    on_event("content", content)
            for call in delta.get("tool_calls") or []:
                index = call.get("index", 0)
                current = tool_calls.setdefault(index, {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                current["id"] += call.get("id") or ""
                function = call.get("function") or {}
                current["function"]["name"] += function.get("name") or ""
                current["function"]["arguments"] += function.get("arguments") or ""
    if tool_calls:
        message["tool_calls"] = [tool_calls[i] for i in sorted(tool_calls)]
    return {"choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}]}
