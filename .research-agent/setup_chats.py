"""Create only the four requested read-only project chats via Codex's API."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, "/home/zwj/.codex/skills/research-agent/scripts")
from codex_rpc import CodexRpc
from repair_chat_visibility import PROVIDER

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = ROOT / ".research-agent/chat_setup_receipt.json"


def save(data):
    RECEIPT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main():
    if (ROOT / ".research-agent/fresh_section_chats.json").exists():
        raise SystemExit("Prior bindings cancelled by user; use new_section_chats.py verify for current entries.")
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("create", "inspect", "bind"))
    args = parser.parse_args()
    plan = json.loads((ROOT / ".research-agent/codex_workspace.json").read_text())
    data = json.loads(RECEIPT.read_text()) if RECEIPT.exists() else {
        "root": str(ROOT), "transport": "existing_codex_app_server_control_socket",
        "section_status": "unavailable_native_sidebar_tools", "project_id": None,
        "host_id": None, "threads": {}, "errors": [],
    }
    with CodexRpc(timeout=30) as rpc:
        if args.action == "create":
            existing = rpc.request("thread/list", {
                "cwd": str(ROOT), "limit": 100,
                "sourceKinds": ["cli", "vscode", "appServer", "exec"],
                "modelProviders": [],
            })
            if existing.get("nextCursor"):
                raise RuntimeError("Thread list incomplete; do not create duplicates")
            known = {v["id"] for v in data["threads"].values()}
            if any(t["id"] not in known for t in existing["data"]):
                raise RuntimeError("Unbound existing project thread requires inspection")
            for role, slot in plan["slots"].items():
                if role in data["threads"]:
                    continue
                requested = slot.get("requested") or {}
                params = {"cwd": str(ROOT), "approvalPolicy": "never",
                          "permissions": ":danger-full-access",
                          "threadSource": "user", "modelProvider": "official_http",
                          "config": {"model_providers": {"official_http": PROVIDER}}}
                if requested.get("model"):
                    params["model"] = requested["model"]
                result = rpc.request("thread/start", params)
                tid = result["thread"]["id"]
                record = {"id": tid, "title": slot["title"], "requested": requested,
                          "created_response": result}
                data["threads"][role] = record
                save(data)
                rpc.request("thread/name/set", {"threadId": tid, "name": slot["title"]})
                record["settings_update"] = rpc.request("thread/settings/update", {
                    "threadId": tid, "approvalPolicy": "never",
                    "permissions": ":danger-full-access",
                })
                turn = {"threadId": tid, "input": [{"type": "text", "text": slot["prompt"] +
                    "\n补充：工程正在复制，本轮只核对已存在的管理文件。不要轮询复制进度。"
                    "四对话通过原生 app-server 创建；侧栏工具未开放，禁止自行创建分区或修改应用数据库。"
                    "用一句话确认已读取的项目根、职责和等待状态后结束。"}]}
                if requested:
                    turn.update(model=requested["model"], effort=requested["effort"])
                record["initialization"] = rpc.request("turn/start", turn)
                save(data)
        if args.action == "bind":
            projects = rpc.request("project/list", {"limit": 100})
            sections = rpc.request("threadSection/list", {"limit": 100})
            if projects.get("nextCursor") or sections.get("nextCursor"):
                raise RuntimeError("Incomplete project/section listing")
            matching = [p for p in projects["data"] if p["name"] == "ScaleLLM"]
            if len(matching) > 1 or (matching and matching[0]["roots"] != [{"path": str(ROOT)}]):
                raise RuntimeError("Existing project needs explicit reconciliation")
            project = matching[0] if matching else rpc.request("project/create", {
                "idempotencyKey": "scalellm-clean-migration-20261014", "name": "ScaleLLM",
                "roots": [{"path": str(ROOT)}],
            })["project"]
            matching = [s for s in sections["data"] if s["name"] == "ScaleLLM"]
            if len(matching) > 1:
                raise RuntimeError("Duplicate existing ScaleLLM sections")
            section = matching[0] if matching else rpc.request("threadSection/create", {"name": "ScaleLLM"})["section"]
            before = rpc.request("thread/list", {"sectionId": section["id"], "limit": 100})
            if before.get("nextCursor"):
                raise RuntimeError("Incomplete section membership")
            current_ids = {t["id"] for t in data["threads"].values()}
            historical = [t["id"] for t in before["data"] if t["id"] not in current_ids]
            data.update(project_id=project["id"], section=section,
                        preserved_historical_threads=historical)
            save(data)
            for record in data["threads"].values():
                rpc.request("thread/metadata/update", {"threadId": record["id"], "projectId": project["id"]})
                rpc.request("thread/section/move", {"threadId": record["id"], "sectionId": section["id"],
                    "beforeThreadId": historical[0] if historical else None})
            data["project_readback"] = rpc.request("project/read", {"projectId": project["id"]})
            data["section_members_readback"] = rpc.request("thread/list", {"sectionId": section["id"], "limit": 100})
        for role, record in data["threads"].items():
            requested = record.get("requested") or {}
            config = {"model_providers": {"official_http": PROVIDER}}
            if requested.get("effort"):
                config["model_reasoning_effort"] = requested["effort"]
            result = rpc.request("thread/resume", {
                "threadId": record["id"], "excludeTurns": True,
                "model": requested.get("model") or record.get("readback", record["created_response"])["model"],
                "modelProvider": "official_http", "config": config,
            })
            if result["thread"]["cwd"] != str(ROOT):
                raise RuntimeError("Wrong working directory for " + role)
            record["readback"] = result
            record["turns"] = rpc.request("thread/turns/list", {
                "threadId": record["id"], "limit": 3, "itemsView": "full",
            })
            rpc.request("thread/name/set", {"threadId": record["id"], "name": record["title"]})
            record["title_readback"] = rpc.request("thread/read", {"threadId": record["id"]})
            save(data)
        if args.action != "create":
            listed = rpc.request("thread/list", {"cwd": str(ROOT), "limit": 100})
            expected = {r["id"] for r in data["threads"].values()}
            actual = {t["id"] for t in listed["data"]}
            if expected != actual or listed.get("nextCursor"):
                raise RuntimeError("Ordinary project listing differs from the four bound entries")
            data["default_cwd_list"] = listed
            save(data)
        if args.action == "bind":
            binding = {"project_name": "ScaleLLM", "root": str(ROOT),
                "section_name": data["section"]["name"], "section_id": data["section"]["id"],
                "host_id": "local", "project_id": data["project_id"], "threads": {}}
            for role, record in data["threads"].items():
                observed = record["title_readback"]["thread"]
                envs = observed["environments"]
                assert envs[0]["environmentId"] == "local"
                assert observed["projectId"] == data["project_id"]
                assert observed["section"]["id"] == data["section"]["id"]
                assert observed["name"] == record["title"]
                assert record["readback"]["approvalPolicy"] == "never"
                assert record["readback"]["sandbox"]["type"] == "dangerFullAccess"
                assert record["readback"]["activePermissionProfile"]["id"] == ":danger-full-access"
                assert record["turns"]["data"][-1]["status"] == "completed"
                binding["threads"][role] = {"id": observed["id"], "title": observed["name"],
                    "cwd": observed["cwd"], "hostId": "local", "projectId": observed["projectId"]}
            (ROOT / ".research-agent/codex_binding_input.json").write_text(json.dumps(binding, ensure_ascii=False, indent=2) + "\n")
            data.update(section_status="verified", host_id="local")
            save(data)
        print(json.dumps({role: {"id": rec["id"], "title": rec["title"],
              "status": rec["readback"]["thread"].get("status"),
              "model": rec["readback"].get("model"),
              "effort": rec["readback"].get("reasoningEffort"),
              "approval": rec["readback"].get("approvalPolicy"),
              "sandbox": rec["readback"].get("sandbox"),
              "turn_statuses": [t.get("status") for t in rec["turns"].get("data", [])]}
              for role, rec in data["threads"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
