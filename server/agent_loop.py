import json

from .file_ops import build_tree
from .rollback import RollbackManager
from .tools import apply_write, execute, prepare_write


async def agent_turn(websocket, client, manager, root, turn_id, model):
    print(f"[agent] turn root={root}")
    try:
        response = None
        async for event in client.stream_chat(manager.load(), model):
            if event["type"] == "reasoning":
                await websocket.send_json({"type": "reasoning", "content": event["content"]})
            elif event["type"] == "content":
                await websocket.send_json({"type": "chunk", "content": event["content"]})
            elif event["type"] == "done":
                response = event["result"]
    except Exception as exc:
        print(f"[agent] model error: {type(exc).__name__}: {exc!r}")
        await websocket.send_json({"type": "error", "content": f"模型调用失败：{exc}"})
        await websocket.send_json({"type": "end"})
        return None

    calls = response.get("tool_calls", [])
    if not calls:
        manager.add({
            "role": "assistant",
            "content": response.get("content", ""),
            "reasoning_content": response.get("reasoning_content", ""),
            "turn_id": turn_id,
        })
        await websocket.send_json({"type": "end"})
        return None

    manager.add({
        "role": "assistant",
        "content": response.get("content") or None,
        "reasoning_content": response.get("reasoning_content", ""),
        "tool_calls": calls,
        "turn_id": turn_id,
    })
    parsed_calls = [_parse_call(call) for call in calls]
    pending_items = []

    write_calls = [item for item in parsed_calls if item[1] == "write_file"]
    if write_calls:
        changes = [prepare_write(root, args["path"], args["content"]) for _, _, args in write_calls]
        for _, name, args in write_calls:
            await websocket.send_json({
                "type": "tool_call",
                "tool": name,
                "arguments": json.dumps(args, ensure_ascii=False),
            })
        pending_items.append({"kind": "diff", "calls": write_calls, "changes": changes})

    for call, name, args in parsed_calls:
        if name == "write_file":
            continue
        if name == "read_file":
            result = execute(name, args, root)
            manager.add({"role": "tool", "tool_call_id": call["id"], "content": result["result"]})
            await websocket.send_json({"type": "tool", "tool": name, "result": result["result"]})
        elif name in {"delete_file", "run_command"}:
            pending_items.append({"kind": "command", "call": call, "name": name, "args": args})
        else:
            result = execute(name, args, root)
            manager.add({"role": "tool", "tool_call_id": call["id"], "content": result["result"]})
            await websocket.send_json({"type": "tool", "tool": name, "result": result["result"]})

    if pending_items:
        pending = {"items": pending_items, "index": 0, "turn_id": turn_id, "model": model}
        await _show_pending(websocket, root, pending_items[0])
        return pending
    return await agent_turn(websocket, client, manager, root, turn_id, model)


async def resolve_approval(websocket, client, manager, root, pending, approved):
    item = pending["items"][pending["index"]]
    if item["kind"] == "diff":
        status = await _resolve_diff(websocket, manager, root, pending["turn_id"], item, approved)
        await websocket.send_json({"type": "tool", "tool": "write_file", "result": status})
    else:
        result = _resolve_command(manager, root, pending["turn_id"], item, approved)
        await websocket.send_json({"type": "tool", "tool": item["name"], "result": result})
        if approved and item["name"] == "delete_file":
            await websocket.send_json({"type": "files", "files": build_tree(root)})

    pending["index"] += 1
    if pending["index"] < len(pending["items"]):
        await _show_pending(websocket, root, pending["items"][pending["index"]])
        return pending
    return await agent_turn(
        websocket,
        client,
        manager,
        root,
        pending["turn_id"],
        pending["model"],
    )


def _parse_call(call):
    name = call["function"]["name"]
    print(f"[tool] requested name={name}")
    try:
        arguments = json.loads(call["function"]["arguments"] or "{}")
    except json.JSONDecodeError as exc:
        print(f"[tool] invalid arguments name={name}: {exc}")
        arguments = {}
    return call, name, arguments


async def _show_pending(websocket, root, item):
    if item["kind"] == "diff":
        await websocket.send_json({"type": "diff", "files": item["changes"]})
        return
    preview = execute(item["name"], item["args"], root)
    await websocket.send_json({
        "type": "approval",
        "tool": item["name"],
        "command": preview["command"],
        "reason": preview["reason"],
    })


async def _resolve_diff(websocket, manager, root, turn_id, item, approved):
    if approved:
        for change in item["changes"]:
            RollbackManager(root).record(turn_id, change)
            apply_write(root, change)
    status = "Files accepted and written." if approved else "User rejected the file changes; try another approach."
    for call, _, _ in item["calls"]:
        manager.add({"role": "tool", "tool_call_id": call["id"], "content": status})
    await websocket.send_json({"type": "diff_status", "status": "accepted" if approved else "rejected"})
    if approved:
        await websocket.send_json({"type": "files", "files": build_tree(root)})
    return status


def _resolve_command(manager, root, turn_id, item, approved):
    if approved and item["name"] == "delete_file":
        RollbackManager(root).record(
            turn_id,
            prepare_write(root, item["args"]["path"], ""),
        )
    result = execute(item["name"], item["args"], root, approved=approved)
    if not approved:
        result = {"result": "User rejected this operation; try another approach."}
    manager.add({"role": "tool", "tool_call_id": item["call"]["id"], "content": result["result"]})
    return result["result"]
