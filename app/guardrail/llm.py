"""Talks to the local LLM (Ollama). The prompt is built from the role's live schema snapshot,
so the model only ever sees tables and columns that role is allowed to read."""
import os
import re
import time
from typing import List, Optional

import ollama
from dotenv import load_dotenv

from app.guardrail import policy
from app.guardrail.schema_loader import SchemaSnapshot

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = ollama.Client(host=HOST)
    return _client


def schema_text(snapshot: SchemaSnapshot) -> str:
    """One line per readable table, listing ONLY the columns this role can SELECT."""
    lines = []
    for t in sorted(snapshot.accessible_tables(), key=lambda t: t.name):
        cols = ", ".join(c.name for c in t.visible_columns)
        lines.append(f"{t.name}({cols})")
    return "\n".join(lines)


def relationships_text(snapshot: SchemaSnapshot) -> str:
    return "\n".join(f"- JOIN ON {fk.describe()}" for fk in snapshot.usable_foreign_keys())


def value_hints_text(snapshot: SchemaSnapshot) -> str:
    return "\n".join(f"- {t}.{c}: " + ", ".join(repr(v) for v in values)
                     for (t, c), values in sorted(snapshot.value_hints.items()))


def system_prompt(snapshot: SchemaSnapshot) -> str:
    parts = [
        "You translate questions into PostgreSQL SELECT queries.",
        "",
        "Database schema (the only tables and columns you may use):",
        schema_text(snapshot),
    ]
    rel = relationships_text(snapshot)
    if rel:
        parts += ["", "How tables join (use exactly these conditions):", rel]
    hints = value_hints_text(snapshot)
    if hints:
        parts += ["", "Exact values stored in the data (copy these spellings exactly, "
                      "they are case-sensitive):", hints]
    rls = sorted({p.table for p in snapshot.policies})
    if rls:
        parts += ["", "Rows in " + ", ".join(rls) + " are already filtered for this user by "
                      "the database; do not add extra filters for that."]
    parts += [
        "",
        "Rules:",
        "- Output exactly one SQL query and nothing else: no explanation, no markdown.",
        "- PostgreSQL syntax only (no backticks, no TOP n, no IFNULL).",
        "- Only SELECT statements. Never modify data.",
        "- Use only the tables and columns listed above.",
        "- Never use SELECT *; list the columns you need.",
        "- Always join with explicit conditions.",
        f"- Add LIMIT (at most {policy.MAX_LIMIT}) unless the query is an aggregate.",
        "- If the question cannot be answered with this schema, output exactly: CANNOT_ANSWER",
    ]
    return "\n".join(parts) + "\n"


def extract_sql(text: str) -> str:
    text = text.strip()

    # Prefer a fenced code block if the model used one
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    if "CANNOT_ANSWER" in text:
        return "CANNOT_ANSWER"

    # Drop any chatter before the first SELECT/WITH
    m = re.search(r"\b(SELECT|WITH)\b", text, flags=re.IGNORECASE)
    if m:
        text = text[m.start():]

    return text.strip()


def chat(system: str, user_message: str, model: Optional[str] = None) -> str:
    """Call Ollama, retrying a few times because a model can fail to load temporarily."""
    last_error = None
    for attempt in range(4):
        try:
            resp = _get_client().chat(
                model=model or MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user_message}],
                options={"temperature": 0, "num_predict": 800},
            )
            return extract_sql(resp["message"]["content"])
        except Exception as e:
            last_error = e
            time.sleep(5 * (attempt + 1))
    raise last_error


def generate_sql(question: str, snapshot: SchemaSnapshot, model: Optional[str] = None) -> str:
    return chat(system_prompt(snapshot), f"Question: {question}", model)


def repair_sql(question: str, bad_sql: str, problems: List[str], snapshot: SchemaSnapshot,
               model: Optional[str] = None) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return chat(
        system_prompt(snapshot),
        f"Question: {question}\n\n"
        f"This query was rejected:\n{bad_sql}\n\n"
        f"Problems found:\n{listed}\n\n"
        "Write a corrected query that answers the same question and fixes the problems. "
        "Output only the SQL.",
        model,
    )
