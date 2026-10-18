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