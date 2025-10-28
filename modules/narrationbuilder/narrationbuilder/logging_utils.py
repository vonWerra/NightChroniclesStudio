from __future__ import annotations

import json
import sys
from typing import Any, Dict


def emit_evt(obj: Dict[str, Any]) -> None:
    """Emit NC_EVT line to stdout for GUI consumption."""
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = str(obj)
    sys.stdout.write(f"NC_EVT {s}\n")
    sys.stdout.flush()


def log_err(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()
