import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.guardrail import policy
from app.guardrail.models import ValidationResult

# SQL syntax that SQLGlot represents as "functions" but that is not a function call
SYNTAX_NODES = (
    exp.Column, exp.Table, exp.Connector,
    exp.Case, exp.If, exp.Cast, exp.TryCast,
)


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

    # 5. Tables
    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    used_tables = set()
    for table in tree.find_all(exp.Table):
        name = table.name.lower()
        if name in cte_names:
            continue
        used_tables.add(name)
        if name in policy.BLOCKED_TABLES:
            result.add("blocked_table", "block", f"Table '{name}' is not allowed")
        elif name not in policy.ALLOWED_SCHEMA:
            result.add("unknown_table", "block", f"Table '{name}' is not in the schema")

    # 6. Columns
    for col in tree.find_all(exp.Column):
        cname = col.name.lower()
        if cname in policy.SENSITIVE_COLUMNS:
            result.add("sensitive_column", "block", f"Column '{cname}' is restricted")

    # 7. Star expansion: * on a table with hidden columns would expose them
    stars = [s for s in tree.find_all(exp.Star) if not isinstance(s.parent, exp.Count)]
    if stars:
        restricted = used_tables & policy.TABLES_WITH_HIDDEN_COLUMNS
        if restricted:
            result.add("star_on_restricted_table", "block",
                       f"SELECT * would expose restricted columns of: {', '.join(sorted(restricted))}")
        else:
            result.add("select_star", "warn", "SELECT * returns every column")

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
