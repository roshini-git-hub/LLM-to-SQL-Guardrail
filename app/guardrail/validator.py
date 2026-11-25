import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from typing import Optional

from app.guardrail import policy
from app.guardrail.models import ValidationResult
from app.guardrail.schema_loader import SYSTEM_SCHEMAS, SchemaSnapshot, get_snapshot

# SQL syntax that SQLGlot represents as "functions" but that is not a function call
SYNTAX_NODES = (
    exp.Column, exp.Table, exp.Connector,
    exp.Case, exp.If, exp.Cast, exp.TryCast,
)


def validate(sql: str, snapshot: Optional[SchemaSnapshot] = None) -> ValidationResult:
    """Check one SQL string against generic rules and the role's live schema snapshot."""
    if snapshot is None:
        snapshot = get_snapshot()
    result = ValidationResult(sql=sql)

    # 1. Parse into an AST (syntax check)
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except ParseError as e:
        result.add("syntax_error", "block", f"Could not parse SQL: {str(e)[:150]}")
        return result

    statements = [s for s in statements if s is not None]

    # 2. Exactly one statement (stops stacked queries)
    if len(statements) != 1:
        result.add("multiple_statements", "block",
                   f"Expected 1 statement, found {len(statements)}")
        return result

    tree = statements[0]

    # 3. Only SELECT allowed
    if not isinstance(tree, (exp.Select, exp.Union, exp.Subquery)):
        result.add("forbidden_statement", "block",
                   f"Only SELECT is allowed, got {type(tree).__name__}")
        return result

    # 4. Write or DDL nodes hidden inside (e.g. in CTEs)
    for node_type in (exp.Insert, exp.Update, exp.Delete, exp.Drop,
                      exp.Create, exp.Alter, exp.Command):
        if tree.find(node_type):
            result.add("hidden_write", "block",
                       f"Found {node_type.__name__} inside the query")

    # 4b. Row locking and SELECT INTO are not read-only operations
    if tree.find(exp.Lock):
        result.add("row_locking", "block", "FOR UPDATE / FOR SHARE is not allowed")
    if tree.find(exp.Into):
        result.add("select_into", "block", "SELECT INTO is not allowed")

    # 5. Tables: decided by what the role may read, as reported by the database
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    used = {}                      # alias or name -> Table from the snapshot
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        schema = (table.db or "").lower()
        if not name or (not schema and name in cte_names):
            continue
        known = snapshot.table(name)
        system = (schema in SYSTEM_SCHEMAS or schema.startswith("pg_")
                  or (not schema and name.startswith("pg_")))
        if system or (schema and (known is None or known.schema.lower() != schema)):
            label = f"{schema}.{name}" if schema else name
            result.add("unknown_table", "block", f"Table '{label}' is not in the allowed schema")
        elif known is None:
            result.add("table_not_found", "block", f"Table '{name}' does not exist")
        elif not known.accessible:
            result.add("blocked_table", "block",
                       f"Table '{name}' is not allowed for role '{snapshot.role}'")
        else:
            used[table.alias_or_name.lower()] = known
            used[name] = known
    used_tables = {t.name.lower(): t for t in used.values()}

    # 6. Columns: hidden (no GRANT) -> block; sensitive but granted -> warn; missing -> fixable
    simple_scope = not cte_names and tree.find(exp.Subquery) is None and isinstance(tree, exp.Select)
    select_aliases = {a.alias.lower() for a in tree.find_all(exp.Alias)}
    reported = set()
    for col in tree.find_all(exp.Column):
        if isinstance(col.this, exp.Star) or not col.name:
            continue
        cname = col.name.lower()
        qual = (col.table or "").lower()
        if qual and qual in used:
            candidates = [used[qual]]
        else:
            candidates = list(used_tables.values())
        found = [t.column(cname) for t in candidates if t.column(cname)]

        if found and not any(c.can_select for c in found):
            if ("hidden", cname) not in reported:
                reported.add(("hidden", cname))
                result.add("sensitive_column", "block",
                           f"Column '{cname}' is restricted for role '{snapshot.role}'")
        elif any(c.can_select and c.sensitive for c in found):
            if ("pii", cname) not in reported:
                reported.add(("pii", cname))
                result.add("sensitive_access", "warn",
                           f"Column '{cname}' holds personal or sensitive data")
        elif (not found and simple_scope and candidates and cname not in select_aliases
              and (not qual or qual in used)):
            where = (f"table '{used[qual].name}'" if qual
                     else "tables " + ", ".join(sorted(used_tables)))
            result.add("column_not_found", "block", f"Column '{cname}' does not exist in {where}")

    # 7. Star expansion: * on a table with hidden columns would expose them
    stars = [s for s in tree.find_all(exp.Star) if not isinstance(s.parent, exp.Count)]
    if stars:
        restricted = sorted(n for n, t in used_tables.items() if t.hidden_columns)
        if restricted:
            result.add("star_on_restricted_table", "block",
                       f"SELECT * would expose restricted columns of: {', '.join(restricted)}")
        else:
            result.add("select_star", "warn", "SELECT * returns every column")
            pii = sorted(n for n, t in used_tables.items()
                         if any(c.sensitive for c in t.visible_columns))
            if pii:
                result.add("sensitive_access", "warn",
                           f"SELECT * includes personal or sensitive columns of: {', '.join(pii)}")

    # 8. Functions: only allowlisted ones
    for func in tree.find_all(exp.Func):
        if isinstance(func, SYNTAX_NODES):
            continue
        fname = func.sql_name().lower()
        ok = fname in policy.ALLOWED_FUNCTIONS
        if not ok and isinstance(func, exp.Anonymous):
            fname = func.name.lower()
            ok = fname in policy.ALLOWED_FUNCTIONS
        if not ok:
            result.add("forbidden_function", "block", f"Function '{fname}' is not allowed")

    # 9. Missing LIMIT
    if isinstance(tree, exp.Select) and not tree.args.get("limit"):
        if tree.find(exp.AggFunc) is None:
            result.add("missing_limit", "warn", "No LIMIT on a non-aggregate query")

    # 10. Recursive CTEs can run without end (policy: not allowed for this role)
    for w in tree.find_all(exp.With):
        if w.args.get("recursive"):
            result.add("recursive_cte", "block", "Recursive queries are not allowed")
            break

    return result
