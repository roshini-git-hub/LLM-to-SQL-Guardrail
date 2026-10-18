import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.guardrail.models import ValidationResult
from app.guardrail import policy


def validate(sql: str) -> ValidationResult:
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

    # 4. Look for write or DDL nodes hidden inside (e.g. CTEs)
    for node_type in (exp.Insert, exp.Update, exp.Delete, exp.Drop,
                      exp.Create, exp.Alter, exp.Command):
        if tree.find(node_type):
            result.add("hidden_write", "block",
                       f"Found {node_type.__name__} inside the query")

    # 5. Tables
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in cte_names:
            continue
        if name in policy.BLOCKED_TABLES:
            result.add("blocked_table", "block", f"Table '{name}' is not allowed")
        elif name not in policy.ALLOWED_SCHEMA:
            result.add("unknown_table", "block", f"Table '{name}' is not in the schema")

    # 6. Columns
    for col in tree.find_all(exp.Column):
        cname = col.name.lower()
        if cname in policy.SENSITIVE_COLUMNS:
            result.add("sensitive_column", "block", f"Column '{cname}' is restricted")

    # 7. SELECT * is flagged because it would expose restricted columns
    if tree.find(exp.Star):
        in_count = any(isinstance(s.parent, exp.Count) for s in tree.find_all(exp.Star))
        if not in_count:
            result.add("select_star", "warn", "SELECT * may expose restricted columns")

    # 8. Functions: only allowlisted ones
    for func in tree.find_all(exp.Func):
        if isinstance(func, (exp.Column, exp.Table)):
            continue
        fname = func.sql_name().lower()
        builtin_ok = fname in policy.ALLOWED_FUNCTIONS
        if not builtin_ok and isinstance(func, exp.Anonymous):
            fname = func.name.lower()
            builtin_ok = fname in policy.ALLOWED_FUNCTIONS
        if not builtin_ok:
            result.add("forbidden_function", "block", f"Function '{fname}' is not allowed")

    # 9. Missing LIMIT
    if isinstance(tree, exp.Select) and not tree.args.get("limit"):
        has_agg = tree.find(exp.AggFunc) is not None
        if not has_agg:
            result.add("missing_limit", "warn", "No LIMIT on a non-aggregate query")

    return result