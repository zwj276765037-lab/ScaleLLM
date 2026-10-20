"""Small, strict JSON/identity helpers used only by the new assessment tools."""
import hashlib
import json
from pathlib import Path


def identity(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    return {"path": str(p), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_sha(value):
    return text_sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for n, line in enumerate(stream, 1):
            if line.strip():
                try:
                    row = json.loads(line, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                except ValueError as exc:
                    raise ValueError(f"{path}:{n}: invalid JSON: {exc}") from exc
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{n}: expected object")
                yield row


def write_json(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def write_jsonl(path, rows):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def index_unique(rows, key):
    result = {}
    for row in rows:
        k = key(row)
        if k in result:
            raise ValueError(f"duplicate key: {k}")
        result[k] = row
    return result
