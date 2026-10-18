import re
import time

from app.guardrail.db import get_connection
from app.guardrail.engine import run_query
from app.guardrail.validator import validate

# A typical naive blacklist
BLACKLIST = re.compile(
    r"\b(drop|delete|update|insert|alter|truncate|create|grant|revoke|copy)\b",
    re.IGNORECASE,
)


def _ms(start):
    return (time.perf_counter() - start) * 1000


def no_guardrail(sql):
    """Every LLM query goes straight to the database (analytical baseline: never stops anything)."""
    return False, 0.0


def regex_blacklist(sql):
    start = time.perf_counter()
    flagged = bool(BLACKLIST.search(sql))
    return flagged, _ms(start)


def db_role_only(sql):
    """Only PostgreSQL permissions (restricted role, read-only, 5s timeout) protect the database."""
    start = time.perf_counter()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        if cur.description:
            cur.fetchall()
        flagged = False  # the query ran to completion
    except Exception:
        flagged = True   # permission denied, read-only violation or timeout
    finally:
        conn.rollback()
        conn.close()
    return flagged, _ms(start)


def ast_only(sql):
    """SQLGlot validation and policy rules only (no cost estimation)."""
    start = time.perf_counter()
    flagged = validate(sql).blocked
    return flagged, _ms(start)


def full_guardrail(sql):
    """Validation + cost estimation + risk score + safe execution."""
    start = time.perf_counter()
    response = run_query(sql, execute=False)
    flagged = response.decision != "ALLOW"
    return flagged, _ms(start)


BASELINES = {
    "no_guardrail": no_guardrail,
    "regex_blacklist": regex_blacklist,
    "db_role_only": db_role_only,
    "ast_only": ast_only,
    "full_guardrail": full_guardrail,
}
