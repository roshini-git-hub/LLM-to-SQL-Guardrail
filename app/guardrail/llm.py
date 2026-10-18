import os
import re

import ollama
from dotenv import load_dotenv

from app.guardrail import policy

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")
HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = ollama.Client(host=HOST)
    return _client


def schema_text() -> str:
    lines = []
    for table, cols in policy.ALLOWED_SCHEMA.items():
        lines.append(f"{table}({', '.join(sorted(cols))})")
    return "\n".join(lines)


RELATIONSHIPS = """orders.customer_id -> customers.customer_id
order_items.order_id -> orders.order_id
order_items.product_id -> products.product_id"""

SYSTEM_PROMPT = f"""You translate questions into PostgreSQL SELECT queries.

Database schema (the only tables and columns you may use):
{schema_text()}

Relationships:
{RELATIONSHIPS}

Rules:
- Output exactly one SQL query and nothing else: no explanation, no markdown.
- Only SELECT statements. Never modify data.
- Use only the tables and columns listed above.
- Never use SELECT *; list the columns you need.
- Always join with explicit conditions.
- Add LIMIT (at most {policy.MAX_LIMIT}) unless the query is an aggregate.
- If the question cannot be answered with this schema, output exactly: CANNOT_ANSWER
"""


def _extract_sql(text: str) -> str:
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


def _call(user_message: str) -> str:
    resp = _get_client().chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        options={"temperature": 0, "num_predict": 800},
    )
    return _extract_sql(resp["message"]["content"])


def generate_sql(question: str) -> str:
    return _call(f"Question: {question}")


def repair_sql(question: str, bad_sql: str, reasons: list) -> str:
    problems = "\n".join(f"- {r}" for r in reasons)
    return _call(
        f"Question: {question}\n\n"
        f"This query was rejected:\n{bad_sql}\n\n"
        f"Problems found:\n{problems}\n\n"
        "Write a corrected query that answers the same question and fixes the problems. "
        "Output only the SQL."
    )
