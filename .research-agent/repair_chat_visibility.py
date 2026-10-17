"""Repair only this project's hidden entries using supported Codex APIs."""
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, "/home/zwj/.codex/skills/research-agent/scripts")
from codex_rpc import CodexRpc

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = ROOT / ".research-agent/chat_visibility_repair.json"
SETUP = ROOT / ".research-agent/chat_setup_receipt.json"
PROVIDER = {
    "name": "OpenAI Official HTTP",
    "wire_api": "responses",
    "requires_openai_auth": True,
    "base_url": "https://chatgpt.com/backend-api/codex",
}


def save(data):
    RECEIPT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    if (ROOT / ".research-agent/fresh_section_chats.json").exists():
        raise SystemExit("Prior bindings cancelled by user; do not restore forked entries.")
    original = json.loads(SETUP.read_text())
    state = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {
        "root": str(ROOT),
        "reason": "Creation provider openai is excluded by the desktop's official_http listing. Resume changes runtime state but not the original rollout metadata.",
        "method": "Native thread/fork preserves history; archive only replaced setup entries after default-list verification.",
        "original_setup": original,
        "threads": {},
    }
    original = state["original_setup"]
    with CodexRpc(timeout=30) as rpc:
        for role, old in original["threads"].items():
            if role in state["threads"] and state["threads"][role].get("initialization"):
                continue
            requested = old.get("requested") or {}
            model = requested.get("model") or old["readback"]["model"]
            effort = requested.get("effort")
            config = {"model_providers": {"official_http": PROVIDER}}
            if effort:
                config["model_reasoning_effort"] = effort
            params = {
                "threadId": old["id"], "excludeTurns": True,
                "deferGoalContinuation": True, "threadSource": "user",
                "cwd": str(ROOT), "model": model,
                "modelProvider": "official_http", "config": config,
                "approvalPolicy": "never", "permissions": ":danger-full-access",
            }
            if role in state["threads"]:
                record = state["threads"][role]
                rpc.request("thread/resume", {
                    "threadId": record["id"], "excludeTurns": True,
                    "model": model, "modelProvider": "official_http", "config": config,
                })
            else:
                result = rpc.request("thread/fork", params)
                record = {"id": result["thread"]["id"], "original_id": old["id"],
                          "title": old["title"], "model": model, "effort": effort,
                          "fork_response": result}
                state["threads"][role] = record
            save(state)
            rpc.request("thread/name/set", {"threadId": record["id"], "name": old["title"]})
            rpc.request("thread/metadata/update", {
                "threadId": record["id"], "projectId": original["project_id"],
            })
            rpc.request("thread/section/move", {
                "threadId": record["id"], "sectionId": original["section"]["id"],
                "beforeThreadId": original["preserved_historical_threads"][0],
            })
            params = {"threadId": record["id"], "model": model,
                      "clientUserMessageId": str(uuid.uuid4()), "input": [{
                          "type": "text",
                          "text": "本轮仅修复项目对话的侧栏入口，原对话历史已保留。项目仍为 /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM；工程暂停。不要调用工具、修改文件、启动任何任务或发送其他会话消息。只回复一句：本职责对话已就绪，等待用户指令。",
                      }]}
            if effort:
                params["effort"] = effort
            record["initialization"] = rpc.request("turn/start", params)
            save(state)
            print(json.dumps({"role": role, "id": record["id"], "initialization_started": True}), flush=True)
    with CodexRpc(timeout=30) as rpc:
        state["default_cwd_list"] = rpc.request("thread/list", {"cwd": str(ROOT), "limit": 100})
        visible = {t["id"] for t in state["default_cwd_list"]["data"]}
        assert all(r["id"] in visible for r in state["threads"].values())
        for record in state["threads"].values():
            if not record.get("original_archived"):
                rpc.request("thread/archive", {"threadId": record["original_id"]})
                record["original_archived"] = True
                save(state)
        state["default_section_list"] = rpc.request("thread/list", {
            "sectionId": original["section"]["id"], "limit": 100,
        })
        state["default_project_list"] = rpc.request("thread/list", {
            "projectId": original["project_id"], "limit": 100,
        })
        visible = {t["id"] for t in state["default_section_list"]["data"]}
        assert all(t in visible for t in original["preserved_historical_threads"])
        assert all(r["id"] in visible for r in state["threads"].values())
        setup = json.loads(json.dumps(original))
        binding = json.loads((ROOT / ".research-agent/codex_binding_input.json").read_text())
        for role, record in state["threads"].items():
            config = {"model_providers": {"official_http": PROVIDER}}
            if record["effort"]:
                config["model_reasoning_effort"] = record["effort"]
            observed = rpc.request("thread/resume", {
                "threadId": record["id"], "excludeTurns": True,
                "model": record["model"], "modelProvider": "official_http", "config": config,
            })
            assert observed["model"] == record["model"]
            assert observed["reasoningEffort"] == record["effort"]
            assert observed["approvalPolicy"] == "never"
            assert observed["sandbox"]["type"] == "dangerFullAccess"
            assert observed["thread"]["cwd"] == str(ROOT)
            turns = rpc.request("thread/turns/list", {
                "threadId": record["id"], "limit": 1, "itemsView": "full",
            })
            assert turns["data"][0]["status"] == "completed"
            assert not turns["data"][0].get("error")
            rpc.request("thread/name/set", {"threadId": record["id"], "name": record["title"]})
            readback = rpc.request("thread/read", {"threadId": record["id"]})
            setup["threads"][role] = {
                "id": record["id"], "title": record["title"],
                "requested": original["threads"][role].get("requested"),
                "created_response": record["fork_response"],
                "initialization": record["initialization"], "readback": observed,
                "turns": turns, "title_readback": readback,
                "replaces_archived_id": record["original_id"],
            }
            binding["threads"][role]["id"] = record["id"]
        setup["section_members_readback"] = state["default_section_list"]
        setup["default_project_list"] = state["default_project_list"]
        setup["visibility_repair_receipt"] = str(RECEIPT)
        setup["section_status"] = "verified_default_listing"
        SETUP.write_text(json.dumps(setup, ensure_ascii=False, indent=2) + "\n")
        (ROOT / ".research-agent/codex_binding_input.json").write_text(
            json.dumps(binding, ensure_ascii=False, indent=2) + "\n")
        state["status"] = "verified_default_listing_and_bindings_updated"
        save(state)
        print("Default cwd/project/section listing verified; old historical chats retained.", flush=True)


if __name__ == "__main__":
    main()
