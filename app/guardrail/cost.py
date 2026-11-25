import json
from dataclasses import dataclass, field
from typing import List, Optional

from app.guardrail import policy
from app.guardrail.db import connection
from app.guardrail.schema_loader import SchemaSnapshot


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


def explain(sql: str, role: Optional[str] = None) -> dict:
    """EXPLAIN only: the planner estimates the plan, nothing is executed."""
    with connection(role) as conn:
        cur = conn.cursor()
        cur.execute("EXPLAIN (FORMAT JSON) " + sql)
        raw = cur.fetchone()[0]
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw[0]["Plan"]


def analyse_plan(root: dict, snapshot: SchemaSnapshot) -> CostEstimate:
    nodes = []
    _walk(root, nodes)

    biggest = snapshot.largest_table_rows
    huge_rows = max(policy.HUGE_ROWS_FLOOR, policy.HUGE_ROWS_FACTOR * biggest)

    warnings = []
    for n in nodes:
        node_type = n["Node Type"]
        rows = n.get("Plan Rows", 0)

        if node_type == "Seq Scan":
            table = snapshot.table(n.get("Relation Name", ""))
            table_rows = table.rows if table else 0
            reads_most_of_big_table = (
                table_rows >= policy.SEQ_SCAN_MIN_TABLE_ROWS
                and rows >= policy.SEQ_SCAN_FRACTION * table_rows
                and rows >= policy.SEQ_SCAN_ROWS
            )
            if reads_most_of_big_table:
                warnings.append(
                    f"Large sequential scan on '{n.get('Relation Name')}' "
                    f"(~{rows} of ~{table_rows} rows)"
                )

        if node_type == "Nested Loop" and rows >= policy.CARTESIAN_MIN_ROWS:
            has_condition = "Join Filter" in n or _descendants_have(n, "Index Cond")
            if not has_condition:
                warnings.append("Possible cartesian product (join without a condition)")

    max_rows = max(n.get("Plan Rows", 0) for n in nodes)
    if max_rows >= huge_rows:
        warnings.append(f"Plan step estimated at ~{max_rows} rows "
                        f"(biggest table has ~{biggest})")

    return CostEstimate(
        root_cost=root["Total Cost"],
        max_cost=max(n["Total Cost"] for n in nodes),
        max_rows=max_rows,
        node_types=[n["Node Type"] for n in nodes],
        warnings=warnings,
    )


def estimate_cost(sql: str, snapshot: SchemaSnapshot, role: Optional[str] = None) -> CostEstimate:
    return analyse_plan(explain(sql, role), snapshot)
