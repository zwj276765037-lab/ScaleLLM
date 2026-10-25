"""Durable, attempt-relative evidence for real device operations."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import threading


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()


class Evidence:
    def __init__(self, root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=False)
        self.lock=threading.RLock()
    def _path(self, rel):
        path=(self.root/rel).resolve();path.relative_to(self.root)
        path.parent.mkdir(parents=True,exist_ok=True);return path
    def write_bytes(self,rel,data):
        data=bytes(data);path=self._path(rel)
        with self.lock:
            if path.exists():raise FileExistsError(path)
            with open(path,'xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        return {'path':path.relative_to(self.root).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    def write_json(self,rel,value):
        return self.write_bytes(rel,(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode('utf-8'))
    def replace_json(self,rel,value):
        path=self._path(rel);tmp=path.with_suffix(path.suffix+'.tmp')
        with self.lock:
            with open(tmp,'w',encoding='utf-8') as f:json.dump(value,f,indent=2,sort_keys=True,ensure_ascii=False);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(tmp,path)
    def journal(self,event,details=None):
        value={'utc':utc(),'event':event,'details':details or {}}
        with self.lock:
            with open(self.root/'journal.jsonl','a',encoding='utf-8') as f:f.write(json.dumps(value,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())


def named(record,name):return {name+'_path':record['path'],name+'_sha256':record['sha256']}
