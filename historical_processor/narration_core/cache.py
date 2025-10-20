# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Optional


class NarrationCache:
    """Simple JSON file cache for generated texts (intro/transitions/grammar chunks).

    Key = sha256(JSON payload with prompt/template version + minimal context).
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        root = Path(os.environ.get("NC_OUTPUTS_ROOT", Path.cwd() / "outputs"))
        self.base_dir = base_dir or (root / ".cache" / "narration_core")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, payload: Dict[str, Any]) -> str:
        b = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return sha256(b).hexdigest()

    def load(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._key(payload)
        fp = self.base_dir / f"{key}.json"
        if not fp.exists():
            return None
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return None

    def save(self, payload: Dict[str, Any], data: Dict[str, Any]) -> str:
        key = self._key(payload)
        fp = self.base_dir / f"{key}.json"
        try:
            fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            # best-effort; ignore cache write errors
            pass
        return key
