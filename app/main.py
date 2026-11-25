from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.guardrail import schema_loader
from app.guardrail.audit import log_event
from app.guardrail.engine import run_query
from app.guardrail.pipeline import ask


@asynccontextmanager
async def lifespan(app: FastAPI):
    schema_loader.start_listener()   # LISTEN schema_changed -> refresh cached snapshots
    yield
    schema_loader.stop_listener()


app = FastAPI(title="LLM-to-SQL Guardrail", lifespan=lifespan)


class SQLRequest(BaseModel):
    sql: str
    role: Optional[str] = None


class QuestionRequest(BaseModel):
    question: str
    role: Optional[str] = None


def resolve_role(body_role: Optional[str], header_role: Optional[str]) -> Optional[str]:
    """The caller may act as a database role via the 'role' field or the X-DB-Role header.
    Only roles the guardrail's login user is a member of are accepted."""
    role = body_role or header_role
    if not role:
        return None
    if role not in schema_loader.assumable_roles():
        raise HTTPException(403, f"Unknown or not permitted role: {role}")
    return role


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/roles")
def roles():
    return {"roles": schema_loader.assumable_roles()}


@app.get("/schema")
def schema(x_db_role: Optional[str] = Header(None), role: Optional[str] = None):
    """What the given role can see, as read from the database catalogs."""
    snap = schema_loader.get_snapshot(resolve_role(role, x_db_role))
    return {
        "role": snap.role,
        "loaded_at": snap.loaded_at,
        "tables": {
            t.name: {
                "columns": [c.name for c in t.visible_columns],
                "sensitive": [c.name for c in t.visible_columns if c.sensitive],
                "hidden_columns": len(t.hidden_columns),
                "rows": t.rows,
                "row_level_security": t.rls_enabled,
            }
            for t in snap.accessible_tables()
        },
        "joins": [fk.describe() for fk in snap.usable_foreign_keys()],
        "rls_policies": [{"table": p.table, "name": p.name} for p in snap.policies],
    }


@app.post("/schema/refresh")
def schema_refresh():
    """Manual refresh (normally automatic via the event trigger + LISTEN/NOTIFY)."""
    schema_loader.invalidate_all()
    snap = schema_loader.get_snapshot()
    return {"refreshed": True, "tables": len(snap.accessible_tables())}


@app.post("/query")
def query(req: SQLRequest, x_db_role: Optional[str] = Header(None)):
    """Run raw SQL through the guardrail (no LLM involved)."""
    role = resolve_role(req.role, x_db_role)
    resp = run_query(req.sql, role=role)
    log_event("sql", None, resp)
    return resp


@app.post("/ask")
def ask_question(req: QuestionRequest, x_db_role: Optional[str] = Header(None)):
    """Natural language -> LLM -> guardrail -> repair loop -> result."""
    role = resolve_role(req.role, x_db_role)
    result = ask(req.question, role=role)
    log_event("question", req.question, result.final, result.repairs_used)
    return result
