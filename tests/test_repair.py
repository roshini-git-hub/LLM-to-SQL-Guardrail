"""Repair loop: dialect fixes, schema-aware hints, and the rule that security is never repaired.
The LLM is replaced by a scripted fake, so these tests need PostgreSQL but not Ollama."""
import pytest

from app.guardrail import pipeline
from app.guardrail.llm import system_prompt
from app.guardrail.repair import build_feedback, fix_dialect
from app.guardrail.schema_loader import get_snapshot


class FakeLLM:
    """Returns the given answers in order and remembers the feedback it was sent."""

    def __init__(self, monkeypatch, answers):
        self.answers = list(answers)
        self.feedback = []
        monkeypatch.setattr(pipeline, "generate_sql", lambda q, snap, model=None: self.answers.pop(0))
        monkeypatch.setattr(pipeline, "repair_sql", self._repair)

    def _repair(self, question, bad_sql, problems, snapshot, model=None):
        self.feedback.append(problems)
        return self.answers.pop(0)


# ---- dialect fixes ----------------------------------------------------------------------------

@pytest.mark.parametrize("sql,expected", [
    ("SELECT `name` FROM `customers` LIMIT 5", 'SELECT "name" FROM "customers" LIMIT 5'),
    ("SELECT TOP 5 name FROM customers", "SELECT name FROM customers LIMIT 5"),
    ("SELECT IFNULL(city, '-') FROM customers LIMIT 5", "SELECT COALESCE(city, '-') FROM customers LIMIT 5"),
    ("SELECT ISNULL(city, '-') FROM customers", "SELECT COALESCE(city, '-') FROM customers"),
])
def test_dialect_is_transpiled_to_postgres(sql, expected):
    assert fix_dialect(sql)[0] == expected


def test_valid_postgres_needs_no_dialect_fix():
    assert fix_dialect("SELECT name FROM customers WHERE city = 'Delhi' LIMIT 3") == []


def test_mysql_query_is_fixed_without_calling_the_llm(monkeypatch):
    llm = FakeLLM(monkeypatch, ["SELECT `name`, IFNULL(`city`, '-') FROM `customers` LIMIT 3"])
    result = pipeline.ask("names and cities", role="analyst")
    assert result.final.decision == "ALLOW" and len(result.final.rows) == 3
    assert result.repairs_used == 0 and result.dialect_fixes == 1
    assert llm.feedback == []
    assert [t["source"] for t in result.trail] == ["llm", "dialect_fix"]


# ---- schema-aware feedback --------------------------------------------------------------------

def test_feedback_names_real_columns_and_join_path():
    snap = get_snapshot("analyst")
    sql = "SELECT c.cust_name FROM customers c JOIN orders o ON c.id = o.customer_id LIMIT 5"
    fb = " ".join(build_feedback(sql, ["[column_not_found] Column 'cust_name' does not exist in table 'customers'"], snap))
    assert "Column cust_name does not exist in customers. Available: customer_id, name, city, created_at." in fb
    assert "Did you mean: name" in fb
    assert "orders joins customers on orders.customer_id = customers.customer_id." in fb


def test_feedback_never_reveals_hidden_columns_or_tables():
    snap = get_snapshot("analyst")
    fb = " ".join(build_feedback("SELECT mail FROM customers", ['Planner rejected the query: column "mail" does not exist'], snap))
    fb += " ".join(build_feedback("SELECT 1 FROM employe", ["[table_not_found] Table 'employe' does not exist"], snap))
    assert "email" not in fb and "phone" not in fb and "employees" not in fb
    prompt = system_prompt(snap)
    assert "email" not in prompt and "employees" not in prompt and "salary" not in prompt
    assert "email" in system_prompt(get_snapshot("support"))   # support is granted it


def test_table_typo_gets_closest_match():
    fb = build_feedback("SELECT name FROM product", ["[table_not_found] Table 'product' does not exist"], get_snapshot("analyst"))
    assert "Did you mean: products" in fb[0]


def test_wrong_column_is_repaired_with_precise_feedback(monkeypatch):
    llm = FakeLLM(monkeypatch, ["SELECT cust_name FROM customers LIMIT 3",
                                "SELECT name FROM customers LIMIT 3"])
    result = pipeline.ask("customer names", role="analyst")
    assert result.final.decision == "ALLOW" and result.repairs_used == 1
    assert "Available: customer_id, name, city, created_at" in llm.feedback[0][0]
    assert result.trail[1]["feedback_sent"] == llm.feedback[0]


def test_at_most_two_repairs(monkeypatch):
    llm = FakeLLM(monkeypatch, ["SELECT a FROM customers LIMIT 1", "SELECT b FROM customers LIMIT 1",
                                "SELECT c FROM customers LIMIT 1", "SELECT name FROM customers LIMIT 1"])
    result = pipeline.ask("x", role="analyst")
    assert result.repairs_used == 2 and result.final.decision == "BLOCK"
    assert len(result.trail) == 3 and len(llm.answers) == 1


# ---- security is never repaired ---------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "SELECT salary FROM employees",                 # forbidden table
    "SELECT email FROM customers LIMIT 5",          # forbidden column
    "DELETE FROM orders",                           # write
    "SELECT pg_sleep(10)",                          # dangerous function
    "SELECT * FROM customers",                      # star would expose hidden columns
])
def test_security_violation_is_blocked_and_never_sent_back(monkeypatch, sql):
    llm = FakeLLM(monkeypatch, [sql, "SELECT name FROM customers LIMIT 1"])
    result = pipeline.ask("anything", role="analyst")
    assert result.final.decision == "BLOCK"
    assert result.repairs_used == 0 and llm.feedback == [] and len(llm.answers) == 1
