"""Freeze clean document IDs and roles; JSONL is per document, never per scalar."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import traceback
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from run_numerical_fidelity import cpu_supervise, identity, write_json


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def canonical_url(url):
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def read_records(path):
    if path.suffix == ".parquet":
        import pyarrow as pa
        import pyarrow.parquet as pq
        pa.set_cpu_count(1)
        for batch in pq.ParquetFile(path).iter_batches(batch_size=128, columns=["text"], use_threads=False):
            yield from batch.to_pylist()
    else:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    yield json.loads(line)


def wikitext_articles(path):
    """Whole article boundaries, not blank/nonempty source rows."""
    parts, start = [], None
    for index, row in enumerate(read_records(path)):
        text = row.get("text", "")
        if re.fullmatch(r"\s*=\s+[^=]+?\s+=\s*", text):
            if parts:
                yield {"source_index": start, "text": "\n".join(parts)}
            parts, start = [text], index
        elif text.strip():
            if start is None:
                start = index
            parts.append(text)
    if parts:
        yield {"source_index": start, "text": "\n".join(parts)}


def freeze_documents(records, quotas, train_count, dev_count, seed, smoke_texts):
    """Exact normalized text + same-source URL clusters; no iid certification."""
    parent = list(range(len(records)))
    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    def union(first, second):
        first, second = find(first), find(second)
        if first != second:
            parent[second] = first
    by_text, by_url = {}, {}
    exposure = [normalized(text) for text in smoke_texts if normalized(text)]
    for index, row in enumerate(records):
        text = normalized(row["text"])
        row["text_sha256"] = digest(row["text"])
        row["normalized_text_sha256"] = digest(text)
        row["smoke_overlap"] = any(fragment in text for fragment in exposure)
        for lookup, key in [(by_text, row["normalized_text_sha256"]), (by_url, row.get("canonical_url"))]:
            if key:
                if key in lookup:
                    union(index, lookup[key])
                else:
                    lookup[key] = index
    groups = {}
    for index in range(len(records)):
        groups.setdefault(find(index), []).append(index)
    representatives, inventory = [], {}
    excluded_clusters = 0
    for members in groups.values():
        exposed = any(records[index]["smoke_overlap"] for index in members)
        if exposed:
            excluded_clusters += 1
        chosen = min(members, key=lambda index: digest(f"{seed}:{records[index]['doc_id']}"))
        row = dict(records[chosen])
        row["duplicate_cluster"] = digest("\n".join(sorted(records[index]["doc_id"] for index in members)))
        row["duplicate_cluster_members"] = [records[index]["doc_id"] for index in members]
        inventory.setdefault(row["domain"], {"unique_clusters": 0, "clean_clusters": 0})
        inventory[row["domain"]]["unique_clusters"] += 1
        inventory[row["domain"]]["clean_clusters"] += int(not exposed)
        if not exposed:
            representatives.append(row)
    selected = []
    for domain, count in quotas.items():
        candidates = sorted((row for row in representatives if row["domain"] == domain and row["source_split"] != "train"),
                            key=lambda row: digest(f"{seed}:eval:{row['doc_id']}"))
        if len(candidates) < count:
            raise ValueError(f"insufficient actual clean clusters in {domain}: {len(candidates)} < {count}")
        selected += [{**row, "split": "eval", "evidence_role": "formal_eval", "selection_probability": count / len(candidates)}
                     for row in candidates[:count]]
    training = sorted((row for row in representatives if row["source_split"] == "train"),
                      key=lambda row: digest(f"{seed}:train_dev:{row['doc_id']}"))
    if len(training) < train_count + dev_count:
        raise ValueError("insufficient unexposed train articles for disjoint train/dev")
    for split, pool in [("train", training[:train_count]), ("dev", training[train_count:train_count + dev_count])]:
        selected += [{**row, "split": split, "evidence_role": "calibration" if split == "train" else "development",
                      "selection_probability": (train_count if split == "train" else dev_count) / len(training),
                      "train_dev_pool_selection_probability": (train_count + dev_count) / len(training)} for row in pool]
    if len({row["duplicate_cluster"] for row in selected}) != len(selected):
        raise AssertionError("cluster leakage across frozen roles")
    return selected, {"source_rows": len(records), "unique_clusters": len(groups),
                       "excluded_smoke_clusters": excluded_clusters, "by_domain": inventory,
                       "deduplication": "NFC/whitespace exact text + canonical URL; semantic near-duplicate independence not certified"}


def prepare_worker(args):
    root = args.data_root.resolve()
    sources = [("c4_official_validation_first10000", "web", "validation", root / "bape_eval/raw/c4_official/validation_first10000.jsonl"),
               ("ag_news_test", "news", "test", root / "bape_eval/raw/ag_news/test.parquet"),
               ("imdb_test", "reviews", "test", root / "bape_eval/raw/imdb/test.parquet"),
               ("wikitext2_train", "wikipedia", "train", root / "wikitext-2-raw-v1/train-00000-of-00001.jsonl")]
    identities = {name: identity(path) for name, _, _, path in sources}
    smoke_paths = [root / f"calibration/{name}.jsonl" for name in ["first64", "first128"]]
    smoke = [row["text"] for path in smoke_paths for row in read_records(path) if isinstance(row.get("text"), str)]
    rows = []
    for asset, domain, split, path in sources:
        iterator = wikitext_articles(path) if split == "train" else read_records(path)
        for position, row in enumerate(iterator):
            text = row.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            source_index = row.get("source_index", position)
            rows.append({"doc_id": f"{asset}:{source_index}", "source_id": str(source_index),
                         "source_asset": asset, "domain": domain, "source_split": split,
                         "canonical_url": canonical_url(row["url"]) if row.get("url") else None,
                         "source_file": identities[asset], "text": text})
    selected, inventory = freeze_documents(rows, {"web": args.web, "news": args.news, "reviews": args.reviews},
                                          args.train_documents, args.dev_documents, args.seed, smoke)
    files = {}
    for split in ["train", "dev", "eval"]:
        path = args.output_dir / f"documents_{split}.jsonl"
        with path.open("x", encoding="utf-8") as stream:
            for row in selected:
                if row["split"] == split:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        files[split] = {**identity(path), "documents": sum(row["split"] == split for row in selected)}
    result = {"schema": "m005_clean_document_manifest_v1", "seed": args.seed,
              "inventory": inventory, "files": files, "sources": identities,
              "excluded_engineering_smoke_sources": [identity(path) for path in smoke_paths],
              "independent_unit": "operational unique document cluster; not token/tensor/scalar",
              "train_dev_disjoint": True, "train_dev_domains": ["wikipedia"],
              "development_domain_limitation": "train/dev are out-of-domain for web/news/reviews; no claim of matched-domain nuisance variance",
              "evaluation_domain_counts": {domain: sum(row["split"] == "eval" and row["domain"] == domain for row in selected)
                                           for domain in ["web", "news", "reviews"]},
              "calibration_performed": False, "model_inference_performed": False,
              "historical_source_exposure": "full corpus prior-use not certified; old smoke text/containing documents excluded; no claim of previously unseen benchmark"}
    write_json(args.output_dir / "document_manifest.json", result)
    print(json.dumps({"files": files, "inventory": inventory}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2026101903)
    parser.add_argument("--web", type=int, default=512)
    parser.add_argument("--news", type=int, default=256)
    parser.add_argument("--reviews", type=int, default=256)
    parser.add_argument("--train-documents", type=int, default=64)
    parser.add_argument("--dev-documents", type=int, default=64)
    parser.add_argument("--wall-seconds", type=int, default=300)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    try:
        code = prepare_worker(args) if args.worker else cpu_supervise(args, __file__, "prepare")
    except Exception:
        traceback.print_exc()
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
