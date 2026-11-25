import json
import time
from pathlib import Path

LOG_PATH = Path("data") / "audit.jsonl"


def log_event(kind: str, question, response, repairs_used: int = 0, trail=None):
    LOG_PATH.parent.mkdir(exist_ok=True)
    record = {
        "ts": time.time(),
        "kind": kind,
        "role": getattr(response, "role", None),
        "question": question,
        "sql": response.sql,
        "decision": response.decision,
        "score": response.score,
        "reasons": response.reasons,
        "rows_returned": len(response.rows),
        "elapsed_ms": response.elapsed_ms,
        "repairs_used": repairs_used,
        "attempts": trail or [],   # every attempt of the repair loop, with the feedback sent
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
