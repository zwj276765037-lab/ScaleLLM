"""Create four fresh sidebar chats, with no inherited history or agent binding."""
import argparse
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, "/home/zwj/.codex/skills/research-agent/scripts")
from codex_rpc import CodexRpc

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = ROOT / ".research-agent/fresh_section_chats.json"
SECTION = "01a11e1e-67eb-73e0-a08e-771bc0ee8bea"


def save(data):
    RECEIPT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "verify"))
    args = parser.parse_args()
    prior = json.loads((ROOT / ".research-agent/chat_setup_receipt.json").read_text())
    data = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {
        "request": "取消绑定；在ScaleLLM分区新建四个独立对话。",
        "root": str(ROOT), "section_id": SECTION, "project_binding": None,
        "agent_binding": False, "threads": {}, "cancelled_entries": {},
    }
    with CodexRpc(timeout=30) as rpc:
        config = rpc.request("config/read", {"includeLayers": False})["config"]
        if "official_http" not in config.get("model_providers", {}):
            raise RuntimeError("official_http must exist in persistent user config before creating or verifying chats")
        if args.action == "create":
            archived = rpc.request("thread/list", {
                "cwd": str(ROOT), "archived": True, "modelProviders": [], "limit": 100,
            })
            assert not archived.get("nextCursor")
            archived_ids = {t["id"] for t in archived["data"]}
            for old in prior["threads"].values():
                for tid in (old["id"], old.get("replaces_archived_id")):
                    if not tid or tid in data["cancelled_entries"]:
                        continue
                    observed = rpc.request("thread/read", {"threadId": tid})["thread"]
                    if observed["status"]["type"] not in ("idle", "notLoaded"):
                        raise RuntimeError("Do not archive an active chat: " + tid)
                    rpc.request("thread/metadata/update", {"threadId": tid, "projectId": ""})
                    rpc.request("thread/section/move", {"threadId": tid, "sectionId": None})
                    if tid not in archived_ids:
                        rpc.request("thread/archive", {"threadId": tid})
                    data["cancelled_entries"][tid] = {"archived": True, "project_id": None, "section_id": None}
                    save(data)
            for role, old in prior["threads"].items():
                if role in data["threads"]:
                    continue
                requested = old.get("requested") or {}
                model = requested.get("model") or old["readback"]["model"]
                effort = requested.get("effort")
                config = {}
                if effort:
                    config["model_reasoning_effort"] = effort
                result = rpc.request("thread/start", {
                    "cwd": str(ROOT), "model": model, "modelProvider": "official_http",
                    "config": config, "threadSource": "user",
                    "approvalPolicy": "never", "permissions": ":danger-full-access",
                })
                thread = result["thread"]
                assert thread.get("forkedFromId") is None
                assert thread.get("parentThreadId") is None
                record = {"id": thread["id"], "title": old["title"], "created": result}
                data["threads"][role] = record
                save(data)
                rpc.request("thread/name/set", {"threadId": thread["id"], "name": old["title"]})
                rpc.request("thread/section/move", {
                    "threadId": thread["id"], "sectionId": SECTION,
                    "beforeThreadId": prior["preserved_historical_threads"][0],
                })
                params = {"threadId": thread["id"], "model": model,
                          "clientUserMessageId": str(uuid.uuid4()), "input": [{
                              "type": "text",
                              "text": "你是ScaleLLM的“" + old["title"] + "”独立对话。工作目录为 /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM。这是全新对话，不继承旧会话，不绑定旧代理。本轮仅建立入口；不要调用工具、读取文件、发送消息或执行任何工程任务。只回复“已就绪，等待你的指令。”",
                          }]}
                if effort:
                    params["effort"] = effort
                record["initialization"] = rpc.request("turn/start", params)
                save(data)
                print(json.dumps({"role": role, "id": thread["id"], "fresh": True}), flush=True)
        else:
            listed = rpc.request("thread/list", {"sectionId": SECTION, "limit": 100})
            ids = {t["id"] for t in listed["data"]}
            assert not listed.get("nextCursor")
            assert all(t in ids for t in prior["preserved_historical_threads"])
            assert not ids.intersection(data["cancelled_entries"])
            for record in data["threads"].values():
                tid = record["id"]
                assert tid in ids
                rpc.request("thread/name/set", {"threadId": tid, "name": record["title"]})
                observed = rpc.request("thread/read", {"threadId": tid})["thread"]
                turns = rpc.request("thread/turns/list", {"threadId": tid, "limit": 2, "itemsView": "full"})
                assert observed.get("forkedFromId") is None
                assert observed.get("parentThreadId") is None
                assert observed.get("projectId") is None
                assert observed["cwd"] == str(ROOT)
                assert observed["section"]["id"] == SECTION
                assert len(turns["data"]) == 1 and not turns.get("nextCursor")
                assert turns["data"][0]["status"] == "completed"
                assert not turns["data"][0].get("error")
                assert observed["status"]["type"] in ("idle", "notLoaded")
                created = record["created"]
                resumed = rpc.request("thread/resume", {
                    "threadId": tid, "excludeTurns": True,
                    "model": created["model"], "modelProvider": created["modelProvider"],
                })
                rpc.request("thread/settings/update", {
                    "threadId": tid, "model": created["model"],
                    "effort": created["reasoningEffort"],
                })
                assert resumed["modelProvider"] == "official_http"
                assert resumed["model"] == created["model"]
                assert resumed["approvalPolicy"] == "never"
                assert resumed["sandbox"]["type"] == "dangerFullAccess"
                record["persistent_provider_resume"] = {
                    "passed": True, "temporary_config_supplied": False,
                    "model": resumed["model"], "provider": resumed["modelProvider"],
                    "requested_effort_restored": created["reasoningEffort"],
                }
                record["verified"] = {"thread": observed, "turns": turns}
            assert len(data["threads"]) == 4
            data["status"] = "verified_four_fresh_unbound_section_chats"
            data["section_readback"] = listed
            save(data)
            print(json.dumps({"status": data["status"], "threads": {
                r: {"id": t["id"], "title": t["title"]} for r, t in data["threads"].items()
            }}, ensure_ascii=False))


if __name__ == "__main__":
    main()
