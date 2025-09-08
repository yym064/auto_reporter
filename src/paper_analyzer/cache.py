import hashlib
import json
import os
from typing import Any, Dict, Optional


class JsonlCache:
    def __init__(self, cache_dir: str) -> None:
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, "lm_cache.jsonl")
        self.mem: Dict[str, Any] = {}
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                        self.mem[row["key"]] = row["value"]
                    except Exception:
                        continue

    @staticmethod
    def make_key(payload: Dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def get(self, payload: Dict[str, Any]) -> Optional[Any]:
        key = self.make_key(payload)
        return self.mem.get(key)

    def set(self, payload: Dict[str, Any], value: Any) -> None:
        key = self.make_key(payload)
        self.mem[key] = value
        with open(self.cache_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")

