"""Reads the database's own catalogs to learn what the CURRENT role may see and do.

Nothing about the schema is hard-coded. The guardrail asks PostgreSQL:
  - which tables and columns exist                      (pg_class, pg_attribute)
  - which of them this role may SELECT                  (has_column_privilege, has_schema_privilege)
  - how tables relate                                   (pg_constraint, foreign keys)
  - which row-level security policies apply             (pg_class.relrowsecurity, pg_policies)
  - how big the tables are                              (pg_class.reltuples, pg_stat_user_tables)
  - which columns are sensitive                         (column COMMENTs + name heuristics)

The result is a SchemaSnapshot, cached per role and refreshed when the schema changes
(see start_listener(): an event trigger sends NOTIFY, and we LISTEN for it).
"""
import re
import select
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from psycopg2 import sql

from app.guardrail import policy
from app.guardrail.db import connection, new_connection

SYSTEM_SCHEMAS = ("pg_catalog", "information_schema")

# Column names that look sensitive (used together with column COMMENTs containing pii/sensitive)
_SENSITIVE_SUBSTRINGS = (
    "email", "phone", "mobile", "salary", "wage", "aadhaar", "aadhar", "passport",
    "password", "passwd", "secret", "token", "api_key", "apikey", "credit_card",
    "card_number", "account_number", "birth",
)
_SENSITIVE_TOKENS = {"ssn", "pan", "dob", "cvv", "pwd", "iban", "pin"}
_COMMENT_PATTERN = re.compile(r"\b(pii|sensitive)\b", re.IGNORECASE)

_TEXT_TYPES = ("text", "character varying", "character", "citext")


def looks_sensitive(column: str, comment: Optional[str]) -> bool:
    if comment and _COMMENT_PATTERN.search(comment):
        return True
    name = column.lower()
    if any(s in name for s in _SENSITIVE_SUBSTRINGS):
        return True
    return bool(set(re.split(r"[^a-z0-9]+", name)) & _SENSITIVE_TOKENS)


@dataclass
class Column:
    name: str
    type: str
    can_select: bool
    sensitive: bool = False
    comment: Optional[str] = None


@dataclass
class Table:
    schema: str
    name: str
    columns: List[Column]
    rls_enabled: bool = False
    rows: int = 0
    pages: int = 0

    @property
    def visible_columns(self) -> List[Column]:
        return [c for c in self.columns if c.can_select]

    @property
    def hidden_columns(self) -> List[Column]:
        return [c for c in self.columns if not c.can_select]

    @property
    def accessible(self) -> bool:
        return any(c.can_select for c in self.columns)

    def column(self, name: str) -> Optional[Column]:
        name = name.lower()
        return next((c for c in self.columns if c.name.lower() == name), None)


@dataclass
class ForeignKey:
    table: str
    columns: List[str]
    ref_table: str
    ref_columns: List[str]

    def describe(self) -> str:
        left = ", ".join(f"{self.table}.{c}" for c in self.columns)
        right = ", ".join(f"{self.ref_table}.{c}" for c in self.ref_columns)
        return f"{left} = {right}"


@dataclass
class RlsPolicy:
    table: str
    name: str
    command: str
    using: Optional[str]


@dataclass
class SchemaSnapshot:
    role: str
    tables: Dict[str, Table] = field(default_factory=dict)
    foreign_keys: List[ForeignKey] = field(default_factory=list)
    policies: List[RlsPolicy] = field(default_factory=list)
    value_hints: Dict[Tuple[str, str], List[str]] = field(default_factory=dict)
    loaded_at: float = field(default_factory=time.time)

    # ---- lookups -------------------------------------------------------------------------
    def table(self, name: str) -> Optional[Table]:
        return self.tables.get(name.lower())

    def accessible_tables(self) -> List[Table]:
        return [t for t in self.tables.values() if t.accessible]

    def schemas(self) -> set:
        return {t.schema for t in self.tables.values()}

    def usable_foreign_keys(self) -> List[ForeignKey]:
        """Foreign keys whose columns the role can actually use in a join."""
        out = []
        for fk in self.foreign_keys:
            a, b = self.table(fk.table), self.table(fk.ref_table)
            if not a or not b:
                continue
            if all((a.column(c) and a.column(c).can_select) for c in fk.columns) and \
               all((b.column(c) and b.column(c).can_select) for c in fk.ref_columns):
                out.append(fk)
        return out

    def policies_for(self, table: str) -> List[RlsPolicy]:
        return [p for p in self.policies if p.table == table.lower()]

    # ---- size-relative thresholds (replace the old absolute numbers) ----------------------
    @property
    def largest_table_rows(self) -> int:
        return max((t.rows for t in self.accessible_tables()), default=0)

    @property
    def scan_cost_unit(self) -> float:
        """Planner cost of one sequential scan of the biggest table (1 per page + 0.01 per row)."""
        cost = max((t.pages + 0.01 * t.rows for t in self.accessible_tables()), default=0.0)
        return max(cost, policy.MIN_SCAN_COST_UNIT)

    @property
    def cost_low(self) -> float:
        return policy.COST_LOW_FACTOR * self.scan_cost_unit

    @property
    def cost_medium(self) -> float:
        return policy.COST_MEDIUM_FACTOR * self.scan_cost_unit

    @property
    def cost_high(self) -> float:
        return policy.COST_HIGH_FACTOR * self.scan_cost_unit


# ---- loading --------------------------------------------------------------------------------

_COLUMNS_SQL = """
SELECT n.nspname, c.relname, a.attname,
       format_type(a.atttypid, a.atttypmod),
       has_schema_privilege(n.oid, 'USAGE')
         AND has_column_privilege(c.oid, a.attnum, 'SELECT') AS can_select,
       col_description(c.oid, a.attnum),
       c.relrowsecurity,
       -- planner statistics if the table was ANALYZEd, otherwise the live-row counter
       (CASE WHEN c.reltuples >= 0 THEN c.reltuples ELSE COALESCE(s.n_live_tup, 0) END)::bigint,
       c.relpages
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
WHERE c.relkind IN ('r', 'v', 'm', 'p')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg\\_toast%' AND n.nspname NOT LIKE 'pg\\_temp%'
ORDER BY n.nspname, c.relname, a.attnum
"""

_FK_SQL = """
SELECT cl.relname, fcl.relname,
  ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum ORDER BY k.ord),
  ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.attnum ORDER BY k.ord)
FROM pg_constraint con
JOIN pg_class cl ON cl.oid = con.conrelid
JOIN pg_class fcl ON fcl.oid = con.confrelid
WHERE con.contype = 'f'
"""

# Only policies that apply to the current role: directly, via PUBLIC, or via a role whose
# privileges it inherits ('USAGE'), which is the same test PostgreSQL uses for RLS.
_POLICY_SQL = """
SELECT tablename, policyname, cmd, qual
FROM pg_policies
WHERE roles = '{public}'
   OR EXISTS (SELECT 1 FROM unnest(roles) r
              WHERE r <> 'public' AND pg_has_role(current_user, r::name, 'USAGE'))
"""

_STATS_SQL = "SELECT tablename, attname, n_distinct FROM pg_stats"


def _load_value_hints(cur, tables: Dict[str, Table]) -> Dict[Tuple[str, str], List[str]]:
    """Exact spellings of columns with few distinct values (helps small LLMs get WHERE right)."""
    try:
        cur.execute(_STATS_SQL)
        stats = {(t, a): d for t, a, d in cur.fetchall()}
    except Exception:
        cur.connection.rollback()
        stats = {}

    hints = {}
    for table in tables.values():
        for col in table.visible_columns:
            if col.sensitive or not col.type.startswith(_TEXT_TYPES) or len(hints) >= 15:
                continue
            n_distinct = stats.get((table.name, col.name))
            # pg_stats hides tables with row-level security, so without stats only probe small tables
            if n_distinct is None and table.rows > 500_000:
                continue
            if n_distinct is not None and not (0 < n_distinct <= 20):
                continue
            try:
                cur.execute(sql.SQL("SELECT DISTINCT {c} FROM {s}.{t} WHERE {c} IS NOT NULL "
                                    "ORDER BY 1 LIMIT 21").format(
                    c=sql.Identifier(col.name), s=sql.Identifier(table.schema),
                    t=sql.Identifier(table.name)))
                values = [r[0] for r in cur.fetchall()]
            except Exception:
                cur.connection.rollback()
                continue
            if 0 < len(values) <= 20:
                hints[(table.name, col.name)] = values
    return hints


def load_snapshot(role: Optional[str] = None) -> SchemaSnapshot:
    """Read the catalogs as `role` (or as the login role when None). Always a fresh read."""
    with connection(role) as conn:
        cur = conn.cursor()
        cur.execute("SELECT current_user")
        who = cur.fetchone()[0]

        tables: Dict[str, Table] = {}
        cur.execute(_COLUMNS_SQL)
        for (schema, tname, cname, ctype, can_select, comment,
             rls, rows, relpages) in cur.fetchall():
            key = tname.lower()
            table = tables.get(key)
            if table is not None and table.schema != schema:
                if schema != "public":
                    continue  # same name in two schemas: the public one wins
                table = None
            if table is None:
                table = tables[key] = Table(schema, tname, [], bool(rls),
                                            int(rows), int(relpages))
            table.columns.append(Column(cname, ctype, bool(can_select),
                                        looks_sensitive(cname, comment), comment))

        cur.execute(_FK_SQL)
        fks = [ForeignKey(t, list(c), rt, list(rc)) for t, rt, c, rc in cur.fetchall()]

        cur.execute(_POLICY_SQL)
        policies = [RlsPolicy(t.lower(), n, cmd, q) for t, n, cmd, q in cur.fetchall()]

        hints = _load_value_hints(cur, tables)

    return SchemaSnapshot(who, tables, fks, policies, hints)


def assumable_roles() -> List[str]:
    """Roles the guardrail's login user may act as (it must be a member of them)."""
    with connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT rolname FROM pg_roles "
                    "WHERE pg_has_role(current_user, oid, 'SET') AND rolname <> current_user "
                    "AND NOT rolsuper AND rolname NOT LIKE 'pg\\_%' ORDER BY 1")
        return [r[0] for r in cur.fetchall()]


# ---- cache + change notification ------------------------------------------------------------

_cache: Dict[str, SchemaSnapshot] = {}
_cache_lock = threading.Lock()


def get_snapshot(role: Optional[str] = None) -> SchemaSnapshot:
    key = role or ""
    with _cache_lock:
        snap = _cache.get(key)
        if snap and (time.time() - snap.loaded_at) < policy.SNAPSHOT_MAX_AGE_SECONDS:
            return snap
    snap = load_snapshot(role)  # load outside the lock: it talks to the database
    with _cache_lock:
        _cache[key] = snap
    return snap


def refresh(role: Optional[str] = None, all_roles: bool = False) -> SchemaSnapshot:
    """Drop cached snapshots and reload the requested one."""
    with _cache_lock:
        if all_roles:
            _cache.clear()
        else:
            _cache.pop(role or "", None)
    return get_snapshot(role)


def invalidate_all():
    with _cache_lock:
        _cache.clear()


CHANNEL = "schema_changed"
_listener = {"thread": None, "stop": threading.Event(), "notifications": 0}


def _listen_loop(stop: threading.Event):
    conn = None
    while not stop.is_set():
        try:
            if conn is None:
                conn = new_connection()
                conn.autocommit = True
                conn.cursor().execute(f"LISTEN {CHANNEL}")
                invalidate_all()  # we may have missed a change while disconnected
            if select.select([conn], [], [], 1.0)[0]:
                conn.poll()
                if conn.notifies:
                    conn.notifies.clear()
                    _listener["notifications"] += 1
                    invalidate_all()
        except Exception:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            conn = None
            stop.wait(2.0)
    if conn is not None:
        conn.close()


def start_listener():
    """Start a background thread that LISTENs for schema_changed and clears the cache."""
    t = _listener["thread"]
    if t and t.is_alive():
        return
    _listener["stop"] = threading.Event()
    t = threading.Thread(target=_listen_loop, args=(_listener["stop"],),
                         name="schema-listener", daemon=True)
    _listener["thread"] = t
    t.start()


def stop_listener():
    _listener["stop"].set()
    t = _listener["thread"]
    if t:
        t.join(timeout=3)
    _listener["thread"] = None


def notification_count() -> int:
    return _listener["notifications"]
