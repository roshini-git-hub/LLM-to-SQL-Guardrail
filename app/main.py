from fastapi import FastAPI
from pydantic import BaseModel

from app.guardrail.audit import log_event
from app.guardrail.engine import run_query
from app.guardrail.pipeline import ask

app = FastAPI(title="LLM-to-SQL Guardrail")


class SQLRequest(BaseModel):
    sql: str


class QuestionRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query")
def query(req: SQLRequest):
    """Run raw SQL through the guardrail (no LLM involved)."""
    resp = run_query(req.sql)
    log_event("sql", None, resp)
    return resp


@app.post("/ask")
def ask_question(req: QuestionRequest):
    """Natural language -> LLM -> guardrail -> repair loop -> result."""
    result = ask(req.question)
    log_event("question", req.question, result.final, result.repairs_used)
    return result
