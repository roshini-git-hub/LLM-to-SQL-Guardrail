"""Turns a rejected query into precise, database-aware feedback for the LLM.

Two tools, both driven by the role's SchemaSnapshot (so nothing hidden is ever revealed):
  1. fix_dialect(): rewrite MySQL / SQL Server syntax into PostgreSQL with SQLGlot, no LLM call.
  2. build_feedback(): replace vague errors ("column does not exist") with the real column
     list, the closest valid names (difflib) and the foreign-key join conditions.
"""
import difflib
import re
from typing import List, Optional

import sqlglot
from sqlglot import exp

from app.guardrail import policy
from app.guardrail.schema_loader import SchemaSnapshot, Table

_TSQL_SIGNS = re.compile(r"\bTOP\s+\d|\[\w+\]|\bGETDATE\b|\bISNULL\s*\(|\bLEN\s*\(|\bDATEADD\b",
                         re.IGNORECASE)


# ---- 1. Dialect mistakes ----------------------------------------------------------------------

def fix_dialect(sql: str) -> List[str]:
    """PostgreSQL rewrites of `sql` read as another dialect (most likely dialect first).

    Returns only rewrites that differ from the original, e.g.
      SELECT TOP 5 `name`, IFNULL(city, '-') ...  ->  SELECT "name", COALESCE(city, '-') ... LIMIT 5
    The caller must send every rewrite through the full guardrail again.
    """
    def normal(text):
        return " ".join(text.lower().rstrip("; \n").split())

    order = ["tsql", "mysql"] if _TSQL_SIGNS.search(sql) else ["mysql", "tsql"]
    out = []
    for dialect in ["postgres"] + order:   # SQLGlot's postgres reader already maps e.g. IFNULL
        try:
            statements = sqlglot.transpile(sql, read=dialect, write="postgres")
        except Exception:
            continue
        if len(statements) == 1 and normal(statements[0]) != normal(sql) \
                and statements[0] not in out:
            out.append(statements[0])
    return out


# ---- 2. Schema-aware feedback -----------------------------------------------------------------

def _closest(name: str, options: List[str]) -> List[str]:
    return difflib.get_close_matches(name.lower(), [o.lower() for o in options], n=3, cutoff=0.5)


def _tables_used(sql: str, snapshot: SchemaSnapshot) -> List[Table]:
    """Readable tables mentioned in the query (falls back to word matching if it cannot parse)."""
    names = []
    try:
        for t in sqlglot.parse_one(sql, read="postgres").find_all(exp.Table):
            names.append(t.name.lower())
    except Exception:
        names = re.findall(r"\w+", sql.lower())
    seen, out = set(), []
    for n in names:
        table = snapshot.table(n)
        if table and table.accessible and table.name not in seen:
            seen.add(table.name)
            out.append(table)
    return out


def _columns(table: Table) -> str:
    return ", ".join(c.name for c in table.visible_columns)   # never lists hidden columns


def _join_hints(tables: List[Table], snapshot: SchemaSnapshot) -> List[str]:
    names = {t.name for t in tables}
    return [f"{fk.table} joins {fk.ref_table} on {fk.describe()}."
            for fk in snapshot.usable_foreign_keys()
            if fk.table in names and fk.ref_table in names]


def _column_feedback(column: str, used: List[Table], snapshot: SchemaSnapshot) -> str:
    scope = used or snapshot.accessible_tables()
    parts = []
    for t in scope:
        parts.append(f"Column {column} does not exist in {t.name}. Available: {_columns(t)}.")
    close = _closest(column, [c.name for t in scope for c in t.visible_columns])
    if close:
        parts.append("Did you mean: " + ", ".join(close) + "?")
    else:
        elsewhere = [t.name for t in snapshot.accessible_tables()
                     if t not in scope and t.column(column) and t.column(column).can_select]
        if elsewhere:
            parts.append(f"A column named {column} exists in: {', '.join(elsewhere)} "
                         "(join that table).")
    return " ".join(parts)


def _table_feedback(table: str, snapshot: SchemaSnapshot) -> str:
    names = sorted(t.name for t in snapshot.accessible_tables())
    msg = f"Table {table} does not exist. Available tables: {', '.join(names)}."
    close = _closest(table, names)
    if close:
        msg += " Did you mean: " + ", ".join(close) + "?"
    return msg


def build_feedback(sql: str, reasons: List[str], snapshot: SchemaSnapshot) -> List[str]:
    """One precise, actionable line per problem, plus join conditions for the tables used."""
    used = _tables_used(sql, snapshot)
    feedback = []

    for reason in reasons:
        col = (re.search(r"\[column_not_found\] Column '([^']+)'", reason)
               or re.search(r'column "?([\w.]+)"? does not exist', reason))
        tab = (re.search(r"\[table_not_found\] Table '([^']+)'", reason)
               or re.search(r'relation "([\w.]+)" does not exist', reason)
               or re.search(r'missing FROM-clause entry for table "(\w+)"', reason))

        if col:
            feedback.append(_column_feedback(col.group(1).split(".")[-1], used, snapshot))
        elif tab and "missing FROM-clause" in reason:
            feedback.append(f"{tab.group(1)} is used but not listed in FROM/JOIN. "
                            "Add it with a JOIN, or remove the reference.")
        elif tab:
            feedback.append(_table_feedback(tab.group(1).split(".")[-1], snapshot))
        elif "[syntax_error]" in reason:
            feedback.append("The SQL could not be parsed. Use plain PostgreSQL syntax "
                            "(double quotes for identifiers, LIMIT n, COALESCE).")
        elif "[missing_limit]" in reason:
            feedback.append(f"Add LIMIT (at most {policy.MAX_LIMIT}) at the end of the query.")
        elif "[select_star]" in reason:
            cols = "; ".join(f"{t.name}: {_columns(t)}" for t in used)
            feedback.append(f"Do not use SELECT *. Name the columns you need ({cols}).")
        elif "cartesian" in reason:
            feedback.append("Two tables are joined without a condition. "
                            "Every JOIN needs an ON condition.")
        elif "sequential scan" in reason or "estimated cost" in reason or "Plan step" in reason:
            feedback.append("The query is too expensive: " + reason +
                            ". Add a WHERE filter, aggregate, or a smaller LIMIT.")
        elif "function" in reason and "does not exist" in reason:
            feedback.append(reason + ". Use a standard PostgreSQL function instead "
                            "(e.g. COALESCE, EXTRACT, DATE_TRUNC, ROUND).")
        else:
            feedback.append(re.sub(r"^\[\w+\]\s*", "", reason))

    feedback.extend(_join_hints(used, snapshot))
    return feedback
