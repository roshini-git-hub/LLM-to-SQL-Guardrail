# Tables and columns the guardrail considers allowed for the "analyst" role.
ALLOWED_SCHEMA = {
    "customers":   {"customer_id", "name", "city", "created_at"},
    "products":    {"product_id", "name", "category", "price"},
    "orders":      {"order_id", "customer_id", "order_date", "status", "total_amount"},
    "order_items": {"item_id", "order_id", "product_id", "quantity", "unit_price"},
}

# Tables that exist but must never be touched.
BLOCKED_TABLES = {"employees"}

# Columns that are sensitive even if the table is allowed.
SENSITIVE_COLUMNS = {"email", "phone", "salary"}

# Only these functions may appear in queries.
ALLOWED_FUNCTIONS = {
    "count", "sum", "avg", "min", "max", "round", "lower", "upper",
    "coalesce", "date_trunc", "extract", "length", "abs",
}

MAX_LIMIT = 1000
# --- Cost and risk thresholds (tune these later using evaluation results) ---
SEQ_SCAN_ROWS = 100000      # warn on sequential scans estimated above this many rows
HUGE_ROWS = 1000000         # warn if any plan step is estimated above this many rows
CARTESIAN_MIN_ROWS = 10000  # ignore tiny cross joins

COST_LOW = 20000            # planner cost units
COST_MEDIUM = 100000
COST_HIGH = 500000

REVIEW_AT = 35              # risk score at or above this -> REVIEW
BLOCK_AT = 70               # risk score at or above this -> BLOCK

# SQLGlot reports some functions under different names than the SQL text
ALLOWED_FUNCTIONS |= {
    "timestamp_trunc", "current_timestamp", "now",
    "current_date", "current_time",
}

# Window functions
ALLOWED_FUNCTIONS |= {"row_number", "rank", "dense_rank", "lag", "lead"}

# --- Added after the final evaluation (not measured on the final set) ---
ALLOWED_FUNCTIONS |= {
    "nullif", "trim", "ltrim", "rtrim", "concat", "group_concat", "string_agg",
    "substring", "replace", "greatest", "least", "floor", "ceil",
}

# --- Added after the final evaluation (not measured on the final set) ---
ALLOWED_FUNCTIONS |= {
    "nullif", "trim", "ltrim", "rtrim", "concat", "group_concat", "string_agg",
    "substring", "replace", "greatest", "least", "floor", "ceil",
}

# Tables that have columns hidden from this role (SELECT * would expand into them)
TABLES_WITH_HIDDEN_COLUMNS = {"customers"}
