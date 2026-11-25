import json
from dataclasses import dataclass, field
from typing import List

from app.guardrail import policy
from app.guardrail.db import connection


@dataclass
class CostEstimate:
    root_cost: float
    max_cost: float
    max_rows: int
    node_types: List[str]
    warnings: List[str] = field(default_factory=list)


def _walk(node, out):
    out.append(node)
    for child in node.get("Plans", []):
        _walk(child, out)


def _descendants_have(node, key):
    for child in node.get("Plans", []):
        if key in child or _descendants_have(child, key):
            return True
    return False


def estimate_cost(sql: str) -> CostEstimate:
    with connection() as conn:
        cur = conn.cursor()
        cur.execute("EXPLAIN (FORMAT JSON) " + sql)
        raw = cur.fetchone()[0]
    if isinstance(raw, str):
        raw = json.loads(raw)
    root = raw[0]["Plan"]

    nodes = []
    _walk(root, nodes)

    warnings = []
    for n in nodes:
        node_type = n["Node Type"]
        rows = n.get("Plan Rows", 0)

        if node_type == "Seq Scan" and rows >= policy.SEQ_SCAN_ROWS:
            warnings.append(
                f"Large sequential scan on '{n.get('Relation Name')}' (~{rows} rows)"
            )

        if node_type == "Nested Loop" and rows >= policy.CARTESIAN_MIN_ROWS:
            has_condition = "Join Filter" in n or _descendants_have(n, "Index Cond")
            if not has_condition:
                warnings.append("Possible cartesian product (join without a condition)")

    max_rows = max(n.get("Plan Rows", 0) for n in nodes)
    if max_rows >= policy.HUGE_ROWS:
        warnings.append(f"Plan step estimated at ~{max_rows} rows")

    return CostEstimate(
        root_cost=root["Total Cost"],
        max_cost=max(n["Total Cost"] for n in nodes),
        max_rows=max_rows,
        node_types=[n["Node Type"] for n in nodes],
        warnings=warnings,
    )
